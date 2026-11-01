"""Development-only compatibility bridge to the pinned executable benchmark API.

This is deliberately not imported by the workflow, model or held-out evaluator.
Jena remains the inference authority; OntoCheck executes its own constraint scorer.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from .artifacts import canonical_json, digest
from .assessment import COMMIT, RESOURCE_ROOT, ROOT
from .engine_isolation import isolated_command, python_runtime_paths
from .schemas import valid_iri
from .validation import validate

PROFILE = 'jena_rdfs_simple'
WORKER = Path(__file__).with_name('benchmark_worker.py')
EXPORT_ID = '__jena_closure_export'


def _admit(suite):
    from rdflib import URIRef
    from rdflib.plugins.sparql import prepareQuery
    from rdflib.plugins.sparql.parserutils import CompValue
    if not isinstance(suite, dict) or suite.get('schema_version') != '2.0':
        raise ValueError('Only explicit schema 2.0 development benchmarks are admitted')
    cases = suite.get('cases')
    if not isinstance(cases, list) or not 0 < len(cases) <= 20:
        raise ValueError('Provide 1–20 development cases')
    if any(not isinstance(case, dict) or case.get('split') != 'development' for case in cases):
        raise ValueError('Non-development benchmark input is not admitted to this bridge')
    if suite.get('inference') != {'profile': PROFILE}:
        raise ValueError('Only the explicit jena_rdfs_simple profile is supported; profiles are never rewritten')
    namespaces = suite.get('namespaces', {})
    if not isinstance(namespaces, dict) or len(namespaces) > 20 or any(
            not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', prefix) or not valid_iri(uri)
            for prefix, uri in namespaces.items()):
        raise ValueError('Benchmark namespaces must be bounded explicit HTTP(S) bindings')
    prologue = ''.join(f'PREFIX {prefix}: <{uri}>\n' for prefix, uri in sorted(namespaces.items()))
    tests, identities, case_ids = [], [], set()
    for case in cases:
        case_id = case.get('id')
        if (not isinstance(case_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', case_id)
                or case_id in case_ids):
            raise ValueError('Case identifiers must be bounded and unique')
        case_ids.add(case_id)
        if (case.get('task_type') != 'constrained_plan' or case.get('level') != 'constrained_generation'
                or case.get('scoring') != {'answer_weight': 0.0, 'evidence_weight': 0.0, 'constraint_weight': 1.0}):
            raise ValueError('Only constrained_plan with unit constraint-only scoring is admitted')
        query, expected = case.get('query', {}), case.get('expected', {})
        if (set(query) != {'language', 'checks'} or query.get('language') != 'sparql_constraints'
                or expected.get('kind') != 'constraint_checks' or not isinstance(expected.get('values'), dict)):
            raise ValueError('Only explicit SPARQL constraint checks are supported')
        checks = query['checks']
        if not isinstance(checks, list) or not 0 < len(checks) <= 20:
            raise ValueError('Each case requires 1–20 checks')
        check_ids = set()
        for check in checks:
            check_id, text = check.get('id'), check.get('query')
            if (set(check) != {'id', 'query'} or not isinstance(check_id, str)
                    or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', check_id) or check_id in check_ids
                    or not isinstance(text, str) or not 0 < len(text) <= 16_000):
                raise ValueError('Constraint check identifiers/queries are invalid or duplicated')
            check_ids.add(check_id)
            state = expected['values'].get(check_id)
            if state not in ('entailed', 'not_entailed'):
                raise ValueError('Every check requires an explicit entailment state')
            algebra = prepareQuery(prologue + text).algebra

            def inspect(node):
                if not isinstance(node, CompValue):
                    return
                if node.name not in {'AskQuery', 'Project', 'BGP'} or ('datasetClause' in node and node['datasetClause']):
                    raise ValueError('Only local positive basic-graph-pattern ASK checks are admitted')
                if node.name == 'BGP' and any(not isinstance(predicate, URIRef) for _, predicate, _ in node['triples']):
                    raise ValueError('Variable predicates and property paths are unsupported')
                for child in node.values():
                    if isinstance(child, CompValue):
                        inspect(child)

            if algebra.name != 'AskQuery':
                raise ValueError('Constraint checks must be ASK queries')
            inspect(algebra)
            test_id = f'{case_id}::{check_id}'
            tests.append({'id': test_id, 'kind': 'ask', 'query': prologue + text, 'expected': state == 'entailed'})
            identities.append((case_id, check_id, test_id))
        if check_ids != set(expected['values']):
            raise ValueError('Expected states must exactly match the executed checks')
    if len(tests) > 99:
        raise ValueError('At most 99 checks fit the bounded Jena export run')
    return tests, identities


def run_rdfs_benchmark(ontology_ttl: str, suite: dict) -> dict:
    report = {'status': 'unsupported', 'split': 'development', 'score': None, 'equivalent': None,
              'oracles_passed': None, 'raw': {}, 'comparisons': [], 'diagnostics': [],
              'engine': {'name': 'OntoCheck executable benchmark', 'commit': COMMIT,
                         'reasoner': 'frozen-jena-rdfs-simple-v1'},
              'limitations': ['Only the admitted development constrained_plan subset is verified.',
                              'Built-in graph_path is a counterexample baseline, not an RDFS-equivalent engine.',
                              'No held-out study, OWL reasoning, proof-path or published-domain-suite equivalence is claimed.']}
    try:
        suite_bytes = canonical_json(suite)
        if len(suite_bytes) > 128_000:
            raise ValueError('Benchmark suite exceeds its input limit')
        suite = json.loads(suite_bytes)  # Freeze caller-owned mappings before admission/execution.
        tests, identities = _admit(suite)
        if not isinstance(ontology_ttl, str) or len(ontology_ttl.encode()) > 1_048_576:
            raise ValueError('Benchmark graph or suite exceeds its input limit')
    except Exception as exc:
        # No oracle values, identifiers, query text or input digests are returned for
        # inadmissible splits. This routine cannot be used as held-out feedback.
        report['diagnostics'].append('Benchmark input is outside the admitted development contract: ' + type(exc).__name__)
        return report
    report['suite_sha256'] = hashlib.sha256(canonical_json(suite)).hexdigest()
    report['ontology_sha256'] = hashlib.sha256(ontology_ttl.encode()).hexdigest()
    bundle = digest({'suite': report['suite_sha256'], 'ontology': report['ontology_sha256'],
                     'bridge': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                     'worker': hashlib.sha256(WORKER.read_bytes()).hexdigest()})
    report['bundle_digest'] = bundle
    export = {'id': EXPORT_ID, 'kind': 'select_rows', 'query': 'SELECT ?s ?p ?o WHERE { ?s ?p ?o }',
              'expected': [], 'comparison': 'contains'}
    jena = validate(ontology_ttl, bundle_digest=bundle, tests=[*tests, export])
    report['raw']['jena'] = jena
    if jena['status'] not in {'passed', 'failed'}:
        report['status'] = jena['status']
        report['diagnostics'].append('Jena did not produce an admitted, complete closure and case result set')
        return report
    try:
        rows = next(case['actual'] for case in jena['cases'] if case['id'] == EXPORT_ID)
        closure_hash = hashlib.sha256(canonical_json(rows)).hexdigest()
        report['closure_rows_sha256'] = closure_hash
        payload = {'ontology_ttl': ontology_ttl, 'suite': suite, 'closure_rows': rows,
                   'ontology_sha256': report['ontology_sha256'], 'suite_sha256': report['suite_sha256'],
                   'closure_rows_sha256': closure_hash, 'nltk_data_dir': str(RESOURCE_ROOT)}
        python = os.getenv('OE_ONTOCHECK_PYTHON', str(ROOT / '.venv-ontocheck/bin/python'))
        with tempfile.TemporaryDirectory(prefix='oe-benchmark-') as work:
            directory = Path(work)
            request = directory / 'request.json'
            request.write_bytes(canonical_json(payload))
            command, isolation = isolated_command([python, '-I', str(WORKER), str(request)], workdir=directory,
                readable=[WORKER, RESOURCE_ROOT, *python_runtime_paths(python)])
            report['engine']['isolation'] = isolation
            output = directory / 'result.json'
            with output.open('wb') as stream:
                process = subprocess.run(command, stdout=stream, stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL, cwd=directory, timeout=20,
                    env={'PATH': str(Path(python).parent), 'LANG': 'C.UTF-8', 'TMPDIR': work})
            if process.returncode or output.stat().st_size > 4 * 1024 * 1024:
                raise RuntimeError('Pinned benchmark worker failed or exceeded its output limit')
            result = json.loads(output.read_text())
        if result.get('status') != 'completed':
            report['status'] = result.get('status') if result.get('status') in {'error', 'unsupported'} else 'error'
            report['diagnostics'].extend(result.get('diagnostics', ['Invalid upstream report']))
            return report
        for key in ('ontology_sha256', 'suite_sha256', 'closure_rows_sha256'):
            if result.get(key) != report[key]:
                raise ValueError('Upstream benchmark report input identity mismatch')
        report['engine']['upstream_environment'] = result['upstream_environment']
        raw = result['raw']
        values = raw['ontocheck']['results']
        if (len(values) != len(suite['cases']) or {case['case_id'] for case in values} != {case['id'] for case in suite['cases']}
                or any(case['status'] != 'success' for case in values)):
            report['raw'].update(raw)
            raise ValueError('Upstream benchmark skipped or failed a required case; its raw zero is unavailable')
        by_case = {case['case_id']: case for case in values}
        direct = {case['id']: case for case in jena['cases']}
        for case_id, check_id, test_id in identities:
            observed = by_case[case_id]['actual']['checks'][check_id]
            direct_state = 'entailed' if direct[test_id]['actual'] else 'not_entailed'
            report['comparisons'].append({'case_id': case_id, 'check_id': check_id,
                'jena': direct_state, 'ontocheck': observed, 'equal': direct_state == observed})
        report['raw'].update(raw)
        report['equivalent'] = all(item['equal'] for item in report['comparisons'])
        report['oracles_passed'] = jena['status'] == 'passed' and raw['ontocheck']['score'] == 1.0
        if not report['equivalent']:
            raise ValueError('Upstream evaluation disagrees with direct Jena queries on the exported closure')
        report.update(status='completed', score=raw['ontocheck']['score'])
    except subprocess.TimeoutExpired:
        report['status'] = 'timeout'
        report['diagnostics'].append('Executable OntoCheck benchmark worker exceeded 20 seconds')
    except (OSError, ValueError, RuntimeError, TypeError, KeyError, StopIteration) as exc:
        report['status'] = 'error'
        report['diagnostics'].append(f'{type(exc).__name__}: {str(exc)[:1000]}')
    return report
