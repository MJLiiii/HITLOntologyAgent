"""Isolated live PostgreSQL migration/publication/recovery and coordinated restore check.

Creates only the labelled oe-studio-pg-check container; removes it in finally. All
application state is synthetic and separate from .data. Durable evidence excludes
credentials and session keys. Existing containers are never replaced or stopped.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL

from oe_studio.db import Base

ROOT = Path(__file__).resolve().parents[1]
NAME = 'oe-studio-pg-check'
USER = 'ontology_studio'


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hashes(root):
    return {str(path.relative_to(root)): file_hash(path) for path in sorted(root.rglob('*')) if path.is_file()}


def database_state(url, data_dir):
    """Verify DB/artifact/Git references and return a credential-free comparison manifest."""
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            tables = set(inspect(connection).get_table_names())
            if tables != set(Base.metadata.tables) | {'alembic_version'}:
                raise ValueError('Unexpected database tables')
            differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
            if differences:
                raise ValueError('Restored schema differs from the SQLAlchemy model')
            rows = {table: [dict(row) for row in connection.execute(text(f'SELECT * FROM {table} ORDER BY 1')).mappings()]
                    for table in sorted(tables)}
    finally:
        engine.dispose()
    artifacts = data_dir / 'artifacts'
    artifact_hashes = tree_hashes(artifacts)
    if any(name != sha for name, sha in artifact_hashes.items()):
        raise ValueError('Content-addressed artifact hash mismatch')
    def verify_refs(value):
        if isinstance(value, dict):
            if {'sha256', 'byte_length', 'media_type'} <= value.keys():
                path = artifacts / value['sha256']
                if not path.is_file() or path.stat().st_size != value['byte_length']:
                    raise ValueError('Broken database artifact reference')
            for child in value.values():
                verify_refs(child)
        elif isinstance(value, list):
            for child in value:
                verify_refs(child)
    for row in rows['items']:
        verify_refs(row['data'])
    git = data_dir / 'ontology.git'
    subprocess.run(['git', '--git-dir', str(git), 'fsck', '--full'], capture_output=True, check=True, timeout=30)
    refs = subprocess.run(['git', '--git-dir', str(git), 'show-ref'], capture_output=True, text=True, timeout=30)
    if refs.returncode not in (0, 1):
        raise ValueError('Cannot verify approved Git refs')
    refs_by_name = {line.split()[1]: line.split()[0] for line in refs.stdout.splitlines()}
    items = {row['id']: row for row in rows['items']}
    for project in rows['projects']:
        if project['pending_publication_id']:
            raise ValueError('A pending publication remains after recovery')
        if project['approved_version_id']:
            version = items[project['approved_version_id']]
            if (version['kind'] != 'version' or version['status'] != 'approved'
                    or refs_by_name.get(f"refs/heads/{project['id']}-approved") != version['data']['commit']):
                raise ValueError('Database approved version and Git head differ')
    return {'tables': {name: {'rows': len(values), 'sha256': hashlib.sha256(
                json.dumps(values, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()}
                for name, values in rows.items()}, 'artifacts': artifact_hashes,
            'git_refs': sorted(refs.stdout.splitlines()), 'git_files': tree_hashes(git),
            'schema_matches_models': True, 'artifact_references_valid': True, 'approved_heads_match': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    nonce = uuid4().hex
    state = (args.output or ROOT / 'research/results/postgres-check' / nonce).resolve()
    if state.exists():
        raise SystemExit('Choose a new output directory; verification evidence is append-only.')
    if state == (ROOT / '.data').resolve() or state.is_relative_to((ROOT / '.data').resolve()):
        raise SystemExit('The check cannot write into persistent application .data.')
    image_match = re.search(r'^\s*image:\s*(postgres:[^\s]+@sha256:[a-f0-9]{64})\s*$',
                            (ROOT / 'infra/compose.yaml').read_text(), re.MULTILINE)
    if not image_match:
        raise SystemExit('Expected an exact official PostgreSQL image digest in infra/compose.yaml.')
    image = image_match.group(1)
    password = secrets.token_urlsafe(32)
    def redact(value):
        return value.replace(password, '<redacted>')
    def run(command, *, timeout=60, check=True, input=None, output=None, env=None):
        result = subprocess.run(command, input=input, stdout=output or subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=timeout, env=env, cwd=ROOT)
        if check and result.returncode:
            details = redact(result.stderr.decode(errors='replace'))[-6000:]
            raise RuntimeError(f'{command[0]} exited {result.returncode}: {details}')
        return result
    existing = run(['docker', 'container', 'inspect', NAME], check=False)
    if existing.returncode == 0:
        raise SystemExit(f'{NAME} already exists; refusing to replace or stop it.')
    # Prove the daemon is reachable before treating an inspect error as absence.
    run(['docker', 'info', '--format', '{{.ServerVersion}}'])
    state.mkdir(parents=True, mode=0o700)
    (state / 'owner.json').write_text(json.dumps({'nonce': nonce, 'container': NAME, 'classification': 'synthetic_software_verification'}))
    report = {'schema_version': 1, 'classification': 'synthetic_software_verification_not_human_study',
              'image': image, 'container': NAME, 'port': '127.0.0.1:54329', 'status': 'started',
              'credentials_retained': False, 'persistent_application_data_touched': False,
              'engine_scope': 'workflow engine reports are explicit fixtures; real Jena/OntoCheck verified separately',
              'checks': []}
    created = False
    try:
        with tempfile.TemporaryDirectory(prefix='oe-pg-check-credentials-') as temp:
            env_file = Path(temp) / 'postgres.env'
            env_file.write_text(f'POSTGRES_USER={USER}\nPOSTGRES_DB=ontology_studio\nPOSTGRES_PASSWORD={password}\n')
            env_file.chmod(0o600)
            # docker run can create a stopped container even if port allocation fails.
            # The finalizer checks the nonce before removing any container with this name.
            created = True
            run(['docker', 'run', '--detach', '--name', NAME, '--label', f'oe.check.owner={nonce}',
                 '--publish', '127.0.0.1:54329:5432', '--env-file', str(env_file),
                 '--tmpfs', '/var/lib/postgresql/data:rw', image], timeout=240)
            deadline = time.monotonic() + 60
            while run(['docker', 'exec', NAME, 'pg_isready', '-U', USER, '-d', 'ontology_studio'], check=False).returncode:
                if time.monotonic() > deadline:
                    raise RuntimeError('Isolated PostgreSQL did not become ready')
                time.sleep(.25)
            report['postgres_version'] = run(['docker', 'exec', NAME, 'postgres', '--version']).stdout.decode().strip()
            print('Isolated PostgreSQL ready; running migrations, concurrent publishers and crash recovery.', flush=True)
            base_url = URL.create('postgresql+psycopg', username=USER, password=password,
                                  host='127.0.0.1', port=54329, database='ontology_studio')
            env = {**os.environ, 'PYTHONPATH': str(ROOT / 'services/api/src'),
                   'OE_POSTGRES_CHECK_URL': base_url.render_as_string(hide_password=False),
                   'OE_POSTGRES_CHECK_STATE': str(state), 'OE_POSTGRES_CHECK_OWNER': nonce, 'OE_SERVICE_TOKEN': ''}
            result = run([sys.executable, '-m', 'pytest', 'tests/integration/test_postgres.py', '-q',
                          '--junitxml=' + str(state / 'pytest.xml')], env=env, timeout=240, check=False)
            output = redact(result.stdout.decode(errors='replace') + result.stderr.decode(errors='replace'))
            (state / 'pytest.log').write_text(output)
            # Test assertion tracebacks may include env values; redact durable JUnit too.
            junit = state / 'pytest.xml'
            if junit.exists():
                junit.write_text(redact(junit.read_text()))
            print(output[-6000:], flush=True)
            if result.returncode:
                raise RuntimeError('PostgreSQL tests failed; inspect the redacted pytest.log')
            for case_file in sorted(state.glob('oe_check_*.json')):
                case = json.loads(case_file.read_text())
                database = case['database']
                if not re.fullmatch('oe_check_[a-z0-9_]+', database):
                    raise ValueError('Unexpected test database name')
                source = state / case['data_relative']
                before = database_state(base_url.set(database=database), source)
                backup = state / 'backups' / database
                backup.mkdir(parents=True)
                with (backup / 'database.dump').open('xb') as stream:
                    run(['docker', 'exec', NAME, 'pg_dump', '-U', USER, '--format=custom', '--no-owner',
                         '--no-acl', database], output=stream)
                for name in ('artifacts', 'ontology.git'):
                    shutil.copytree(source / name, backup / name)
                if database_state(base_url.set(database=database), source) != before:
                    raise ValueError('Application changed during coordinated backup')
                restore_name = 'restore_' + uuid4().hex[:16]
                run(['docker', 'exec', NAME, 'createdb', '-U', USER, restore_name])
                run(['docker', 'exec', '-i', NAME, 'pg_restore', '-U', USER, '--exit-on-error', '--no-owner',
                     '--no-acl', '-d', restore_name], input=(backup / 'database.dump').read_bytes())
                restored = state / 'restored' / database
                restored.mkdir(parents=True)
                for name in ('artifacts', 'ontology.git'):
                    shutil.copytree(backup / name, restored / name)
                after = database_state(base_url.set(database=restore_name), restored)
                if before != after:
                    raise ValueError('Restored database rows, artifact bytes or approved Git state differ')
                evidence = {**case, 'restored_equal': True, 'database_dump_sha256': file_hash(backup / 'database.dump'),
                            'state': before}
                (backup / 'backup-manifest.json').write_text(json.dumps(evidence, sort_keys=True, indent=2) + '\n')
                report['checks'].append(evidence)
            if len(report['checks']) != 7:
                raise ValueError('Expected all seven migration/concurrency/recovery/team-account verification cases')
            report['status'] = 'passed'
            print('All seven databases restored with identical rows, artifacts and Git heads.', flush=True)
    except Exception as exc:
        report.update(status='failed', error=redact(str(exc)))
        raise
    finally:
        # These are only synthetic check-owned local cookies; never retain reusable keys.
        for key in state.rglob('session.key'):
            key.unlink()
        if created:
            owner = run(['docker', 'inspect', '--format', '{{ index .Config.Labels "oe.check.owner" }}', NAME], check=False)
            if owner.returncode == 0 and owner.stdout.decode().strip() == nonce:
                cleanup = run(['docker', 'rm', '--force', '--volumes', NAME], check=False)
                report['owned_container_removed'] = cleanup.returncode == 0
            else:
                report['owned_container_removed'] = False
        (state / 'report.json').write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
        print(f'Redacted PostgreSQL evidence: {state / "report.json"}', flush=True)


if __name__ == '__main__':
    main()
