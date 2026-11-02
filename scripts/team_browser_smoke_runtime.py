"""Disposable, no-model PostgreSQL runtime for actual-browser synthetic verification.

Run start outside a restrictive process sandbox; stop removes only this helper's
labelled container and processes. Credentials/logs stay in a private temporary
folder, never in the retained evidence directory or the working .data store.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import signal
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / '.venv/bin/python'
IMAGE = 'postgres:17.6-alpine3.22@sha256:ef257d85f76e48da1c64832459b59fcaba1a4dac97bf5d7450c77753542eee94'
LABEL = 'oe.synthetic.team-browser'


def run(args, env=None, **kwargs):
    return subprocess.run(args, env=env, check=True, capture_output=True, text=True, **kwargs)


def free_port(port):
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('127.0.0.1', port))


def environment(private):
    env = {key: os.environ[key] for key in ('PATH', 'HOME', 'TMPDIR', 'LANG') if key in os.environ}
    env.update(json.loads((private / 'environment.json').read_text()))
    return env


def process_identity(pid):
    result = subprocess.run(['ps', '-p', str(pid), '-o', 'lstart=', '-o', 'command='],
                            capture_output=True, text=True, check=False)
    if result.returncode == 1 and not result.stdout.strip():
        return None
    if result.returncode != 0:
        raise SystemExit('Cannot verify process identity; leaving runtime untouched')
    identity = result.stdout.strip()
    if not identity:
        raise SystemExit('Empty process identity; leaving runtime untouched')
    return identity


def stop(private):
    state_path = private / 'state.json'
    if not state_path.exists():
        print('No active owned runtime state; nothing to stop.')
        return
    state = json.loads(state_path.read_text())
    if state.get('stopped'):
        print('Owned runtime already stopped.')
        return
    name = state['container']
    result = run(['docker', 'inspect', '--format', '{{ index .Config.Labels "' + LABEL + '" }}', name])
    if result.stdout.strip() != state['owner']:
        raise SystemExit('Refusing cleanup: container has different owner label')
    if state.get('pids') and not state.get('processes'):
        raise SystemExit('Refusing cleanup: legacy state has no process identities')
    processes = state.get('processes', [])
    # Preflight every identity before signalling any process group.
    for process in processes:
        current = process_identity(process['pid'])
        if current is not None and current != process['identity']:
            raise SystemExit('Refusing cleanup: process identity changed; leaving runtime untouched')
    for process in reversed(processes):
        current = process_identity(process['pid'])
        if current is None:
            continue
        if current != process['identity']:
            raise SystemExit('Refusing cleanup: process identity changed; leaving this process untouched')
        try:
            os.killpg(process['pid'], signal.SIGTERM)
        except ProcessLookupError:
            pass
    run(['docker', 'rm', '-f', name])
    state['stopped'] = True
    state_path.write_text(json.dumps(state))
    shutil.rmtree(private)
    print('Owned processes stopped and labelled disposable PostgreSQL container removed.')


def start():
    for port in (8016, 5186, 55436):
        free_port(port)
    private = Path(tempfile.mkdtemp(prefix='oe-team-browser-'))
    private.chmod(0o700)
    owner = secrets.token_hex(8)
    name = 'oe-team-browser-' + owner
    password = secrets.token_urlsafe(24)
    env = dict(OE_MODE='team', OE_DATA_DIR=str(private / 'data'),
               OE_DATABASE_URL=f'postgresql+psycopg://studio:{password}@127.0.0.1:55436/studio',
               OE_TEAM_ORIGIN='http://127.0.0.1:5186', OE_TEAM_ALLOW_INSECURE_LOOPBACK='true',
               OE_EMBEDDED_WORKER='false', OE_EAGER_JOBS='false',
               PYTHONPATH=str(ROOT / 'services/api/src'),
               OE_JAVA_EXECUTABLE='/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home/bin/java',
               OE_ONTOCHECK_PYTHON=str(ROOT / '.venv-ontocheck/bin/python'),
               STUDIO_API_URL='http://127.0.0.1:8016')
    (private / 'environment.json').write_text(json.dumps(env))
    (private / 'empty.env').write_text('')
    state = {'owner': owner, 'container': name, 'processes': [], 'private': str(private)}
    state_path = private / 'state.json'
    state_path.write_text(json.dumps(state))
    clean = environment(private)
    docker_env = {**clean, 'POSTGRES_PASSWORD': password}
    run(['docker', 'run', '-d', '--name', name, '--label', LABEL + '=' + owner,
         '-p', '127.0.0.1:55436:5432', '-e', 'POSTGRES_USER=studio', '-e', 'POSTGRES_DB=studio',
         '-e', 'POSTGRES_PASSWORD', IMAGE], env=docker_env)
    try:
        for _ in range(60):
            ready = subprocess.run(['docker', 'exec', name, 'pg_isready', '-U', 'studio'], capture_output=True)
            if ready.returncode == 0:
                break
            time.sleep(.5)
        else:
            raise RuntimeError('Disposable PostgreSQL did not become ready')
        bootstrap = '''from pathlib import Path
import json
from alembic import command
from alembic.config import Config
from sqlalchemy import select
from oe_studio.settings import Settings
from oe_studio.workflow import Studio
from oe_studio.db import Project
from oe_studio.accounts import create_account,grant_project
root=Path(%r)
config=Config(str(root/'alembic.ini'))
config.set_main_option('script_location',str(root/'migrations'))
# Migration env resolves Settings from this private cwd; there is no .env here.
command.upgrade(config,'head')
studio=Studio(Settings(_env_file=None))
with studio.db.session() as session:
    project=session.scalar(select(Project))
records=[]
for role in ('researcher','reviewer','approver','viewer'):
    account=create_account(studio.db,'browser-'+role,'Synthetic-browser-only-2026!')
    grant_project(studio.db,account.id,project.id,[role])
    records.append({'username':account.username,'role':role,'subject':account.id})
Path('accounts.json').write_text(json.dumps({'project_id':project.id,'accounts':records}))
studio.db.engine.dispose()
''' % str(ROOT)
        run([str(PYTHON), '-c', bootstrap], env=clean, cwd=private)
        api = private / 'api.py'
        api.write_text("from oe_studio.main import create_app\nfrom oe_studio.settings import Settings\napp=create_app(Settings(_env_file=None))\n")
        commands = [
            [str(PYTHON), '-m', 'uvicorn', 'api:app', '--host', '127.0.0.1', '--port', '8016'],
            [str(PYTHON), '-m', 'oe_studio.worker', '--env-file', str(private / 'empty.env')],
            ['node', str(ROOT / 'apps/studio-plugin/node_modules/vite/bin/vite.js'), str(ROOT / 'apps/studio-plugin'), '--host', '127.0.0.1', '--port', '5186'],
        ]
        for index, args in enumerate(commands):
            proc = subprocess.Popen(args, env=clean, cwd=private, stdout=(private / f'process-{index}.log').open('w'), stderr=subprocess.STDOUT, start_new_session=True)
            identity = process_identity(proc.pid)
            if identity is not None:
                state['processes'].append({'pid': proc.pid, 'identity': identity})
            state_path.write_text(json.dumps(state, indent=2))
        for _ in range(80):
            try:
                urllib.request.urlopen('http://127.0.0.1:5186', timeout=1).close()
                urllib.request.urlopen('http://127.0.0.1:8016/health/live', timeout=1).close()
                break
            except Exception:
                time.sleep(.5)
        else:
            raise RuntimeError('API/frontend did not become ready; inspect private logs')
        print(json.dumps({'private_runtime': str(private), 'origin': 'http://127.0.0.1:5186', 'accounts': ['browser-'+role for role in ('researcher','reviewer','approver','viewer')]}))
    except Exception:
        stop(private)
        raise


def snapshot(private, destination):
    destination.mkdir(parents=True, exist_ok=True)
    code = """import json,os
