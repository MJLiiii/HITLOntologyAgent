"""Candidate-derived development specs; never independent domain oracles."""
import hashlib
from pathlib import Path
import re

from rdflib import BNode, Literal, RDF, RDFS, SH, URIRef, XSD
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugins.sparql.parserutils import CompValue

from .artifacts import canonical_json, digest
from .demo import NS
from .rdf import canonicalize, parse_ttl, to_term
from .schemas import ChangeSet, TestSpec

MAX_TESTS = 40


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def leaf_shape_id(graph, shape):
    """Match Jena's unambiguous length-prefixed UTF-8 leaf fingerprint."""
    if isinstance(shape, URIRef):
        return str(shape)
    rows = []
    for predicate, obj in graph.predicate_objects(shape):
        if isinstance(obj, BNode):
            raise ValueError('Nested anonymous shapes have no admitted leaf signature')
        fields = [str(predicate), 'iri' if isinstance(obj, URIRef) else 'literal', str(obj),
                  str(obj.datatype or (RDF.langString if obj.language else XSD.string)) if isinstance(obj, Literal) else '',
                  (obj.language or '') if isinstance(obj, Literal) else '']
        encoded = b''.join(str(len(v.encode())).encode() + b':' + v.encode() for v in fields)
        rows.append(encoded.hex())
    return 'urn:oe:shacl-leaf:sha256:' + sha(''.join(row + '\n' for row in sorted(rows)))


def query_terms(query, kind='ask'):
    """Only local basic patterns; Jena independently parses every accepted case."""
    try:
        algebra = prepareQuery(query).algebra
        if algebra.name != ('AskQuery' if kind == 'ask' else 'SelectQuery'):
            raise ValueError('Query kind mismatch')
        terms = set()

        def inspect(value):
            if isinstance(value, CompValue):
                if value.name not in {'AskQuery', 'SelectQuery', 'Project', 'BGP'}:
                    raise ValueError('Unsupported query algebra')
                if value.get('datasetClause') not in (None, [], 'datasetClause'):
                    raise ValueError('External query datasets are prohibited')
                for key, child in value.items():
                    if key == 'triples':
                        for triple in child:
                            if not isinstance(triple[1], URIRef) or any(isinstance(t, BNode) for t in triple):
                                raise ValueError('Only named-predicate query patterns are admitted')
                            terms.update(str(t) for t in triple if isinstance(t, URIRef))
                    elif key != '_vars':
                        inspect(child)
            elif isinstance(value, (list, tuple)):
                for child in value:
                    inspect(child)
        inspect(algebra)
        return terms
    except Exception as error:
        raise ValueError('Unsupported or malformed development query') from error


def _shape_constraints(graph, shape):
    allowed_node = {RDF.type, SH.targetClass, SH.property, SH.name, SH.description, SH.message, RDFS.label, RDFS.comment}
    if set(graph.predicates(shape)) - allowed_node:
        raise ValueError('Only targetClass shapes with simple property constraints are generated')
    targets, props = list(graph.objects(shape, SH.targetClass)), list(graph.objects(shape, SH.property))
    if not isinstance(shape, URIRef) or len(targets) != 1 or not isinstance(targets[0], URIRef) or not 1 <= len(props) <= 5:
        raise ValueError('One named target class and one to five properties are required')
    allowed = {RDF.type, SH.path, SH.minCount, SH.maxCount, SH.nodeKind, SH.datatype,
               SH.severity, SH.name, SH.description, SH.message, RDFS.label, RDFS.comment}
    constraints = []
    for prop in props:
        if set(graph.predicates(prop)) - allowed:
            raise ValueError('Property constraint is outside count, IRI/literal kind and datatype templates')
        values = {}
        for predicate in (SH.path, SH.minCount, SH.maxCount, SH.nodeKind, SH.datatype, SH.severity):
            objects = list(graph.objects(prop, predicate))
            if len(objects) > 1:
                raise ValueError('Repeated property parameters are unsupported')
            values[predicate] = objects[0] if objects else None
        if not isinstance(values[SH.path], URIRef):
            raise ValueError('Only simple named property paths are supported')
        for predicate in (SH.minCount, SH.maxCount):
            count = values[predicate]
            if count is not None and (not isinstance(count, Literal) or count.datatype != XSD.integer
                                      or not re.fullmatch(r'\+?\d+', str(count))):
                raise ValueError('Counts must be explicit nonnegative integer literals')
        minimum = int(values[SH.minCount]) if values[SH.minCount] is not None else 0
        maximum = int(values[SH.maxCount]) if values[SH.maxCount] is not None else None
        if not 0 <= minimum <= 3 or (maximum is not None and not minimum <= maximum <= 3):
            raise ValueError('Counts must be consistent integers from zero to three')
        kind, datatype = values[SH.nodeKind], values[SH.datatype]
        if kind not in (None, SH.IRI, SH.Literal) or datatype not in (None, XSD.string, XSD.integer, XSD.decimal, XSD.boolean):
            raise ValueError('Unsupported node kind or datatype template')
        if kind == SH.IRI and datatype is not None:
            raise ValueError('IRI/datatype conjunction has no valid generated boundary fixture')
        if datatype == XSD.boolean and (minimum > 1 or maximum not in (None, 0, 1)):
            raise ValueError('Boolean value space cannot supply three distinct valid boundary values')
        if values[SH.severity] not in (None, SH.Violation):
            raise ValueError('Only violation severity has a fixed conformance oracle')
        constraints.append({'path': values[SH.path], 'minimum': minimum, 'maximum': maximum,
                            'kind': kind, 'datatype': datatype, 'source': leaf_shape_id(graph, prop)})
    if len({row['path'] for row in constraints}) != len(constraints):
        raise ValueError('Repeated path constraints require an explicit oracle')
    return targets[0], sorted(constraints, key=lambda row: str(row['path']))


