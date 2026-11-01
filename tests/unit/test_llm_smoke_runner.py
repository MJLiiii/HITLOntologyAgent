import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


SPEC = importlib.util.spec_from_file_location('check_llm_profiles', Path('scripts/check_llm_profiles.py'))
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def test_missing_key_reports_each_fixture_without_dispatch_or_budget(tmp_path):
    async def forbidden(*args, **kwargs):
        raise AssertionError('Missing credentials must prevent dispatch')
    profiles = [{'id': 'one', 'revision': 'rev', 'api_key_env': 'OPENCODE_API_KEY'},
                {'id': 'two', 'revision': 'rev', 'api_key_env': 'OPENCODE_API_KEY'}]
    results = asyncio.run(runner.compare_profiles(SimpleNamespace(), profiles, tmp_path / 'staged.sqlite',
                                                  complete_fn=forbidden, credential_fn=lambda *_: ''))
    assert len(results) == 4
    assert all(row['status'] == 'blocked_missing_credential' for row in results)
    assert {row['profile_id'] for row in results} == {'one', 'two'}
    assert len({row['fixture_sha256'] for row in results}) == 2


def test_identical_fixtures_validate_schema_grounding_and_retain_provider_failures(tmp_path):
    async def complete(settings, system, context, output_schema):
        if settings.resolved_llm_profile['id'] == 'failed':
            raise RuntimeError('sensitive key must never reach report')
        return json.dumps(({'answer': 'Operations Team owns Payroll Service.', 'evidence_ids': ['synthetic-source-1'], 'triple_indices': []} if 'question' in context else {'summary': 'Add supported ownership assertion', 'changes': [{'operation': 'add', 'triple': {'subject': 'https://example.org/oe-demo/PayrollService', 'predicate': 'https://example.org/oe-demo/hasOwner', 'object': 'https://example.org/oe-demo/OperationsTeam'}, 'evidence_ids': ['synthetic-source-1'], 'rationale': 'The synthetic source directly records ownership.'}]})), {
            'input_tokens': 25, 'output_tokens': 9, 'cost': None}
    profiles = [{'id': 'good', 'revision': 'rev', 'api_key_env': 'OPENCODE_API_KEY'},
                {'id': 'failed', 'revision': 'rev', 'api_key_env': 'OPENCODE_API_KEY'}]
    results = asyncio.run(runner.compare_profiles(SimpleNamespace(), profiles, tmp_path / 'staged.sqlite',
                                                  complete_fn=complete, credential_fn=lambda *_: 'private'))
    assert [row['status'] for row in results] == ['passed', 'passed', 'provider_error', 'provider_error']
    assert results[0]['fixture_sha256'] == results[2]['fixture_sha256']
    assert results[1]['fixture_sha256'] == results[3]['fixture_sha256']
    assert all('sensitive' not in json.dumps(row) for row in results)
    assert results[0]['schema_valid'] is True and results[0]['citation_valid'] is True
    assert results[0]['expected_facts_valid'] is True
    assert results[0]['usage'] == {'input_tokens': 25, 'output_tokens': 9, 'cost': None}


def test_schema_or_unsupported_answer_is_a_failed_observation(tmp_path):
    responses = iter([{'answer': 'Wrong answer', 'evidence_ids': ['invented'], 'triple_indices': []}, {'answer': 5}])
    async def complete(*args):
        return json.dumps(next(responses)), {}
    results = asyncio.run(runner.compare_profiles(
        SimpleNamespace(), [{'id': 'bad', 'revision': 'rev', 'api_key_env': 'KEY'}], tmp_path / 'staged.sqlite',
        complete_fn=complete, credential_fn=lambda *_: 'private'))
    assert results[0]['status'] == 'citation_failed'
    assert results[0]['schema_valid'] is True and results[0]['citation_valid'] is False
    assert results[0]['expected_facts_valid'] is False
    assert results[1]['status'] == 'schema_failed'


