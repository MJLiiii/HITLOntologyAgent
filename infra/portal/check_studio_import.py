"""Opt-in real provider/engines lifecycle in a new isolated synthetic Studio store.

Decisions are explicitly simulated engineering inputs. No study or main Studio
state is touched. Keep output: it contains immutable receipts, private operator
configuration (0600), and the isolated store for subsequent browser verification.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4

from trustgraph.api import ConfigValue

from check_pipeline import TEXT, write
from check_selected_import import capture_configuration
from init_pipeline import BASE, api

RATIONALE = 'SIMULATED ENGINEERING TEST: isolated seeded provider import; not a human study or actual expert decision.'


def main(output, flow_id):
    if output.exists():
        raise ValueError('Choose a fresh output directory; never overwrite prior attempt evidence')
    output.mkdir(parents=True)
    data = output.resolve() / 'studio'
    os.environ['OE_DATA_DIR'] = str(data)
    from fastapi.testclient import TestClient
    from oe_studio.main import create_app
    from oe_studio.settings import Settings
    from oe_studio.integrations.trustgraph.imports import configuration_digest
    from oe_studio.integrations.trustgraph.seed import project_seed_ontology
    application = create_app(Settings(llm_config_file=None, data_dir=data, database_url='', eager_jobs=True,
        service_token='', trustgraph_config_file=None))
    provider = api()
    if flow_id in provider.flow().list():
        raise ValueError('Choose a new synthetic flow; never silently repeat a prior ingestion')
    write(output / 'authority.json', {'kind': 'synthetic_engineering', 'simulated_decisions': True,
        'study_observations': False, 'main_studio_modified': False, 'rationale': RATIONALE})
    with TestClient(application) as client:
        assert client.get('/api/v1/session', headers={'X-OE-Session-Token': application.state.bootstrap_token}).status_code == 200
        project = client.get('/api/v1/projects').json()['items'][0]
        root = '/api/v1/projects/' + project['id']
        def post(path, body, status=202, headers=None):
            response = client.post(root + path, json=body, headers=headers or {'Idempotency-Key': str(uuid4())})
            assert response.status_code == status, response.text
            return response.json()
        def job(path, body, *, success=True):
            handle = post(path, body)
            result = client.get(handle['status_url']).json()
            write(output / ('job-' + result['id'] + '.json'), result)
            if success:
                assert result['status'] == 'succeeded', result.get('error')
            return result
        candidate = job('/proposal-jobs', {'corpus_snapshot_id': project['corpus_snapshot_id'], 'instruction': RATIONALE})['result']
        revision = client.get(root + f"/proposals/{candidate['proposal_id']}/revisions/1").json()
        bundle = {'proposal_id': revision['id'], 'revision': 1, 'bundle_digest': revision['bundle_digest']}
        validation = job('/validation-jobs', bundle)['result']
        assessment = job('/assessment-jobs', bundle)['result']
        assert validation['status'] == 'passed' and assessment['status'] == 'completed'
        post('/scope-decisions', {'scope_digest': project['scope_digest'], 'decision': 'accept', 'rationale': RATIONALE}, 201)
        submission = {'proposal_id': revision['id'], 'revision': 1, 'validation_run_id': validation['id'],
                      'required_assessment_run_ids': [assessment['id']]}
        post('/review-submissions', submission, 201, {'If-Match': '1'})
        review = post('/reviews', {**submission, 'bundle_digest': revision['bundle_digest'], 'decision': 'accept',
            'rationale': RATIONALE, 'review_policy_id': project['review_policy_id']}, 201)
        publication = post('/publications', {**bundle, 'approval_ids': [review['id']], 'expected_head': None})
        assert publication['status'] == 'completed', publication
        write(output / 'simulated-publication.json', publication)
        studio = application.state.studio
        with studio.db.session() as session:
            version = studio.get(session, project['id'], publication['new_version_id'], 'version')
            seed = version.data['ontology']
        original = json.loads((BASE / 'pipeline-config-v4.json').read_text())
        blueprint = copy.deepcopy(original['blueprints']['oe-ontology-v4'])
        provider.config().put([
            ConfigValue(type='flow-blueprint', key=flow_id, value=json.dumps(blueprint)),
            ConfigValue(type='ontology', key='oe-synthetic-ownership', value=json.dumps(project_seed_ontology(studio.artifacts.get_verified(seed)))),
            ConfigValue(type='collection', key=flow_id, value=json.dumps({'collection': flow_id, 'name': flow_id, 'tags': ['synthetic']})),
        ])
        params = {'llm-model': 'oe-qwen3-smoke:1.7b', 'llm-rag-model': 'oe-qwen3-smoke:1.7b', 'llm-temperature': '0',
                  'llm-rag-temperature': '0', 'embeddings-model': 'all-minilm:latest', 'reranker-model': 'ms-marco-TinyBERT-L-2-v2',
                  'chunk-size': '2000', 'chunk-overlap': '0'}
        provider.flow().start(flow_id, flow_id, RATIONALE, parameters=params)
        configuration = capture_configuration(provider, flow_id)
        binding = {'project_id': project['id'], 'url': 'http://127.0.0.1:18888', 'workspace': 'default',
            'flow': flow_id, 'collection': flow_id, 'seed_digest': seed['sha256'],
            'config_digest': configuration_digest(configuration), 'token': provider.token, 'timeout': 60}
        private = output.resolve() / 'provider-private.json'
        with open(private, 'x', opener=lambda path, flags: os.open(path, flags, 0o600)) as stream:
            json.dump({'projects': [{'binding': binding, 'seed_mode': 'approved_ontology', 'expected_configuration': configuration}]}, stream)
        studio.settings.trustgraph_config_file = private
        response = client.post(root + '/documents', files={'file': ('atlas.txt', TEXT.encode(), 'text/plain')},
            data={'title': 'Synthetic Atlas ownership', 'classification': 'synthetic'})
        assert response.status_code == 201, response.text
        document = response.json()
        before = subprocess.check_output(['git', f'--git-dir={data / "ontology.git"}', 'show-ref']).decode()
        receipt = job('/trustgraph-ingestions', {'document_id': document['id']})['result']
        assert receipt['status'] == 'queued' and receipt['upstream_completion_supported'] is False
        recovered = job('/trustgraph-ingestion-recoveries', {'preparation_id': receipt['preparation_id']})['result']
        assert recovered['id'] == receipt['id']
        deadline = time.monotonic() + 120
        while True:
            hints = client.get(root + '/trustgraph-ingestions/' + receipt['id'] + '/chunks')
            assert hints.status_code == 200, hints.text
            write(output / 'chunk-hints.json', hints.json())
            if hints.json()['chunk_uris']:
                selected = job('/trustgraph-snapshots', {'ingestion_run_id': receipt['id'], 'chunk_uris': hints.json()['chunk_uris']}, success=False)
                if selected['status'] == 'succeeded':
                    break
                assert 'required_extraction_stage_evidence_missing' in selected.get('error', ''), selected.get('error')
            assert time.monotonic() < deadline, 'No verifiable selected extraction within the observation deadline'
            time.sleep(2)
        evidence = client.get(root + '/corpus-evidence').json()['items']
        assert len(evidence) == 1 and evidence[0]['resolved'] and evidence[0]['quote'] == TEXT
        answer = job('/question-jobs', {'question': 'Which team owns the Atlas service?', 'corpus_snapshot_id': selected['result']['id']})['result']
        assert answer['evidence'] and all(row['resolved'] for row in answer['evidence'])
        assert any(row['id'] == evidence[0]['id'] for row in answer['evidence'])
        assert TEXT in answer['answer']
        after = subprocess.check_output(['git', f'--git-dir={data / "ontology.git"}', 'show-ref']).decode()
        assert before == after
        current = client.get('/api/v1/projects').json()['items'][0]
        assert current['approved_version_id'] == publication['new_version_id']
        write(output / 'evidence.json', evidence)
        write(output / 'question.json', answer)
        report = {'status': 'passed', 'authority': RATIONALE, 'project_id': project['id'],
            'flow_id': flow_id, 'data_dir': str(data), 'private_config_path': str(private),
            'seed_version_id': publication['new_version_id'], 'seed_sha256': seed['sha256'],
            'validation_engine': validation['engine'], 'assessment_engine': assessment.get('engine'),
            'queued_receipt_id': receipt['id'], 'recovery_reattached_same_receipt': True,
            'selected_corpus_id': selected['result']['id'], 'exact_passage_resolved': True,
            'question_reads_imported_passage': True, 'canonical_git_refs_unchanged_by_import': before == after,
            'upstream_global_completion': False, 'external_model_answer_quality_claimed': False}
        write(output / 'report.json', report)
        print(json.dumps(report, indent=2))


def resume_read(output):
    """Finish only local reads of a retained import; never enqueue or alter config."""
    data = output.resolve() / 'studio'
    os.environ['OE_DATA_DIR'] = str(data)
    from fastapi.testclient import TestClient
    from oe_studio.main import create_app
    from oe_studio.settings import Settings
    publication = json.loads((output / 'simulated-publication.json').read_text())
    jobs = [json.loads(path.read_text()) for path in output.glob('job-*.json')]
    results = [job['result'] for job in jobs if job['status'] == 'succeeded']
    receipts = [row for row in results if 'receipt' in row]
    assert len(receipts) >= 2 and len({row['id'] for row in receipts}) == 1
    application = create_app(Settings(llm_config_file=None, data_dir=data, database_url='', eager_jobs=True,
        service_token='', trustgraph_config_file=None))
    with TestClient(application) as client:
        assert client.get('/api/v1/session', headers={'X-OE-Session-Token': application.state.bootstrap_token}).status_code == 200
        project = client.get('/api/v1/projects').json()['items'][0]
        root = '/api/v1/projects/' + project['id']
        assert project['approved_version_id'] == publication['new_version_id']
        with application.state.studio.db.session() as session:
            corpus = application.state.studio.get(session, project['id'], project['corpus_snapshot_id'], 'corpus')
            assert corpus.status == 'frozen' and corpus.data['provider'] == 'trustgraph'
            seed = application.state.studio.get(session, project['id'], project['approved_version_id'], 'version').data['ontology']
        evidence = client.get(root + '/corpus-evidence').json()['items']
        assert len(evidence) == 1 and evidence[0]['resolved'] and evidence[0]['quote'] == TEXT
        response = client.post(root + '/question-jobs', json={'question': 'Which team owns the Atlas service?',
            'corpus_snapshot_id': project['corpus_snapshot_id']}, headers={'Idempotency-Key': str(uuid4())})
        assert response.status_code == 202, response.text
        result = client.get(response.json()['status_url']).json()
        write(output / ('job-' + result['id'] + '.json'), result)
        assert result['status'] == 'succeeded', result
        answer = result['result']
        assert answer['corpus_snapshot_id'] == project['corpus_snapshot_id']
        assert any(row['id'] == evidence[0]['id'] and row['resolved'] for row in answer['evidence'])
        assert TEXT in answer['answer']
        refs = subprocess.check_output(['git', f'--git-dir={data / "ontology.git"}', 'show-ref']).decode().splitlines()
        assert refs and all(row.split()[0] == publication['commit'] for row in refs)
        validation = next(row for row in results if 'stages' in row and 'bundle_digest' in row)
        assessment = next(row for row in results if 'strict_fitness' in row)
        report = {'status': 'passed', 'authority': RATIONALE, 'project_id': project['id'],
            'data_dir': str(data), 'private_config_path': str(output.resolve() / 'provider-private.json'),
            'seed_version_id': project['approved_version_id'], 'seed_sha256': seed['sha256'],
            'validation_engine': validation['engine'], 'assessment_engine': assessment.get('engine'),
            'queued_receipt_id': receipts[0]['id'], 'recovery_reattached_same_receipt': True,
            'selected_corpus_id': project['corpus_snapshot_id'], 'exact_passage_resolved': True,
            'question_reads_imported_passage': True, 'canonical_git_refs_match_simulated_publication': True,
            'upstream_global_completion': False, 'external_model_answer_quality_claimed': False,
            'resumed_local_reads_only': True, 'remote_provider_not_required_for_read': True}
        write(output / 'evidence.json', evidence)
        write(output / 'question.json', answer)
        write(output / 'report.json', report)
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--flow-id', default='oe-studio-ledger-v1')
    parser.add_argument('--resume-read', action='store_true')
    args = parser.parse_args()
    resume_read(args.output) if args.resume_read else main(args.output, args.flow_id)
