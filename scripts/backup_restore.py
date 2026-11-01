"""Offline SQLite/artifact/bare-Git backup and isolated restoration verification.

Stop Studio before running. PostgreSQL deployments require pg_dump/pg_restore and
coordinated artifact/Git snapshots; this utility refuses non-SQLite stores.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file() and p.name != 'backup-manifest.json'}


def inspect(root):
    database = root / 'studio.sqlite'
    if not database.is_file():
        raise ValueError('Expected a local studio.sqlite; PostgreSQL needs pg_dump/pg_restore')
    with sqlite3.connect(f'{database.as_uri()}?mode=ro', uri=True) as connection:
        if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('SQLite integrity check failed')
        if connection.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('SQLite foreign key check failed')
        projects = connection.execute('SELECT id, approved_version_id FROM projects ORDER BY id').fetchall()
        items = connection.execute('SELECT id, kind, data FROM items ORDER BY id').fetchall()
    artifact_root = root / 'artifacts'
    for path in artifact_root.iterdir() if artifact_root.is_dir() else []:
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != path.name:
            raise ValueError(f'Artifact hash mismatch: {path.name}')

    def verify_refs(value):
        if isinstance(value, dict):
            if {'sha256', 'byte_length', 'media_type'} <= value.keys():
                path = artifact_root / value['sha256']
                if not path.is_file() or path.stat().st_size != value['byte_length']:
                    raise ValueError('Broken artifact reference in workflow record')
            for child in value.values():
                verify_refs(child)
        elif isinstance(value, list):
            for child in value:
                verify_refs(child)

    for _, _, data in items:
        verify_refs(json.loads(data))
    git = root / 'ontology.git'
    if not git.is_dir():
        raise ValueError('Missing ontology.git')
    subprocess.run(['git', '--git-dir', str(git), 'fsck', '--full'], capture_output=True, check=True)
    refs = subprocess.run(['git', '--git-dir', str(git), 'show-ref'], capture_output=True, text=True)
    if refs.returncode not in (0, 1):
        raise ValueError('Cannot read approved Git refs')
    return {'projects': projects, 'item_count': len(items),
            'workflow_rows_sha256': hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest(),
            'git_refs': sorted(refs.stdout.splitlines())}


def backup(source, target):
    source, target = source.resolve(), target.resolve()
    if source == target or source in target.parents or target in source.parents:
        raise ValueError('Backup destination must be separate from application data')
    if target.exists():
        raise ValueError('Backup destination must not already exist')
    before = inspect(source)
    target.mkdir(parents=True)
    for name in ('artifacts', 'ontology.git'):
        shutil.copytree(source / name, target / name)
    with sqlite3.connect(f'{(source / "studio.sqlite").as_uri()}?mode=ro', uri=True) as origin:
        with sqlite3.connect(target / 'studio.sqlite') as destination:
            origin.backup(destination)
    after = inspect(source)
    if before != after or inspect(target) != before:
        raise ValueError('Store changed while backing up; stop Studio and retry to a fresh destination')
    manifest = {'schema_version': 1, 'contents': hashes(target), 'state': before,
                'session_key_excluded': True, 'requirement': 'application_stopped'}
    (target / 'backup-manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return manifest


def restore(source, target):
    source, target = source.resolve(), target.resolve()
    manifest = json.loads((source / 'backup-manifest.json').read_text())
    if hashes(source) != manifest['contents']:
        raise ValueError('Backup content hash mismatch')
    if target.exists():
        raise ValueError('Restore destination must not already exist')
    shutil.copytree(source, target)
    if hashes(target) != manifest['contents']:
        raise ValueError('Restored content hash mismatch')
    # JSON stores tuples as lists, so normalize before comparison.
    actual = json.loads(json.dumps(inspect(target)))
    if actual != manifest['state']:
        raise ValueError('Restored workflow records or approved heads differ')
    return actual


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['backup', 'restore', 'check'])
    parser.add_argument('--data-dir', type=Path, default=Path('.data'))
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    if args.action == 'check':
        with tempfile.TemporaryDirectory(prefix='oe-restore-check-') as temp:
            backup(args.data_dir, Path(temp) / 'backup')
            state = restore(Path(temp) / 'backup', Path(temp) / 'restored')
            print(json.dumps({'status': 'passed', 'restored_state': state}, indent=2))
    elif not args.destination:
        parser.error('--destination is required for backup or restore')
    else:
        operation = backup if args.action == 'backup' else restore
        operation(args.data_dir, args.destination)
        print(f'{args.action} verified: {args.destination}')


if __name__ == '__main__':
    main()
