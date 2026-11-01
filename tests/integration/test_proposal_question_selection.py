"""Generation focus cannot remove the frozen scope's mandatory checks."""
import json
from uuid import uuid4

import pytest

from tests.integration.test_workflow import client as workflow_client, job, project

client = workflow_client


def model_spy(client, monkeypatch):
    studio = client.app.state.studio
    studio.settings.model_url, studio.settings.model_name = 'http://localhost:11434', 'fixture-model'
    contexts = []

    def generate(_self, system, context, schema):
        contexts.append(context)
        return schema.model_validate({'summary': 'Declare the source-backed service class', 'changes': [{
            'operation': 'add', 'triple': {'subject': 'https://example.org/oe-demo/Service',
            'predicate': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type',
            'object': 'http://www.w3.org/2002/07/owl#Class'},
            'evidence_ids': [context['evidence'][0]['id']],
            'rationale': 'The source describes services'}]}), {}

    monkeypatch.setattr('oe_studio.model.ModelClient.generate', generate)
    return contexts


@pytest.mark.parametrize('select_subset', [False, True])
def test_question_focus_reaches_model_without_removing_scope_checks(client, monkeypatch, select_subset):
    p = project(client)
    contexts = model_spy(client, monkeypatch)
    questions = p['competency_questions']
    selected = [questions[-1]['id']] if select_subset else []
    result = job(client, p['id'], 'proposal', {'instruction': 'Focus the requested question',
                 'competency_question_ids': selected})
    expected = [questions[-1]] if select_subset else questions
    assert contexts[0]['competency_questions'] == expected
    revision = client.get(f"/api/v1/projects/{p['id']}/proposals/{result['proposal_id']}/revisions/1").json()
    studio = client.app.state.studio
    frozen_questions = json.loads(studio.artifacts.get_verified(revision['manifest']['questions']))
    frozen_tests = json.loads(studio.artifacts.get_verified(revision['manifest']['tests']))
    assert frozen_questions == questions
    assert {test['test_id'] for test in frozen_tests} == {q['id'] for q in questions}
    with studio.db.session() as session:
        generations = studio.items(session, p['id'], 'generation')
        assert generations[-1].data['context']['competency_questions'] == expected
    assert project(client)['approved_version_id'] is None


@pytest.mark.parametrize('use_model', [False, True])
@pytest.mark.parametrize('invalid', ['unknown', 'duplicate'])
def test_invalid_question_selection_fails_before_generation_or_candidate_writes(client, monkeypatch, use_model, invalid):
    p = project(client)
    contexts = model_spy(client, monkeypatch) if use_model else []
    question_id = p['competency_questions'][0]['id']
    selected = ['outside-frozen-scope'] if invalid == 'unknown' else [question_id, question_id]
    response = client.post(f"/api/v1/projects/{p['id']}/proposal-jobs", json={
        'instruction': 'Try an invalid selection', 'competency_question_ids': selected},
        headers={'Idempotency-Key': str(uuid4())})
    assert response.status_code == 202
    result = client.get('/api/v1/jobs/' + response.json()['job_id']).json()
    assert result['status'] == 'failed', result
    assert 'question' in result['error'].lower()
    assert contexts == []
    root = f"/api/v1/projects/{p['id']}"
    assert client.get(root + '/proposals').json()['items'] == []
    with client.app.state.studio.db.session() as session:
        assert client.app.state.studio.items(session, p['id'], 'generation') == []
    assert project(client)['approved_version_id'] is None
