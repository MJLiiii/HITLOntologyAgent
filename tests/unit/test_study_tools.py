import pytest

from oe_studio import demo
from oe_studio.artifacts import canonical_json
from oe_studio.experiments import _seal, sha
from oe_studio.rdf import canonicalize, parse_ttl
from research.evaluator import EvaluatorIdentity, evaluate_frozen, private_mount
from research.study import allocate_explanation_arms, expert_time, paired_task_analysis


def test_rq3_allocation_preserves_displays_and_never_repeats_task_exposure():
    cases = [{'case_id': f'case-{i}', 'task_id': f'task-{i}',
              'source_packet_digest': 'a' * 64, 'assessment_digest': 'b' * 64} for i in range(6)]
    allocation = allocate_explanation_arms(cases, ['r1', 'r2', 'r3', 'r4'], seed=7,
                                           prior_exposures=[('r1', 'task-0')])
    assert allocation == allocate_explanation_arms(cases, ['r1', 'r2', 'r3', 'r4'], seed=7,
                                                   prior_exposures=[('r1', 'task-0')])
    pairs = {(a['reviewer_id'], a['task_id']) for a in allocation}
    assert len(pairs) == len(allocation) and ('r1', 'task-0') not in pairs
    for case in cases:
        arms = [a for a in allocation if a['case_id'] == case['case_id']]
        assert {a['arm'] for a in arms} == {'explanation_visible', 'explanation_hidden'}
        assert len({(a['source_packet_digest'], a['assessment_digest']) for a in arms}) == 1
    counts = [sum(a['reviewer_id'] == reviewer for a in allocation) for reviewer in ('r1', 'r2', 'r3', 'r4')]
    assert max(counts) - min(counts) <= 1


def test_rq3_replicates_do_not_allow_same_reviewer_to_see_same_task_twice():
    cases = [{'case_id': f'replicate-{i}', 'task_id': 'same-task',
              'source_packet_digest': 'a' * 64, 'assessment_digest': 'b' * 64} for i in (1, 2)]
    with pytest.raises(ValueError, match='unexposed'):
        allocate_explanation_arms(cases, ['r1', 'r2'], seed=1)


def event(action, second, reviewer='r1'):
    return {'task_id': 'task-1', 'condition': 'D', 'reviewer_id': reviewer,
            'event': action, 'time': f'2026-01-01T00:00:{second:02d}+00:00'}


def test_rq4_counts_inspection_and_rework_for_all_reviewers_and_censors_unsuccessful_case():
    events = [event('start', 0), event('pause', 10), event('start', 12, 'r2'),
              event('resume', 20), event('end', 25, 'r2')]
    result = expert_time(events, observation_end='2026-01-01T00:00:30Z', accepted=False,
                         acceptance_standard_digest='a' * 64)
    assert result['expert_active_seconds'] == 33
    assert result['right_censored'] and result['time_to_acceptance_seconds'] is None
    assert result['censoring_duration_seconds'] == 33 and result['open_intervals_at_cutoff'] == 1
    ended = expert_time([*events, event('end', 30)], observation_end='2026-01-01T00:00:30Z',
                        accepted=True, acceptance_standard_digest='a' * 64)
    assert ended['time_to_acceptance_seconds'] == 33 and not ended['right_censored']


def test_rq4_no_ledger_is_missing_not_zero_and_invalid_transitions_fail():
    kwargs = dict(observation_end='2026-01-01T00:00:30Z', accepted=False, acceptance_standard_digest='a' * 64)
    assert expert_time([], **kwargs)['expert_active_seconds'] is None
    with pytest.raises(ValueError):
        expert_time([event('start', 0), event('start', 2)], **kwargs)
    with pytest.raises(ValueError, match='complete ended'):
        expert_time([event('start', 0)], **{**kwargs, 'accepted': True})


def test_paired_analysis_uses_tasks_not_replicates_and_retains_missing_task_pairs():
    records = []
    for task, b, c in [('t1', [0., 1.], [1., 1.]), ('t2', [.5, .5], [0., 0.])]:
        for condition, values in [('B', b), ('C', c)]:
            for replicate, value in enumerate(values, 1):
                records.append({'task_id': task, 'condition': condition, 'replicate': replicate,
                                'metrics': {'accuracy': {'value': value}}})
    result = paired_task_analysis(records, task_ids=['t1', 't2', 't3'], replicate_ids=[1, 2], metric='accuracy')
    assert result['scheduled_tasks'] == 3 and result['complete_task_pairs'] == 2
    assert result['mean_paired_difference'] == 0 and result['resampling_unit'] == 'task'
    assert [r['paired_difference'] for r in result['tasks']] == [.5, -.5, None]
    assert result['tasks'][2]['missing_replicates'] == {'B': [1, 2], 'C': [1, 2]}
    assert result['inferential_claim'] is None
    with pytest.raises(ValueError, match='Duplicate logical'):
        paired_task_analysis([*records, records[0]], task_ids=['t1', 't2'], replicate_ids=[1, 2], metric='accuracy')


