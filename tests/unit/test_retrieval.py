from oe_studio.chat import select_context


def test_bounded_context_searches_the_entire_snapshot():
    evidence = [{"id": str(i), "title": "Catalog", "quote": "Unrelated record", "resolved": True} for i in range(25)]
    evidence[-1]["quote"] = "ZephyrService is owned by ReliabilityTeam."
    evidence[-2].update(quote="ZephyrService is withdrawn", resolved=False)
    triples = [{"subject": f"https://example.org/A{i}", "predicate": "https://example.org/owns", "object": "https://example.org/Generic"} for i in range(105)]
    triples[-1]["subject"] = "https://example.org/ZephyrService"
    sources, facts, metadata = select_context("Who owns Zephyr Service?", evidence, triples)
    assert sources[0]["id"] == "24"
    assert all(e["resolved"] for e in sources)
    assert facts[0] == triples[-1]
    assert len(sources) == 20 and len(facts) == 100
    assert metadata["truncated"] is True
    assert metadata["evidence_available"] == 25
    assert metadata["evidence_unresolved"] == 1


def test_small_context_preserves_original_indices_and_reports_no_truncation():
    evidence = [{"id": "one", "title": "Catalog", "quote": "Relevant", "resolved": True}]
    sources, facts, metadata = select_context("relevant", evidence, [])
    assert sources == evidence and facts == []
    assert metadata["truncated"] is False