def generate_suite(*, candidate_ttl, shapes_ttl, fixtures_ttl, questions, changes, evidence, bundle_digest):
    """Derive bounded specs without consulting engine outcomes or held-out inputs."""
    if not re.fullmatch(r'(?:sha256:)?[a-f0-9]{64}', bundle_digest):
        raise ValueError('A frozen bundle digest is required')
    for name, value, bound in [('candidate', candidate_ttl, 1_048_576), ('shapes', shapes_ttl, 100_000),
                               ('fixtures', fixtures_ttl, 100_000)]:
        if not isinstance(value, str) or len(value.encode()) > bound:
            raise ValueError(f'{name} exceeds the generation input bound')
    if not isinstance(questions, list) or not 1 <= len(questions) <= 20:
        raise ValueError('One to twenty frozen development questions are required')
    if not evidence or len(evidence) > 20 or any(not e.get('id') or e.get('resolved') is not True for e in evidence):
        raise ValueError('A bounded resolved evidence packet is required')
    if len({e['id'] for e in evidence}) != len(evidence):
        raise ValueError('Duplicate evidence identity')
    graph, shape_graph = parse_ttl(candidate_ttl), parse_ttl(shapes_ttl)
    canonicalize(graph)
    canonicalize(parse_ttl(fixtures_ttl))
    change_set = ChangeSet.model_validate(changes)
    change_rows = [{'id': 'change:' + digest({'operation': op, 'triple': triple.model_dump()})[7:],
                    'operation': op, 'triple': triple.model_dump()}
                   for op, triples in [('add', change_set.additions), ('delete', change_set.deletions)] for triple in triples]
    q_terms = {}
    for question in questions:
        if question.get('split', 'development') != 'development':
            raise ValueError('Only development questions enter generation')
        if not isinstance(question.get('id'), str) or not question['id'] or question['id'] in q_terms:
            raise ValueError('Unique frozen question identities are required')
        if type(question.get('expected', True)) is not bool:
            raise ValueError('Frozen questions require boolean expectations')
        q_terms[question['id']] = query_terms(question['sparql_query'])
    tests, gaps = [], []
    manifest = {'bundle_digest': bundle_digest, 'candidate_sha256': sha(candidate_ttl),
                'shapes_sha256': sha(shapes_ttl), 'fixtures_sha256': sha(fixtures_ttl),
                'questions_digest': digest(questions), 'evidence_digest': digest(evidence),
                'changes_digest': digest(change_rows), 'changes': change_rows, 'split': 'development'}
    fresh_base = NS + 'synthetic/' + digest(manifest)[7:23] + '/'
    if any(str(term).startswith(fresh_base) for triple in graph + parse_ttl(fixtures_ttl) for term in triple):
        raise ValueError('Synthetic fixture namespace collides with frozen input')

    def emit(scenario, rationale, oracle, terms, **spec):
        if len(tests) >= MAX_TESTS:
            if not any(g['code'] == 'case_limit' for g in gaps):
                gaps.append({'code': 'case_limit', 'detail': f'Bounded to {MAX_TESTS} cases; remaining coverage needs review.'})
            return
        fixture = spec.get('fixtures_ttl', fixtures_ttl)
        if len(fixture.encode()) > 20000 and 'fixtures_ttl' in spec:
            gaps.append({'code': 'fixture_limit', 'detail': 'Generated fixture exceeds 20000 UTF-8 bytes.'})
            return
        if 'query' in spec:
            query_terms(spec['query'], spec['kind'])
        terms = set(map(str, terms))
        linked = [r['id'] for r in change_rows if terms & {r['triple']['subject'], r['triple']['predicate'], r['triple']['object']}]
        values = dict(spec, scenario=scenario, rationale=rationale, oracle_source=oracle,
                      evidence_ids=[e['id'] for e in evidence],
                      question_ids=sorted(q for q, named in q_terms.items() if terms & named), change_ids=linked,
                      target_ontology_sha256=sha(candidate_ttl), fixture_sha256=sha(fixture),
                      assumptions=['Evidence IDs identify the frozen packet; oracle support still needs human judgement.',
                                   'RDFS and SHACL do not establish OWL DL consistency.'])
        values['test_id'] = 'SYN-' + scenario + '-' + digest(values)[7:23]
        case = TestSpec(**values).model_dump(exclude_none=True)
        if len(canonical_json([*tests, case])) > 800_000:
            if not any(g['code'] == 'suite_limit' for g in gaps):
                gaps.append({'code': 'suite_limit', 'detail': 'Generated suite exceeds the 800000-byte bound.'})
            return
        tests.append(case)

    for question in questions:
        emit('regression', 'Preserve the frozen competency-question expectation independently of candidate results.',
             'Frozen development competency question: ' + question['id'], q_terms[question['id']],
             kind='ask', query=question['sparql_query'], expected=question.get('expected', True))

    relationships = [(s, p, o) for s, p, o in graph if p in {RDFS.subClassOf, RDFS.subPropertyOf, RDFS.domain, RDFS.range}]
    changed = {to_term(t) for t in change_set.additions}
    relationships.sort(key=lambda row: (row not in changed, tuple(map(str, row))))
    for index, (subject, predicate, obj) in enumerate(relationships):
        a, b = URIRef(fresh_base + f'axiom-{index}/subject'), URIRef(fresh_base + f'axiom-{index}/object')
        if not isinstance(obj, URIRef):
            gaps.append({'code': 'unsupported_axiom', 'detail': 'Schema inference requires a named object.'})
            continue
        if predicate == RDFS.subClassOf:
            fixture, wanted = (a, RDF.type, subject), (a, RDF.type, obj)
        elif predicate == RDFS.subPropertyOf:
            fixture, wanted = (a, subject, b), (a, obj, b)
        else:
            fixture = (a, subject, b)
            wanted = (a if predicate == RDFS.domain else b, RDF.type, obj)
        text = fixtures_ttl + '\n' + ' '.join(term.n3() for term in fixture) + ' .\n'
        emit('positive', 'The candidate schema axiom should entail this fresh synthetic instance under RDFS.',
             'Candidate axiom and fixed RDFS rule; proposed oracle needs review.', [subject, obj],
             kind='ask', fixtures_ttl=text, query='ASK { ' + ' '.join(t.n3() for t in wanted) + ' }', expected=True)

    for shape in sorted(set(shape_graph.subjects(RDF.type, SH.NodeShape)), key=str):
        try:
            target, constraints = _shape_constraints(shape_graph, shape)
        except (ValueError, TypeError, OverflowError) as error:
            gaps.append({'code': 'unsupported_shape', 'detail': str(error), 'shape': str(shape) if isinstance(shape, URIRef) else 'anonymous'})
            continue
        focus = URIRef(fresh_base + 'shape-' + sha(str(shape))[:12] + '/focus')

        def fixture_for(overrides=None, wrong_path=None):
            rows = [(focus, RDF.type, target)]
            for c in constraints:
                count = (overrides or {}).get(c['path'], max(1, c['minimum']) if c['maximum'] != 0 else 0)
                for index in range(count):
                    if c['datatype']:
                        value = 'synthetic-' + str(index) if c['datatype'] == XSD.string else (('true' if index == 0 else 'false') if c['datatype'] == XSD.boolean else str(index + 1))
                        value = Literal(value, datatype=c['datatype'], normalize=False)
                    elif c['kind'] == SH.Literal:
                        value = Literal('synthetic-' + str(index))
                    else:
                        value = URIRef(str(focus) + '/value-' + sha(str(c['path']))[:8] + '-' + str(index))
                    if c['path'] == wrong_path and index == 0:
                        value = Literal('explicit incompatible value') if c['kind'] == SH.IRI else URIRef(str(focus) + '/wrong-kind')
                    rows.append((focus, c['path'], value))
            return fixtures_ttl + '\n' + ''.join(' '.join(term.n3() for term in row) + ' .\n' for row in rows)

        terms = [target, *(c['path'] for c in constraints)]
        emit('positive', 'A fresh instance satisfying each admitted frozen property constraint should conform.',
             'Frozen SHACL shape ' + str(shape), terms, kind='shacl', fixtures_ttl=fixture_for(),
             expected_conforms=True, expected_violations=[])
        for c in constraints:
            signature = {'focusNode': str(focus), 'path': str(c['path']), 'sourceShape': c['source'], 'severity': str(SH.Violation)}
            if c['minimum']:
                emit('missing_data', 'Absent required data violates SHACL; this is not OWL negation.',
                     'Frozen sh:minCount on ' + str(c['path']), [target, c['path']], kind='shacl',
                     fixtures_ttl=fixture_for({c['path']: 0}), expected_conforms=False, expected_violations=[signature])
            emit('negative', 'This fresh subject has no such value: false ASK means not entailed, not logical negation.',
                 'Explicit synthetic absence under the named-triple RDFS profile.', [target, c['path']],
                 kind='ask', fixtures_ttl=fixture_for({c['path']: 0}),
                 query=f'ASK {{ {focus.n3()} {c["path"].n3()} <{fresh_base}unasserted-value> }}', expected=False)
            boundary = c['maximum'] if c['maximum'] is not None else max(2, c['minimum'] + 1)
            emit('boundary', 'Count is at the stated maximum, or above the minimum when no maximum is declared.',
                 'Frozen SHACL cardinality, not an invented domain limit.', [target, c['path']],
                 kind='shacl', fixtures_ttl=fixture_for({c['path']: boundary}), expected_conforms=True, expected_violations=[])
            if c['maximum'] is not None:
                emit('boundary', 'One value beyond the frozen maximum should violate the explicit constraint.',
                     'Frozen sh:maxCount on ' + str(c['path']), [target, c['path']], kind='shacl',
                     fixtures_ttl=fixture_for({c['path']: c['maximum'] + 1}), expected_conforms=False, expected_violations=[signature])
            incompatible = int(c['kind'] is not None) + int(c['datatype'] is not None)
            if incompatible and c['maximum'] != 0:
                emit('contradictory', 'An explicit value contradicts the node-kind/datatype constraint; this is a data-constraint violation, not an OWL inconsistency proof.',
                     'Frozen SHACL nodeKind/datatype on ' + str(c['path']), [target, c['path']], kind='shacl',
                     fixtures_ttl=fixture_for(wrong_path=c['path']), expected_conforms=False,
                     expected_violations=[signature] * incompatible)

    for triple in change_set.additions:
        subject, predicate, obj = to_term(triple)
        if not isinstance(obj, Literal) or (subject, predicate, obj) not in graph:
            continue
        value = {'kind': 'literal', 'value': str(obj), 'datatype': str(obj.datatype or (RDF.langString if obj.language else XSD.string))}
        if obj.language:
            value['lang'] = obj.language
        emit('positive', 'Preserve the proposed addition’s exact literal lexical value, datatype and language tag.',
             'Candidate change item; semantic appropriateness requires source review.', [subject, predicate],
             kind='select_rows', query=f'SELECT ?value WHERE {{ {subject.n3()} {predicate.n3()} ?value }}',
             expected=[{'value': value}], comparison='contains')

    covered = {test['scenario'] for test in tests}
    for scenario in sorted({'positive', 'negative', 'boundary', 'contradictory', 'missing_data', 'regression'} - covered):
        gaps.append({'code': 'scenario_unavailable', 'detail': scenario + ' has no supported template; no oracle invented.'})
    return {'tests': tests, 'generator': {'mode': 'deterministic_candidate_derived', 'version': 'candidate-specs-v1',
            'implementation_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'maximum_cases': MAX_TESTS,
            'oracle_policy': 'Human review required; model/observed engine output never defines expectations.'},
            'input_manifest': manifest, 'coverage_gaps': gaps}