def test_cli_adapter_runs_real_studio_chat_and_proposal_with_no_approval(tmp_path, monkeypatch):
    from sqlalchemy import select
    from oe_studio.db import Item, Project
    from oe_studio.llm_profiles import Profile, _snapshot
    from oe_studio.model import GroundedAnswer, ProposalDraft, ModelClient
    from oe_studio.settings import Settings

    settings = Settings(data_dir=tmp_path / 'studio', _env_file=None)
    profiles = [_snapshot(Profile(id=name, provider='opencode_go', model='glm-5.3-flash',
                                 purposes=['chat', 'proposal'])) for name in ('first', 'second')]
    def generate(self, system, context, schema):
        source_id = context['evidence'][0]['id']
        if schema is GroundedAnswer:
            result = GroundedAnswer(answer='Operations Team owns Payroll Service.', evidence_ids=[source_id],
                                    triple_indices=[])
        else:
            result = ProposalDraft(summary='Add supported ownership assertion', changes=[{
                'operation': 'add', 'triple': {'subject': 'https://example.org/oe-demo/PayrollService',
                    'predicate': 'https://example.org/oe-demo/hasOwner',
                    'object': 'https://example.org/oe-demo/OperationsTeam'}, 'evidence_ids': [source_id],
                'rationale': 'The source records ownership.'}])
        return result, {'raw_output': result.model_dump_json(), 'input_tokens': 25, 'output_tokens': 9}
    monkeypatch.setattr(ModelClient, 'generate', generate)
    studio, complete, fixtures = runner.stage_studio(settings)
    results = asyncio.run(runner.compare_profiles(settings, profiles, tmp_path / 'fixtures.sqlite',
        complete_fn=complete, credential_fn=lambda *_: 'private', fixtures=fixtures))
    assert [row['status'] for row in results] == ['passed'] * 4
    with studio.db.session() as session:
        assert len(list(session.scalars(select(Item).where(Item.kind == 'generation')))) == 4
        assert len(list(session.scalars(select(Item).where(Item.kind == 'proposal')))) == 2
        assert not list(session.scalars(select(Item).where(Item.kind.in_(['review', 'publication']))))
        assert session.scalar(select(Project)).approved_version_id is None
    studio.db.engine.dispose()


def test_wrapped_provider_and_schema_failures_are_not_grounding_findings(tmp_path):
    from oe_studio.model import ModelGenerationError
    errors = iter([{'validation_errors': [], 'input_tokens': None},
                   {'validation_errors': [{'type': 'missing'}], 'input_tokens': 10, 'output_tokens': 3}])
    async def complete(*args):
        raise ModelGenerationError('do not copy raw exception messages', next(errors))
    results = asyncio.run(runner.compare_profiles(
        SimpleNamespace(), [{'id': 'bad', 'revision': 'rev', 'api_key_env': 'KEY'}], tmp_path / 'staged.sqlite',
        complete_fn=complete, credential_fn=lambda *_: 'private'))
    assert results[0]['status'] == 'provider_error'
    assert results[1]['status'] == 'schema_failed'
    assert results[1]['schema_valid'] is False
    assert results[1]['usage'] == {'input_tokens': 10, 'output_tokens': 3, 'cost': None}


def test_real_sdk_studio_comparison_reserves_each_fake_wire_dispatch(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone
    import httpx
    from oe_studio import model
    from oe_studio.llm_budget import budget_summary
    from oe_studio.llm_profiles import Profile, _snapshot
    from oe_studio.llm_runtime import complete
    from oe_studio.settings import Settings

    monkeypatch.setenv('OPENCODE_API_KEY', 'offline-only-placeholder')
    profiles = [_snapshot(Profile(id=name, provider='opencode_go', model=model_name,
                                 temperature=None, purposes=['chat', 'proposal']))
                for name, model_name in [('glm', 'glm-5.3-flash'), ('kimi', 'kimi-k2.7-code')]]
    prices = []
    for profile, tokens, input_rate, output_rate in [(profiles[0], 1000000, '0.15', '0.50'),
                                                    (profiles[1], 262144, '0.95', '4.00')]:
        prices.append({**{key: profile[key] for key in ('id', 'revision', 'provider', 'model', 'base_url')},
                       'input_usd_per_million': input_rate, 'output_usd_per_million': output_rate,
                       'source': 'https://opencode.ai/v2/docs/console/go/',
                       'input_bound': {'method': 'accepted_context_limit', 'tokens': tokens,
                                       'source': 'https://opencode.ai/inference/go/v1/models'}})
    now = datetime.now(timezone.utc)
    price_file = tmp_path / 'prices.json'
    price_file.write_text(json.dumps({'verified_at': now.isoformat(),
        'valid_until': (now + timedelta(hours=1)).isoformat(), 'profiles': prices}))
    settings = Settings(data_dir=tmp_path / 'studio', _env_file=None,
                        llm_smoke_budget_file=tmp_path / 'budget.sqlite', llm_smoke_price_file=price_file)
    def wire(request):
        payload = json.loads(request.content)
        context = json.loads(payload['messages'][1]['content'])
        source_id = context['evidence'][0]['id']
        if 'question' in context:
            result = {'answer': 'Operations Team owns Payroll Service.', 'evidence_ids': [source_id],
                      'triple_indices': [], 'unresolved_points': []}
        else:
            result = {'summary': 'Add ownership assertion', 'changes': [{'operation': 'add',
                      'triple': {'subject': 'https://example.org/oe-demo/PayrollService',
                                'predicate': 'https://example.org/oe-demo/hasOwner',
                                'object': 'https://example.org/oe-demo/OperationsTeam'},
                      'evidence_ids': [source_id], 'rationale': 'The source records ownership.'}]}
        return httpx.Response(200, json={'id': 'offline-completion', 'object': 'chat.completion',
            'created': 0, 'model': payload['model'],
            'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': json.dumps(result)},
                         'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 25, 'completion_tokens': 9, 'total_tokens': 34, 'cost': 0.0,
                      'opencode': {'billing_source': 'go', 'list_cost': 0.0001, 'allowance': 1000.0}}})
    async def wire_complete(settings, system, context, output_schema, **kwargs):
        return await complete(settings, system, context, output_schema, transport=httpx.MockTransport(wire))
    monkeypatch.setattr(model, 'complete', wire_complete)
    studio, adapter, fixtures = runner.stage_studio(settings)
    try:
        results = asyncio.run(runner.compare_profiles(settings, profiles, tmp_path / 'fixtures.sqlite',
            complete_fn=adapter, fixtures=fixtures))
        assert [row['status'] for row in results] == ['passed'] * 4
        assert all(row['usage']['input_tokens'] == 25 and row['usage']['output_tokens'] == 9 for row in results)
        assert all(row['returned_model'] in {'glm-5.3-flash', 'kimi-k2.7-code'} for row in results)
        assert all(row['model'] == row['configured_model'] and row['provider'] == 'opencode_go' for row in results)
        assert all(row['finish_reason'] == 'stop' and row['citation_valid'] and row['expected_facts_valid'] for row in results)
        assert all(row['usage_provenance'] == {'input_tokens': 'provider', 'output_tokens': 'provider', 'cost': 'provider'} for row in results)
        assert all(row['usage']['cost'] == 0 and row['cost_is_estimate'] is False and row['provider_list_cost'] == 0.0001 for row in results)
        assert budget_summary(settings.llm_smoke_budget_file) == {
            'attempts_reserved': 4, 'reserved_usd': '0.834937600', 'attempt_limit': 20, 'usd_limit': '1.00'}
    finally:
        studio.db.engine.dispose()


