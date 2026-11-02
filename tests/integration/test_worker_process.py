"""Actual isolated worker processes use synthetic stores and no configured model."""
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest
from sqlalchemy import select

from oe_studio.db import Item, Job, Project
from oe_studio.settings import Settings
from oe_studio.workflow import Studio

ACTOR = {'kind': 'service', 'subject': 'process-fixture', 'roles': ['researcher']}
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def process_store(tmp_path):
    empty_env = tmp_path / 'worker.env'
    empty_env.write_text('')
    settings = Settings(_env_file=empty_env, data_dir=tmp_path / 'store', model_url='', model_name='',
                        llm_config_file=None, eager_jobs=False)
    studio = Studio(settings)
    with studio.db.session() as session:
        project = session.scalar(select(Project))
    environment = {key: value for key, value in os.environ.items() if not key.startswith('OE_')}
    environment.update(OE_DATA_DIR=str(settings.data_dir), PYTHONPATH=str(ROOT / 'services/api/src'))
    command = [sys.executable, '-m', 'oe_studio.worker', '--env-file', str(empty_env), '--poll-seconds', '0.05']
    return studio, project, environment, command


def queued_proposal(store, key='proposal'):
    studio, project, _, _ = store
    return studio.create_job(project.id, 'proposal', {'instruction': 'Create the synthetic source-grounded ontology',
                              'corpus_snapshot_id': project.corpus_snapshot_id}, key, ACTOR)['job_id']


def snapshot(studio, job_id):
    with studio.db.session() as session:
        job = session.get(Job, job_id)
        return job.status, job.attempt, job.result, job.error


def await_condition(check, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.03)
    raise AssertionError('Worker process did not reach the expected state')


def test_separate_worker_executes_queued_demo_job_once(process_store):
    studio, _, environment, command = process_store
    job_id = queued_proposal(process_store)
    assert snapshot(studio, job_id)[:2] == ('queued', 0)
    subprocess.run([*command, '--once'], env=environment, cwd=ROOT, check=True, capture_output=True, timeout=20)
    status, attempt, result, error = snapshot(studio, job_id)
    assert (status, attempt, error) == ('succeeded', 1, None)
    with studio.db.session() as session:
        assert session.get(Item, result['proposal_id']).data['origin'] == 'demo_generator'
    subprocess.run([*command, '--once'], env=environment, cwd=ROOT, check=True, capture_output=True, timeout=20)
    assert snapshot(studio, job_id) == (status, attempt, result, error)


def test_two_worker_processes_cannot_duplicate_claim(process_store):
    studio, project, environment, command = process_store
    job_id = queued_proposal(process_store)
    children = [subprocess.Popen([*command, '--once'], env=environment, cwd=ROOT,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
    try:
        for child in children:
            _, stderr = child.communicate(timeout=20)
            assert child.returncode == 0, stderr.decode()
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
    assert snapshot(studio, job_id)[:2] == ('succeeded', 1)
    with studio.db.session() as session:
        proposals = list(session.scalars(select(Item).where(Item.project_id == project.id, Item.kind == 'proposal')))
        assert len(proposals) == 1


@pytest.mark.parametrize('shutdown_signal', [signal.SIGTERM, signal.SIGINT])
def test_idle_worker_shuts_down_cleanly(process_store, tmp_path, shutdown_signal):
    _, _, environment, command = process_store
    log = tmp_path / 'worker.log'
    with log.open('w') as output:
        child = subprocess.Popen(command, env=environment, cwd=ROOT, stdout=output, stderr=output)
        try:
            await_condition(lambda: 'Worker started' in log.read_text())
            child.send_signal(shutdown_signal)
            assert child.wait(timeout=10) == 0, log.read_text()
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)


def test_killed_worker_lease_fails_without_replaying_uncertain_call(process_store, tmp_path):
    studio, project, environment, command = process_store
    job_id = queued_proposal(process_store)
    marker = tmp_path / 'entered-call'
    # Block exactly after the durable claim and before the synthetic proposal's effect.
    # This process-local substitute models an interrupted provider call without a network call.
    child_code = '''
import sys, time
from pathlib import Path
from oe_studio.workflow import Studio
from oe_studio.worker import main
def blocked(self, *args, **kwargs):
    Path(sys.argv[1]).write_text('entered')
    time.sleep(120)
Studio.create_proposal = blocked
main(['--env-file', sys.argv[2], '--once'])
'''
    child = subprocess.Popen([sys.executable, '-c', child_code, str(marker), command[4]],
                             env=environment, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        await_condition(marker.exists)
        assert snapshot(studio, job_id)[:2] == ('running', 1)
        child.kill()
        child.communicate(timeout=5)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
    with studio.db.session(write=True) as session:
        session.get(Job, job_id).lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    subprocess.run([*command, '--once'], env=environment, cwd=ROOT, check=True, capture_output=True, timeout=20)
    assert snapshot(studio, job_id)[:2] == ('failed', 1)
    assert 'lease expired' in snapshot(studio, job_id)[3]
    subprocess.run([*command, '--once'], env=environment, cwd=ROOT, check=True, capture_output=True, timeout=20)
    assert snapshot(studio, job_id)[:2] == ('failed', 1)
    with studio.db.session() as session:
        assert not list(session.scalars(select(Item).where(Item.project_id == project.id, Item.kind == 'proposal')))
