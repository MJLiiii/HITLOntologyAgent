from .demo import NS, PREFIX
from .schemas import TestSpec


def generate_specs(evidence_ids):
    """Four bounded demo scenarios; expectations require an explicit human oracle decision."""
    examples = [
        {"test_id": "SYN-positive-owner", "kind": "ask", "query": f"PREFIX demo: <{NS}> ASK {{ demo:PayrollService demo:hasOwner demo:OperationsTeam }}", "expected": True,
         "rationale": "The synthetic ownership policy names Operations Team as the payroll owner."},
        {"test_id": "SYN-unwanted-owner", "kind": "ask", "query": f"PREFIX demo: <{NS}> ASK {{ demo:PayrollService demo:hasOwner demo:DataTeam }}", "expected": False,
         "rationale": "This owner is not entailed by the frozen fixture; this is not proof of OWL negation."},
        {"test_id": "SYN-missing-owner", "kind": "shacl", "fixtures_ttl": PREFIX + "demo:MissingOwnerService a demo:Service .", "expected_conforms": False,
         "rationale": "A missing required owner should violate the Service SHACL shape, not an OWL axiom."},
        {"test_id": "SYN-owner-boundary", "kind": "shacl", "fixtures_ttl": PREFIX + "demo:BoundaryService a demo:Service ; demo:hasOwner demo:OperationsTeam, demo:DataTeam .", "expected_conforms": True,
         "rationale": "The current shape requires at least one owner and specifies no maximum; two owners conform."},
    ]
    return [TestSpec(**value, evidence_ids=evidence_ids[:20]).model_dump(exclude_none=True) for value in examples]
