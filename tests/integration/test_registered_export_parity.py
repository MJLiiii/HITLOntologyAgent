"""Persisted task/phase/export parity; model/engine doubles, never study observations."""
from tests.llm_fixtures import configure_studio_model
import csv
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3

from tests.integration.test_task_registration import registration
from tests.integration.test_workflow import client as workflow_client, job
from oe_studio.experiments import verify_record

client = workflow_client


def test_registered_tasks_keep_all_outcomes_and_d_phases_in_list_and_exports(client, monkeypatch):
    p, _, request, first = registration(client)
    root, studio = f"/api/v1/projects/{p['id']}", client.app.state.studio
    second_response = client.post(root + '/synthetic-tasks', json={**request, 'task_id': 'synthetic-missing-outcomes'})
    assert second_response.status_code == 201, second_response.text
    second = second_response.json()
    configure_studio_model(studio, monkeypatch)
    monkeypatch.setattr('oe_studio.model.ModelClient.generate', lambda self, system, context, schema: (
        schema.model_validate({'summary': 'SIMULATED ENGINEERING TEST: preserve frozen candidate', 'changes': []}),
        {'provider': 'scripted-test-double', 'elapsed_seconds': .01}))
    monkeypatch.setattr('oe_studio.experiments.validate', lambda ttl, **kw: {
        'status': 'passed', 'engine': 'scripted-test-double', 'profile': 'rdfs',
        'cases': [{'id': t['test_id'], 'status': 'passed', 'expected': t['expected'], 'actual': t['expected']}
                  for t in kw['tests']]})
    monkeypatch.setattr('oe_studio.experiments.assess', lambda ttl, **kw: {
        'status': 'completed', 'engine': {'name': 'scripted-test-double'}, 'vocabulary_coverage': 1,
        'vocabulary_utilisation': .5, 'strict_fitness': .75, 'approximate_fitness': .75})

    def run(task):
        return job(client, p['id'], 'synthetic-task', {'registration_id': task['id'],
            'registration_digest': task['registration_digest'], 'condition': 'all', 'replicate_ids': [1]})['runs']

    successful = run(first)
    d = next(row for row in successful if row['condition'] == 'D')
    staged = client.post(root + f"/experiments/{d['id']}/proposal")
    assert staged.status_code == 201, staged.text
    revision = staged.json()
    bundle = {'proposal_id': revision['id'], 'revision': 1, 'bundle_digest': revision['bundle_digest']}
    validation = job(client, p['id'], 'validation', bundle)
    assessment = job(client, p['id'], 'assessment', bundle)
    submission = {'proposal_id': revision['id'], 'revision': 1, 'validation_run_id': validation['id'],
                  'required_assessment_run_ids': [assessment['id']]}
    assert client.post(root + '/review-submissions', json=submission, headers={'If-Match': '1'}).status_code == 201
    reviewed = client.post(root + '/reviews', json={**submission, 'bundle_digest': revision['bundle_digest'],
        'decision': 'request_changes', 'rationale': 'SIMULATED ENGINEERING TEST: parity fixture, not an expert observation',
        'review_policy_id': p['review_policy_id']})
    assert reviewed.status_code == 201, reviewed.text
    linked = client.post(root + f"/experiments/{d['id']}/review-results", json={'review_id': reviewed.json()['id']})
    assert linked.status_code == 201, linked.text
    post = linked.json()
    assert post['phase'] == 'post_review' and post['parent_run_id'] == d['id']
    assert post['correction_seconds'] is None and post['time_to_acceptance_right_censored']

    def unavailable(*args, **kwargs):
        raise ValueError('SIMULATED ENGINEERING TEST: model unavailable for missing-outcome fixture')

    monkeypatch.setattr('oe_studio.model.ModelClient.generate', unavailable)
    missing = run(second)
    assert len(missing) == 4 and all(row['status'] == 'generation_error' for row in missing)
    expected = {row['id']: row for row in [*successful, post, *missing]}

    listed, cursor = [], None
    while True:
        page = client.get(root + '/experiments', params={'limit': 2, **({'cursor': cursor} if cursor else {})}).json()
        listed.extend(page['items'])
        cursor = page['next_cursor']
        if cursor is None:
            break
    assert len(listed) == len(expected) == 9
    assert {row['id'] for row in listed} == set(expected)
    exported = client.get(root + '/experiments/export', params={'format': 'json'})
    csv_export = client.get(root + '/experiments/export', params={'format': 'csv'})
    assert exported.status_code == csv_export.status_code == 200
    assert exported.json()['schema_version'] == 2
    json_rows = exported.json()['items']
    provenance = exported.json()['provenance']
    csv_rows = list(csv.DictReader(io.StringIO(csv_export.text)))
    assert {row['id'] for row in json_rows} == {row['id'] for row in csv_rows} == set(expected)
    assert set(provenance) == set(expected)
    listed_by_id = {row['id']: row for row in listed}
    with studio.db.session() as session:
        for row in json_rows:
            sealed = studio.experiment_record(studio.get(session, p['id'], row['id'], 'experiment'))
            assert row == sealed
            verify_record(row)
            # Typed HTTP serialization must preserve the sealed packet's bytes/values.
            # List-only provenance fields are outside that packet's digest.
            listed_packet = {key: listed_by_id[row['id']][key] for key in sealed}
            verify_record(listed_packet)
            assert listed_packet == sealed
            returned_packet = {key: expected[row['id']][key] for key in sealed}
            verify_record(returned_packet)
            assert returned_packet == sealed
            assert provenance[row['id']]['stored_at'] == listed_by_id[row['id']]['stored_at']
            assert provenance[row['id']]['sealed_record'] == listed_by_id[row['id']]['sealed_record']
            assert provenance[row['id']]['project_context'] == listed_by_id[row['id']]['project_context']
    for row in [*listed, *json_rows]:
        original = expected[row['id']]
        for key in ('task_id', 'phase', 'condition', 'status', 'record_digest', 'strict_fitness', 'correction_seconds'):
            assert row[key] == original[key]
    for row in csv_rows:
        original = expected[row['id']]
        assert row['task_id'] == original['task_id'] and row['phase'] == original['phase']
        assert row['status'] == original['status'] and row['record_digest'] == original['record_digest']
        assert row['strict_fitness'] == ('' if original['strict_fitness'] is None else str(original['strict_fitness']))
        assert row['correction_seconds'] == ''
        sealed = next(item for item in json_rows if item['id'] == row['id'])
        for key, value in sealed.items():
            expected_cell = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else '' if value is None else str(value)
            assert row[key] == expected_cell
    assert client.get(root + '/experiments/export', params={'format': 'json'}).content == exported.content
    assert client.get(root + '/experiments/export', params={'format': 'csv'}).content == csv_export.content
    assert client.get(root).json()['approved_version_id'] is None
    assert studio.git.head(p['id']) is None

    # An opt-in, ignored copy feeds the actual-browser acceptance check. CI creates no artifact.
    if output := os.environ.get('OE_DASHBOARD_PARITY_OUTPUT'):
        destination = Path(output)
        destination.mkdir(parents=True, exist_ok=False)
        data = destination / 'studio'
        shutil.copytree(studio.settings.data_dir, data, ignore=shutil.ignore_patterns('studio.sqlite*'))
        with sqlite3.connect(studio.settings.data_dir / 'studio.sqlite') as source, sqlite3.connect(data / 'studio.sqlite') as target:
            source.backup(target)
        (destination / 'runs.json').write_bytes(exported.content)
        (destination / 'runs.csv').write_bytes(csv_export.content)
        (destination / 'browser-expectations.json').write_text(json.dumps({
            'classification': 'synthetic_engineering_test', 'real_study_approved': False,
            'model_and_engine_execution': 'explicit test doubles; parity only', 'project_id': p['id'],
            'total_records': 9, 'task_one': {'task_id': first['task_id'], 'records': 5, 'automated': 3,
                'pre_review': 1, 'post_review': 1, 'strict_fitness': .75, 'vocabulary_coverage': 1},
            'task_two': {'task_id': second['task_id'], 'records': 4, 'status': 'generation_error',
                'strict_fitness': None, 'vocabulary_coverage': None}, 'approved_version_id': None}, indent=2) + '\n')