from pathlib import Path
from sqlalchemy import select,text
from oe_studio.db import Database,Project,Item,Job,Account,ProjectMembership
private=Path(%r)
destination=Path(%r)
db=Database(os.environ['OE_DATABASE_URL'])
fields={'proposal_id','revision','revision_id','bundle_digest','base_version_id','status','decision','rationale','digest','test_suite_id','test_suite_digest','source_revision_id','successor_revision_id','version_id','git_commit','commit','validation_run_id','assessment_run_ids','review_id','approval_ids','profile','engine','cases','limitations','vocabulary_coverage','vocabulary_utilisation','strict_fitness','approximate_fitness','publication_id','created_at','generator','target_ontology_sha256','input_manifest'}
# Recursively remove session/transport identities even within a selected report.
def clean(value):
    if isinstance(value,dict):
        return {key:clean(item) for key,item in value.items() if not any(part in key.lower() for part in ('password','token','secret','session','csrf','credential'))}
    if isinstance(value,list):return [clean(item) for item in value]
    return value
with db.session() as session:
    result={'scope':'synthetic software verification, not an expert study','database':'PostgreSQL','migration':session.execute(text('select version_num from alembic_version')).scalar(),'jobs_mode':'separate worker, non-eager','model_calls_authorized':False,'projects':[],'accounts':[],'records':[],'jobs':[]}
    for project in session.scalars(select(Project)):
        result['projects'].append({'id':project.id,'name':project.name,'approved_version_id':project.approved_version_id,'pending_publication_id':project.pending_publication_id,'scope_accepted':project.data.get('scope_accepted')})
    for account in session.scalars(select(Account)):
        memberships=list(session.scalars(select(ProjectMembership).where(ProjectMembership.account_id==account.id)))
        result['accounts'].append({'subject':account.id,'username':account.username,'memberships':[{'project_id':item.project_id,'roles':item.roles} for item in memberships]})
    for item in session.scalars(select(Item).order_by(Item.created_at)):
        if item.kind in {'revision','validation','assessment','review','publication','version','test_suite','test-oracle-decision','scope-decision','test_oracle_decision','scope_decision','generation_run','oracle_decision','publication_commit'}:
            result['records'].append({'id':item.id,'kind':item.kind,'status':item.status,'actor_subject':item.data.get('actor',{}).get('subject'),'data':clean({key:value for key,value in item.data.items() if key in fields})})
    result['record_kinds']=sorted(set(session.scalars(select(Item.kind))))
    for job in session.scalars(select(Job)):
        result['jobs'].append({'id':job.id,'kind':job.kind,'status':job.status,'attempt':job.attempt,'actor_subject':job.actor.get('subject'),'error':job.error})
(destination/'evidence.json').write_text(json.dumps(result,indent=2))
db.engine.dispose()
""" % (str(private), str(destination.resolve()))
    run([str(PYTHON), '-c', code], env=environment(private), cwd=private)
    print('Sanitized synthetic verification evidence exported.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'stop', 'snapshot'])
    parser.add_argument('--private-runtime', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT/'research/results/two-agent-team-browser')
    args = parser.parse_args()
    if args.action == 'start':
        start()
    elif args.action == 'snapshot' and args.private_runtime:
        snapshot(args.private_runtime, args.output)
    elif args.private_runtime:
        stop(args.private_runtime)
    else:
        parser.error('stop requires --private-runtime')


if __name__ == '__main__':
    main()
