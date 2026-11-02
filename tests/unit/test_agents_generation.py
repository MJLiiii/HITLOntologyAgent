"""Controlled clients verify agent boundaries without network/model calls."""
import pytest
from oe_studio.agents.test_generation import TestGenerationAgent, TestGenerationAgentInput
from oe_studio.agents.proposal import ProposalAgent, ProposalAgentInput
from oe_studio.model import ModelGenerationError

NS = 'https://example.org/oe-demo/'


class Client:
    def __init__(self, output):
        self.output = output
        self.calls = []

    def generate(self, system, context, schema):
        self.calls.append((system, context, schema))
        return schema.model_validate(self.output), {'provider': 'controlled', 'request_id': 'r1'}


def inputs(**values):
    return TestGenerationAgentInput(**dict(dict(bundle_digest='a' * 64,
        candidate_ttl=f'<{NS}Service> a <http://www.w3.org/2000/01/rdf-schema#Class> .',
        shapes_ttl='', fixtures_ttl='', questions=[{'id': 'Q1', 'sparql_query': f'ASK {{ ?s a <{NS}Service> }}'}],
        changes={}, evidence=[{'id': 'E1', 'resolved': True}]), **values))


def case(**values):
    return dict(dict(kind='ask', query=f'ASK {{ ?s a <{NS}Service> }}', expected=True,
                     rationale='Proposed service instance test', evidence_ids=['E1'], question_ids=['Q1'],
                     scenario='positive'), **values)


def test_pending_server_owned_oracle_and_exact_byte_hash():
    from oe_studio.testspecs import sha
    client = Client({'tests': [case()]})
    frozen = inputs()
    result = TestGenerationAgent(client).run(frozen)
    assert result.tests[0].oracle_status == 'needs_review'
    assert result.tests[0].timeout_seconds == 10
    assert result.tests[0].inference_mode == 'rdfs'
    assert result.tests[0].target_ontology_sha256 == sha(frozen.candidate_ttl)
    assert result.bundle_digest == frozen.bundle_digest


@pytest.mark.parametrize('override', [
    {'query': 'ASK { SERVICE <https://bad.example/> { ?s ?p ?o } }'},
    {'evidence_ids': ['invented']}, {'question_ids': ['held-out']}, {'change_ids': ['unknown']},
    {'fixtures_ttl': f'<{NS}existing> a <{NS}Service> .'},
    {'fixtures_ttl': f'<{NS}synthetic/{"a" * 64}/x> <http://www.w3.org/2002/07/owl#imports> <{NS}Service> .'},
])
def test_rejected_output_preserves_generation_record(override):
    with pytest.raises(ModelGenerationError) as error:
        TestGenerationAgent(Client({'tests': [case(**override)]})).run(inputs())
    assert error.value.record['request_id'] == 'r1'
    assert error.value.record['status'] == 'failed'
    assert error.value.record['output']


def test_admits_fresh_instance_fixture():
    fixture = f'<{NS}synthetic/{"a" * 64}/x> a <{NS}Service> .'
    assert TestGenerationAgent(Client({'tests': [case(fixtures_ttl=fixture)]})).run(inputs()).tests[0].fixtures_ttl == fixture


def test_bound_checked_before_call():
    client = Client({})
    with pytest.raises(ValueError, match='65536'):
        TestGenerationAgent(client).run(inputs(candidate_ttl=' ' * 65537))
    assert not client.calls


def test_model_cannot_set_approval_or_engine_settings():
    from oe_studio.agents.test_generation import TestSuiteDraft
    with pytest.raises(ValueError):
        TestSuiteDraft.model_validate({'tests': [case(oracle_status='accepted', timeout_seconds=300)]})


def test_model_failure_record_passes_through():
    class FailedClient:
        def generate(self, *args):
            raise ModelGenerationError('failed', {'request_id': 'failed1'})
    with pytest.raises(ModelGenerationError) as error:
        TestGenerationAgent(FailedClient()).run(inputs())
    assert error.value.record == {'request_id': 'failed1'}


def test_proposal_agent_checks_evidence_and_preserves_prompt():
    client = Client({'summary': 'A source grounded change', 'changes': [{'operation': 'add',
        'triple': {'subject': NS + 'Service', 'predicate': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type',
                   'object': 'http://www.w3.org/2000/01/rdf-schema#Class'},
        'evidence_ids': ['E1'], 'rationale': 'Source defines a service'}]})
    result = ProposalAgent(client).run(ProposalAgentInput(system_prompt='failed entailment only',
                         context={'evidence': [{'id': 'E1', 'resolved': True}]}))
    assert len(result.changes.additions) == 1
    assert client.calls[0][0] == 'failed entailment only'


def test_select_and_shacl_drafts_are_declarative():
    select = case(kind='select_rows', query=f'SELECT ?s WHERE {{ ?s a <{NS}Service> }}', expected=[])
    shacl = case(kind='shacl', query=None, expected=None, expected_conforms=True, expected_violations=[])
    result = TestGenerationAgent(Client({'tests': [select, shacl]})).run(inputs())
    assert [test.kind for test in result.tests] == ['select_rows', 'shacl']


def test_malformed_fixture_retains_model_record():
    with pytest.raises(ModelGenerationError) as error:
        TestGenerationAgent(Client({'tests': [case(fixtures_ttl='not turtle at all')]})).run(inputs())
    assert error.value.record['request_id'] == 'r1'