@pytest.fixture
def evaluator_mounts(tmp_path):
    inputs, outputs, app = (tmp_path / name for name in ('evaluator-input', 'evaluator-output', 'app'))
    for path in (inputs, outputs, app):
        path.mkdir(mode=0o700)
    credential = b'x' * 32
    (inputs / '.evaluator.key').write_bytes(credential)
    (inputs / '.evaluator.key').chmod(0o600)
    candidate = canonicalize(parse_ttl(demo.ONTOLOGY))
    row = _seal({'id': 'a-run', 'task_id': 'task-1', 'condition': 'A', 'replicate': 1,
                 'candidate_ttl': candidate, 'candidate_digest': sha(candidate)})
    rows = canonical_json([row])
    (inputs / 'frozen-outputs.json').write_bytes(rows)
    packet = {'split': 'held_out', 'base_ontology': candidate, 'shapes_ttl': '',
              'tests': [{'test_id': 'evaluator-only-sentinel', 'kind': 'ask', 'query': 'ASK {}', 'expected': True}],
              'questions': [{'id': 'independent-question', 'question': 'Reserved evaluator fixture?',
                             'sparql_query': 'ASK {}'}]}
    packet_bytes = canonical_json(packet)
    (inputs / 'packet.json').write_bytes(packet_bytes)
    manifest = {'schema_version': 1, 'protocol_id': 'contract-test-only', 'split': 'held_out',
                'evaluator_subject': 'test-evaluator',
                'outputs': {'path': 'frozen-outputs.json', 'sha256': sha(rows)},
                'task_packets': {'task-1': {'path': 'packet.json', 'sha256': sha(packet_bytes)}},
                'schedule': [{'task_id': 'task-1', 'condition': arm, 'replicate': 1} for arm in 'AB']}
    (inputs / 'manifest.json').write_bytes(canonical_json(manifest))
    return inputs, outputs, app, EvaluatorIdentity('test-evaluator', 'evaluator', credential), manifest


def execute(mounts, **kwargs):
    inputs, outputs, app, identity, _ = mounts
    return evaluate_frozen(inputs, outputs, identity, forbidden_roots=[app], **kwargs)


def test_evaluator_freezes_identical_workload_and_retains_missing_scheduled_run(evaluator_mounts):
    calls = []
    def validate(candidate, **kwargs):
        calls.append(kwargs)
        return {'status': 'passed', 'cases': [{'id': 'evaluator-only-sentinel', 'status': 'passed',
                                              'actual': True, 'expected': True}]}
    def assess(candidate, **kwargs):
        calls.append(kwargs)
        return {'status': 'completed', 'vocabulary_coverage': 1.}
    report, path = execute(evaluator_mounts, validate_fn=validate, assess_fn=assess)
    a, b = report['results']
    assert a['held_out_packet_digest'] == b['held_out_packet_digest']
    assert a['metrics']['answer_accuracy_required']['value'] == 1
    assert b['frozen_run_id'] is None and b['case_counts']['error'] == b['case_counts']['scheduled'] == 1
    assert b['metrics']['answer_precision']['value'] is None
    assert report['study_claim'] is None and path.parent == evaluator_mounts[1]
    assert path.stat().st_mode & 0o777 == 0o600
    assert not list(evaluator_mounts[2].iterdir())
    assert len(calls) == 2


@pytest.mark.parametrize('kind,subject,credential', [('human', 'test-evaluator', b'x' * 32),
                                                    ('service', 'test-evaluator', b'x' * 32),
                                                    ('evaluator', 'other', b'x' * 32),
                                                    ('evaluator', 'test-evaluator', b'y' * 32)])
def test_evaluator_rejects_application_identities_and_wrong_credentials(evaluator_mounts, kind, subject, credential):
    inputs, outputs, app, _, _ = evaluator_mounts
    with pytest.raises(PermissionError):
        evaluate_frozen(inputs, outputs, EvaluatorIdentity(subject, kind, credential), forbidden_roots=[app])
    assert not list(outputs.iterdir())


def test_evaluator_rejects_shared_storage_permissions_path_escape_and_symlinks(evaluator_mounts):
    inputs, outputs, app, identity, manifest = evaluator_mounts
    with pytest.raises(PermissionError):
        private_mount(app, [app])
    inputs.chmod(0o755)
    with pytest.raises(PermissionError, match='0700'):
        execute(evaluator_mounts)
    inputs.chmod(0o700)
    manifest['task_packets']['task-1']['path'] = '../app/oracle.json'
    (inputs / 'manifest.json').write_bytes(canonical_json(manifest))
    with pytest.raises(PermissionError, match='inside'):
        execute(evaluator_mounts)
    manifest['task_packets']['task-1']['path'] = 'oracle-link.json'
    (inputs / 'oracle-link.json').symlink_to(inputs / 'packet.json')
    (inputs / 'manifest.json').write_bytes(canonical_json(manifest))
    with pytest.raises(PermissionError, match='Symlinked'):
        execute(evaluator_mounts)


def test_evaluator_rejects_changed_frozen_artifact(evaluator_mounts):
    inputs = evaluator_mounts[0]
    (inputs / 'packet.json').write_text('{}')
    with pytest.raises(ValueError, match='digest'):
        execute(evaluator_mounts)


def test_api_cannot_request_heldout_evaluation_or_real_study(tmp_path, monkeypatch):
    monkeypatch.setenv('OE_DATA_DIR', str(tmp_path / 'import-default'))
    from fastapi.testclient import TestClient
    from oe_studio.main import create_app
    from oe_studio.settings import Settings
    app = create_app(Settings(data_dir=tmp_path / 'app', eager_jobs=True))
    assert not any('held' in path or 'evaluator' in path for path in app.openapi()['paths'])
    with TestClient(app) as client:
        assert client.get('/api/v1/session', headers={'X-OE-Session-Token': app.state.bootstrap_token}).status_code == 200
        project = client.get('/api/v1/projects').json()['items'][0]['id']
        result = client.post(f'/api/v1/projects/{project}/assessment-jobs', json={
            'proposal_id': 'not-a-real-proposal', 'revision': 1, 'bundle_digest': 'a' * 64, 'split': 'held_out'},
            headers={'Idempotency-Key': 'forbidden-heldout-test'})
        assert result.status_code == 422
        result = client.post(f'/api/v1/projects/{project}/experiment-jobs', json={'protocol_id': 'real-study'},
                              headers={'Idempotency-Key': 'forbidden-study-test'})
        assert result.status_code == 422
