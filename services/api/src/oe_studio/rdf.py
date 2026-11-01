import hashlib
import rdflib
from rdflib import BNode, Graph, Literal, URIRef
from .schemas import ChangeSet

# Lexical forms are part of the reviewed artifact, including e.g. "001"^^xsd:integer.
rdflib.NORMALIZE_LITERALS = False
NS = "https://example.org/oe-demo/"


def parse_ttl(text: str) -> Graph:
    graph = Graph()
    if text.strip():
        graph.parse(data=text, format="turtle")
    return graph


def canonicalize(graph: Graph) -> str:
    if any(isinstance(term, BNode) for triple in graph for term in triple):
        raise ValueError("Unsupported blank node in named-triple profile")
    return "".join(sorted(" ".join(term.n3() for term in triple) + " .\n" for triple in graph))


def to_term(triple):
    obj = (URIRef(triple.object) if triple.object_type == "iri" else
           Literal(triple.object, lang=triple.language, datatype=triple.datatype, normalize=False))
    return URIRef(triple.subject), URIRef(triple.predicate), obj


def to_dict(triple) -> dict:
    s, p, o = triple
    result = {"subject": str(s), "predicate": str(p), "object": str(o),
              "object_type": "literal" if isinstance(o, Literal) else "iri"}
    if isinstance(o, Literal) and o.language:
        result["language"] = o.language
    if isinstance(o, Literal) and o.datatype:
        result["datatype"] = str(o.datatype)
    return result


def triples(text: str) -> list[dict]:
    return [to_dict(t) for t in sorted(parse_ttl(text), key=lambda t: tuple(map(str, t)))]


def materialize(base_ttl: str, changes: ChangeSet) -> dict:
    graph = parse_ttl(base_ttl)
    additions = [to_term(t) for t in changes.additions]
    deletions = [to_term(t) for t in changes.deletions]
    if len(set(additions)) != len(additions) or len(set(deletions)) != len(deletions):
        raise ValueError("Duplicate triple operation")
    if set(additions) & set(deletions):
        raise ValueError("Conflicting add/delete")
    for t in additions + deletions:
        if not str(t[0]).startswith(NS):
            raise ValueError("Subject outside frozen domain namespace")
    for t in deletions:
        if t not in graph:
            raise ValueError("Cannot delete missing triple")
        graph.remove(t)
    for t in additions:
        if t in graph:
            raise ValueError("Cannot add existing triple")
        graph.add(t)
    canonical = canonicalize(graph)
    graph.bind("demo", NS)
    return {"ttl": graph.serialize(format="turtle"), "canonical": canonical,
            "sha256": hashlib.sha256(canonical.encode()).hexdigest(),
            "additions": [to_dict(t) for t in sorted(additions)],
            "deletions": [to_dict(t) for t in sorted(deletions)]}
