import pytest
from pydantic import ValidationError
from oe_studio.schemas import TestSpec as Spec
from oe_studio.testspecs import generate_specs


def test_generated_python_is_rejected():
    with pytest.raises(ValidationError):
        Spec(test_id="bad", kind="ask", query="ASK {}", expected=True, rationale="bad test", python="import os")


def test_synthetic_tests_cannot_target_held_out_split():
    with pytest.raises(ValidationError):
        Spec(test_id="bad", kind="ask", query="ASK {}", expected=True, rationale="bad test", split="held_out")


def test_missing_data_is_not_owl_negation():
    suite = generate_specs(["evidence-1"])
    missing = next(t for t in suite if t["test_id"] == "SYN-missing-owner")
    assert missing["kind"] == "shacl" and missing["expected_conforms"] is False
    assert all(t["oracle_status"] == "needs_review" for t in suite)
    assert len(suite) == 4