def test_maximum_cases_and_multibyte_fixture_bound():
    from oe_studio.agents.test_generation import TestSuiteDraft
    with pytest.raises(ValueError):
        TestSuiteDraft.model_validate({'tests': [case()] * 41})
    fixture = '#' + 'é' * 11000
    with pytest.raises(ModelGenerationError, match='20000'):
        TestGenerationAgent(Client({'tests': [case(fixtures_ttl=fixture)]})).run(inputs())


def test_exact_candidate_and_fixture_whitespace_is_preserved():
    from oe_studio.testspecs import sha
    frozen = inputs(candidate_ttl=inputs().candidate_ttl + '\n\n')
    fixture = f'\n<{NS}synthetic/{"a" * 64}/x> a <{NS}Service> .\n\n'
    result = TestGenerationAgent(Client({'tests': [case(fixtures_ttl=fixture)]})).run(frozen)
    assert result.tests[0].target_ontology_sha256 == sha(frozen.candidate_ttl)
    assert result.tests[0].fixtures_ttl == fixture
    assert result.tests[0].fixture_sha256 == sha(fixture)


def test_model_oracle_explanation_and_assumptions_remain_pending():
    result = TestGenerationAgent(Client({'tests': [case(assumptions=['Instance typing follows the source'],
                                  oracle_explanation='The frozen source defines a service class')]})).run(inputs())
    assert result.tests[0].assumptions == ['Instance typing follows the source']
    assert result.tests[0].oracle_source.startswith('Model-proposed expectation; human review required:')
    assert result.tests[0].oracle_status == 'needs_review'


def test_shacl_unknown_expected_signature_is_rejected():
    signature = {'focusNode': NS + 'invented', 'path': NS + 'unknown', 'sourceShape': NS + 'inventedShape',
                 'severity': 'http://www.w3.org/ns/shacl#Violation'}
    with pytest.raises(ModelGenerationError, match='SHACL expectation'):
        TestGenerationAgent(Client({'tests': [case(kind='shacl', query=None, expected=None,
            expected_conforms=False, expected_violations=[signature])]})).run(inputs())


@pytest.mark.parametrize('extra', [
    {'held_out': []}, {'assessment_scores': {'score': 1}}, {'feedback': []}, {'tools': []},
])
def test_proposal_context_rejects_unknown_and_unrelated_inputs(extra):
    with pytest.raises(ValueError):
        ProposalAgentInput(system_prompt='Propose from sources', context={'evidence': [], **extra})


@pytest.mark.parametrize('feedback', [
    {'failed_entailment_cases': []}, {'remaining_attempts': 0},
])
def test_initial_proposal_rejects_repair_feedback_even_when_empty(feedback):
    with pytest.raises(ValueError, match='cannot receive repair feedback'):
        ProposalAgentInput(system_prompt='Propose from sources', context={'evidence': [], **feedback})


@pytest.mark.parametrize('case', [
    {'id': 'owner-required', 'status': 'passed', 'expected': True, 'actual': True},
    {'id': 'owner-required', 'status': 'error', 'expected': True, 'actual': False},
    {'id': ' ', 'status': 'failed', 'expected': True, 'actual': False},
    {'id': 'owner-required', 'status': 'failed', 'expected': True, 'actual': False, 'assessment_score': 99},
])
def test_repair_context_rejects_nonfailed_or_unrelated_diagnostics(case):
    with pytest.raises(ValueError):
        ProposalAgentInput(operation='repair', system_prompt='Repair from failed cases',
            context={'evidence': [], 'failed_entailment_cases': [case]})


def test_proposal_context_preserves_exact_strings_and_original_dictionary_shape():
    from oe_studio.agents.proposal import ProposalContext
    context = {'evidence': [{'id': 'E1', 'resolved': True, 'quote': '  quoted bytes\n'}],
               'ontology': '  <https://example.org/s> <https://example.org/p> " value " .\n\n',
               'instruction': '  Retain lexical whitespace\n'}
    inputs_value = ProposalAgentInput(system_prompt='  preserved prompt\n', context=context)
    assert isinstance(inputs_value.context, ProposalContext)
    assert inputs_value.context.model_dump(exclude_unset=True) == context
    assert inputs_value.system_prompt == '  preserved prompt\n'
    assert ProposalAgentInput(system_prompt='minimal', context={'evidence': []}).context.model_dump(exclude_unset=True) == {'evidence': []}


def test_repair_contract_preserves_caller_selected_nonprefixed_question_identity():
    case = {'id': 'owner-required', 'status': 'failed', 'expected': True, 'actual': False}
    context = {'ontology': '\n', 'evidence': [], 'failed_entailment_cases': [case], 'remaining_attempts': 1}
    value = ProposalAgentInput(operation='repair', system_prompt='Repair from failed cases', context=context)
    assert value.context.model_dump(exclude_unset=True) == context
    with pytest.raises(ValueError, match='requires failed entailment diagnostics'):
        ProposalAgentInput(operation='repair', system_prompt='Repair', context={'evidence': []})


def test_proposal_contract_rejects_held_out_question_split():
    with pytest.raises(ValueError, match='development questions only'):
        ProposalAgentInput(system_prompt='Propose', context={'evidence': [],
            'competency_questions': [{'id': 'secret', 'split': 'held_out'}]})
