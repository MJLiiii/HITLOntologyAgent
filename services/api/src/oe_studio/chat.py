"""Read-only retrieval over a frozen ontology and verified source chunks."""
import re
from rdflib import RDF, RDFS, URIRef
from .rdf import NS, parse_ttl, to_dict

STOP = {"a", "an", "the", "is", "are", "of", "for", "what", "who", "how", "does", "do", "it", "its", "and", "with", "in", "can", "you", "me", "about", "tell", "please", "to"}


def words(text):
    return set(re.findall(r"[a-z0-9]+", text.lower())) - STOP


def select_context(question, evidence, ontology_triples):
    """Rank the complete local snapshot; disclose the bounded model selection."""
    def tokens(text):
        return words(re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text))

    query = tokens(question)
    resolved = [item for item in evidence if item["resolved"]]

    def ranked(items, render, limit):
        if len(items) <= limit:
            return items
        return sorted(items, key=lambda item: -len(query & tokens(render(item))))[:limit]

    sources = ranked(resolved, lambda e: e["title"] + " " + e["quote"], 20)
    facts = ranked(ontology_triples, lambda t: " ".join(str(v) for v in t.values()), 100)
    return sources, facts, {"method": "local_lexical_overlap_v1", "evidence_available": len(evidence),
        "evidence_selected": len(sources), "evidence_unresolved": len(evidence) - len(resolved),
        "triples_available": len(ontology_triples), "triples_selected": len(facts),
        "truncated": len(sources) < len(resolved) or len(facts) < len(ontology_triples)}


def label(graph, term):
    return str(graph.value(term, RDFS.label) or re.sub(r"(?<=[a-z])(?=[A-Z])", " ", str(term).rsplit("/", 1)[-1].rsplit("#", 1)[-1]))


def answer_question(question: str, ontology_ttl: str, evidence: list[dict], history: list[dict] | None = None):
    graph = parse_ttl(ontology_ttl)
    context_question = question
    if history and re.search(r"\b(it|its|they|their|that|those|them)\b", question, re.I):
        previous = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
        context_question = previous + " " + question
    tokens = words(context_question)
    intent = words(question)
    known = []
    label_tokens = set()
    for subject, _, name in graph.triples((None, RDFS.label, None)):
        name_tokens = words(str(name))
        label_tokens.update(name_tokens)
        specific = name_tokens - {"service", "team", "critical", "owner", "has"}
        if specific & tokens:
            known.append(subject)
    ranked = sorted(((len(tokens & words(e["quote"] + " " + e["title"])), e) for e in evidence if e["resolved"]), key=lambda v: (-v[0], v[1]["id"]))
    selected = [e for score, e in ranked[:5] if score > 0]
    named_tokens = {m.group(1).lower() for m in re.finditer(r"\b([A-Za-z][\w-]*)\s+(?:service|team)\b", context_question, re.I)}
    unknown_names = named_tokens - label_tokens - STOP - {"each", "every", "any", "which", "this", "that", "all"}
    if unknown_names:
        passages = [e for e in selected if unknown_names & words(e["quote"])]
        return {"answer": "That named service or team is not recorded in the selected ontology." + (
                    " Relevant source text: " + " ".join(e["quote"] for e in passages[:2]) if passages else " No matching source passage was found."),
                "evidence": passages[:2], "triples": [], "query": None, "mode": "local",
                "unresolved_points": ["Unknown ontology entity: " + ", ".join(sorted(unknown_names))],
                "limitations": ["Local retrieval does not infer an owner for an unknown entity."]}
    rows = []
    answer = ""
    query = None
    owner = URIRef(NS + "hasOwner")
    if intent & {"owner", "owns", "owned", "responsible", "ownership", "accountable"}:
        relations = list(graph.triples((None, owner, None)))
        if known:
            relations = [t for t in relations if t[0] in known or t[2] in known]
        if relations:
            rows = relations
            answer = "\n".join(f"{label(graph, s)} is owned by {label(graph, o)}." for s, _, o in sorted(relations))
            query = f"PREFIX demo: <{NS}> SELECT ?service ?owner WHERE {{ ?service demo:hasOwner ?owner }}"
    elif intent & {"critical", "classification", "classifications", "classified"}:
        rows = list(graph.triples((None, RDF.type, URIRef(NS + "CriticalService"))))
        if known:
            rows = [t for t in rows if t[0] in known]
        if rows:
            answer = ", ".join(label(graph, t[0]) for t in rows) + " is classified as a critical service."
            hierarchy = (URIRef(NS + "CriticalService"), RDFS.subClassOf, URIRef(NS + "Service"))
            if hierarchy in graph:
                rows.append(hierarchy)
                answer += " Critical service is a subclass of Service, so RDFS also classifies it as a service."
    elif tokens & {"services", "service", "teams", "team", "ontology", "classes", "relationships", "concepts", "model"} or known:
        if known:
            rows = [t for s in known for t in graph.triples((s, None, None)) if t[1] != RDFS.label]
        else:
            rows = [t for t in graph if str(t[0]).startswith(NS) and t[1] in {RDF.type, RDFS.subClassOf, owner}][:20]
        if rows:
            answer = "The ontology records these relationships:\n" + "\n".join(
                f"• {label(graph, s)} — {('is a' if p == RDF.type else 'is a subclass of' if p == RDFS.subClassOf else label(graph, p))} — {label(graph, o)}"
                for s, p, o in rows[:10])
    if not answer and selected:
        answer = "The source material contains these relevant passages:\n" + "\n".join(f'“{e["quote"]}” [{i + 1}]' for i, e in enumerate(selected[:3]))
    unresolved = []
    if not answer:
        answer = "I couldn’t find evidence for that in this ontology or its source snapshot. Ask about the recorded services, owners or classifications, or add a relevant source document."
        unresolved = ["The requested information is not supported by the selected ontology and sources."]
    elif rows and not selected:
        unresolved = ["Ontology relationships were found, but no matching source passage was retrieved."]
    elif rows:
        answer += "\n\nSupporting sources: " + ", ".join(f"[{i + 1}] {e['title']}" for i, e in enumerate(selected[:3])) + "."
    return {"answer": answer, "evidence": selected[:3], "triples": [to_dict(t) for t in rows],
            "query": query, "unresolved_points": unresolved, "mode": "local",
            "limitations": ["Local evidence retrieval with deterministic answers; no language model is configured.",
                            "RDFS results are limited to the selected ontology; missing facts do not prove negation."]}