def test_profile_without_credential_reference_can_dispatch_local_fixture(tmp_path):
    async def complete(*args):
        raise RuntimeError('offline local-provider failure')
    def credential(*args):
        raise AssertionError('A local unauthenticated profile needs no credential lookup')
    rows = asyncio.run(runner.compare_profiles(
        SimpleNamespace(), [{'id': 'local', 'revision': 'rev', 'api_key_env': None}], tmp_path / 'staged.sqlite',
        complete_fn=complete, credential_fn=credential))
    assert [row['status'] for row in rows] == ['provider_error', 'provider_error']


def test_valid_citations_do_not_imply_expected_facts(tmp_path):
    responses = iter([
        {'answer': 'The Data Team owns Payroll Service.', 'evidence_ids': ['synthetic-source-1'], 'triple_indices': []},
        {'summary': 'Add a different ownership assertion', 'changes': [{'operation': 'add', 'triple': {
            'subject': 'https://example.org/oe-demo/PayrollService',
            'predicate': 'https://example.org/oe-demo/hasOwner',
            'object': 'https://example.org/oe-demo/DataTeam'}, 'evidence_ids': ['synthetic-source-1'],
            'rationale': 'This cites a real source but changes the expected relation.'}]},
    ])
    async def complete(*args):
        return json.dumps(next(responses)), {}
    rows = asyncio.run(runner.compare_profiles(
        SimpleNamespace(), [{'id': 'wrong', 'revision': 'rev', 'api_key_env': None}], tmp_path / 'staged.sqlite',
        complete_fn=complete))
    assert [row['status'] for row in rows] == ['expected_facts_failed', 'expected_facts_failed']
    assert all(row['schema_valid'] and row['citation_valid'] and not row['expected_facts_valid'] for row in rows)


def test_studio_citation_failure_retains_provider_identity_and_separate_flags(tmp_path, monkeypatch):
    from oe_studio.model import ModelClient, GroundedAnswer
    from oe_studio.llm_profiles import Profile, _snapshot
    from oe_studio.settings import Settings
    settings = Settings(data_dir=tmp_path / 'studio', _env_file=None)
    profile = _snapshot(Profile(id='bad-citation', provider='opencode_go', model='glm-5.3-flash',
                                purposes=['chat', 'proposal']))
    def generate(self, system, context, schema):
        result = GroundedAnswer(answer='Operations Team owns Payroll Service.', evidence_ids=['fabricated'],
                                triple_indices=[])
        return result, {'raw_output': result.model_dump_json(), 'provider': 'opencode_go',
                        'model': 'glm-5.3-flash', 'returned_model': 'wire-identity', 'finish_reason': 'stop',
                        'input_tokens': 25, 'output_tokens': 9}
    monkeypatch.setattr(ModelClient, 'generate', generate)
    studio, adapter, fixtures = runner.stage_studio(settings)
    try:
        rows = asyncio.run(runner.compare_profiles(settings, [profile], tmp_path / 'fixtures.sqlite',
            complete_fn=adapter, credential_fn=lambda *_: 'private', fixtures=fixtures[:1]))
        assert rows[0]['status'] == 'citation_failed'
        assert rows[0]['schema_valid'] is True and rows[0]['citation_valid'] is False
        assert rows[0]['expected_facts_valid'] is True
        assert rows[0]['returned_model'] == 'wire-identity'
        assert rows[0]['usage']['input_tokens'] == 25
    finally:
        studio.db.engine.dispose()
