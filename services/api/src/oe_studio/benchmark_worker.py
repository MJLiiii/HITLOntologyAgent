"""Isolated upstream benchmark execution over a hash-bound Jena materialization."""
from dataclasses import asdict, replace
import hashlib
from importlib import metadata
import json
from pathlib import Path
import resource
import sys

COMMIT = '69d42e38979f381fe531ae547fcc49b8ad58ef15'
STOPWORDS_SHA256 = 'f6d005956f407dbc6ea32e5ff0c7e8e6f71488d3239b9023efdc7fc139d6375b'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def run(payload):
    if any(case.get('split') != 'development' for case in payload['suite']['cases']):
        return {'status': 'unsupported', 'diagnostics': ['Non-development workload is not admitted']}
    resource.setrlimit(resource.RLIMIT_CPU, (10, 11))
    resource.setrlimit(resource.RLIMIT_FSIZE, (4 * 1024 * 1024, 4 * 1024 * 1024))

    def audit(event, args):
        if event in {'socket.connect', 'socket.getaddrinfo', 'socket.sendto', 'socket.sendmsg',
                     'subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn', 'os.fork'}:
            raise PermissionError('Benchmark worker prohibits network access and child processes')

    sys.addaudithook(audit)
    import nltk
    data = Path(payload['nltk_data_dir'])
    if hashlib.sha256((data / 'corpora/stopwords/english').read_bytes()).hexdigest() != STOPWORDS_SHA256:
        raise ValueError('Pinned language resource changed')
    nltk.data.path[:] = [str(data)]
    direct = json.loads(metadata.distribution('ontocheck').read_text('direct_url.json') or '{}')
    if direct.get('vcs_info', {}).get('commit_id') != COMMIT:
        raise ValueError('The exact reviewed OntoCheck source commit is required')
    for key, content in [('ontology_sha256', payload['ontology_ttl'].encode()),
                         ('suite_sha256', canonical(payload['suite'])),
                         ('closure_rows_sha256', canonical(payload['closure_rows']))]:
        if hashlib.sha256(content).hexdigest() != payload[key]:
            raise ValueError('Benchmark input hash mismatch')
    from rdflib import Graph, URIRef, Literal
    from ontocheck.benchmark.io import parse_suite
    from ontocheck.benchmark.runner import BenchmarkRunner
    from ontocheck.benchmark.evaluators import EvaluatorRegistry, ConstrainedPlanEvaluator
    from ontocheck.benchmark.reasoners import ReasonerRegistry, GraphPathReasoner
    suite = parse_suite(payload['suite'])
    if suite.inference_profile != 'jena_rdfs_simple' or any(case.task_type != 'constrained_plan' for case in suite.cases):
        raise ValueError('Unsupported executable benchmark profile/task')
    asserted = Graph().parse(data=payload['ontology_ttl'], format='turtle')
    closure = Graph()

    def term(binding):
        if binding['kind'] == 'iri':
            return URIRef(binding['value'])
        if binding['kind'] == 'literal':
            return Literal(binding['value'], lang=binding.get('lang'),
                           datatype=None if binding.get('lang') else binding.get('datatype'), normalize=False)
        raise ValueError('Blank/unsupported closure terms cannot be reconstructed')

    for row in payload['closure_rows']:
        closure.add(tuple(term(row[key]) for key in ('s', 'p', 'o')))
    if not set(asserted) <= set(closure) or len(closure) != len(payload['closure_rows']):
        raise ValueError('Exported Jena closure does not preserve the exact asserted graph')

    class FrozenJenaRDFSReasoner:
        name = 'frozen-jena-rdfs-simple-v1'

        def materialize(self, graph):
            if set(graph) != set(asserted):
                raise ValueError('A materialization cannot be reused for a different source graph')
            copied = Graph()
            for prefix, namespace in graph.namespaces():
                copied.bind(prefix, namespace)
            for triple in closure:
                copied.add(triple)
            return copied

        def reason(self, case, graph):
            raise ValueError('Graph-path proofs/hop counts are outside this Jena bridge')

    # Fresh registries are local to this process/run. Nothing replaces a global
    # upstream profile or escapes to the application/model's development feedback.
    registry = EvaluatorRegistry()
    registry.register('constrained_plan', ConstrainedPlanEvaluator())
    reasoners = ReasonerRegistry()
    reasoners.register('jena_rdfs_simple', FrozenJenaRDFSReasoner())
    actual = BenchmarkRunner(registry=registry, reasoners=reasoners).run_graph(suite, asserted)
    baseline_reasoners = ReasonerRegistry()
    baseline_reasoners.register('graph_path', GraphPathReasoner())
    baseline = BenchmarkRunner(registry=registry, reasoners=baseline_reasoners).run_graph(
        replace(suite, inference_profile='graph_path'), asserted)
    return {'status': 'completed', **{key: payload[key] for key in ('ontology_sha256', 'suite_sha256', 'closure_rows_sha256')},
            'upstream_environment': {'python': sys.version.split()[0], 'commit': COMMIT,
                'packages': {name: metadata.version(name) for name in ('ontocheck', 'rdflib', 'nltk')},
                'stopwords_sha256': STOPWORDS_SHA256},
            'raw': {'ontocheck': asdict(actual), 'graph_path_counterexample': asdict(baseline)}}


if __name__ == '__main__':
    try:
        result = run(json.loads(Path(sys.argv[1]).read_text()))
    except Exception as exc:
        result = {'status': 'error', 'diagnostics': [f'{type(exc).__name__}: {str(exc)[:1000]}']}
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
