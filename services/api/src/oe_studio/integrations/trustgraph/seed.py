"""Deterministic admitted RDF-to-TrustGraph seed projection.

Upstream class identifiers and domain/range identifiers must agree. Full IRIs
serve as both IDs and URI values, avoiding ambiguous label/local-name aliases.
"""
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD


def project_seed_ontology(content: bytes) -> dict:
    if not content or len(content) > 1_048_576:
        raise ValueError('Seed size exceeds the admitted bound')
    graph = Graph().parse(data=content.decode('utf-8'), format='turtle')
    classes = set(graph.subjects(RDF.type, OWL.Class)) | set(graph.subjects(RDF.type, RDFS.Class))
    objects = set(graph.subjects(RDF.type, OWL.ObjectProperty))
    datatypes = set(graph.subjects(RDF.type, OWL.DatatypeProperty))
    if not classes or len(classes | objects | datatypes) > 100 or objects & datatypes:
        raise ValueError('Seed requires 1–100 unambiguous named classes/properties')
    if any(not isinstance(term, URIRef) or not str(term).startswith(('https://', 'http://')) for term in classes | objects | datatypes):
        raise ValueError('Only named HTTP(S) seed terms are admitted')
    for term in classes | objects | datatypes:
        for predicate, value in graph.predicate_objects(term):
            if predicate not in {RDF.type, RDFS.label, RDFS.comment, RDFS.domain, RDFS.range, RDFS.subClassOf}:
                raise ValueError('Seed schema axiom is unsupported by the admitted projection')
            if predicate == RDF.type and value not in {OWL.Class, RDFS.Class, OWL.ObjectProperty, OWL.DatatypeProperty}:
                raise ValueError('Seed schema type is unsupported by the admitted projection')
            if predicate in {RDFS.label, RDFS.comment} and not isinstance(value, Literal):
                raise ValueError('Seed labels and comments must be literal values')
    result = {'metadata': {'name': 'Approved ontology seed'}, 'classes': {}, 'objectProperties': {}, 'datatypeProperties': {}}
    for group, terms, kind in [('classes', classes, 'owl:Class'), ('objectProperties', objects, 'owl:ObjectProperty'),
                               ('datatypeProperties', datatypes, 'owl:DatatypeProperty')]:
        for term in sorted(terms):
            row = {'uri': str(term), 'type': kind,
                   'rdfs:label': [{'value': str(value), 'language': value.language or ''}
                                  for value in sorted(graph.objects(term, RDFS.label), key=str)]}
            comments = sorted(map(str, graph.objects(term, RDFS.comment)))
            if comments:
                row['rdfs:comment'] = '\n'.join(comments)
            for predicate, key in [(RDFS.domain, 'rdfs:domain'), (RDFS.range, 'rdfs:range'), (RDFS.subClassOf, 'rdfs:subClassOf')]:
                values = list(graph.objects(term, predicate))
                if len(values) > 1:
                    raise ValueError('Multiple seed domain/range/parent constraints are unsupported')
                if values:
                    target = values[0]
                    if target not in classes and not (group == 'datatypeProperties' and predicate == RDFS.range and str(target).startswith(str(XSD))):
                        raise ValueError('Seed class constraints must reference declared class identifiers')
                    row[key] = str(target)
            result[group][str(term)] = row
    return result
