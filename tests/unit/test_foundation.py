import pytest
from pydantic import ValidationError

from oe_studio.artifacts import ArtifactStore
from oe_studio.rdf import materialize, canonicalize, parse_ttl
from oe_studio.schemas import Triple, ChangeSet, QuestionRequest
from oe_studio.settings import Settings

NS = "https://example.org/oe-demo/"
P = "http://www.w3.org/2000/01/rdf-schema#label"


def test_artifact_hash_mismatch_rejected(tmp_path):
    store = ArtifactStore(tmp_path)
    ref = store.put(b"immutable", "text/plain")
    assert store.get_verified(ref) == b"immutable"
    (tmp_path / ref["sha256"]).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="integrity"):
        store.get_verified(ref)


def test_storage_key_cannot_escape_root(tmp_path):
    store = ArtifactStore(tmp_path)
    with pytest.raises(ValueError):
        store.get_verified({"sha256": "../secret", "byte_length": 1})


def test_shared_mode_rejects_dev_identity(tmp_path):
    with pytest.raises(ValueError, match="local"):
        Settings(data_dir=tmp_path, mode="shared")


def test_named_triple_diff_is_deterministic():
    a = Triple(subject=NS + "Service", predicate=P, object="Service", object_type="literal")
    b = Triple(subject=NS + "Team", predicate=P, object="Team", object_type="literal")
    x = materialize("", ChangeSet(additions=[a, b]))
    y = materialize("", ChangeSet(additions=[b, a]))
    assert x["sha256"] == y["sha256"]


def test_literals_preserve_datatype_and_language():
    changes = ChangeSet(additions=[
        Triple(subject=NS + "A", predicate=P, object="001", object_type="literal", datatype="http://www.w3.org/2001/XMLSchema#integer"),
        Triple(subject=NS + "B", predicate=P, object="équipe", object_type="literal", language="fr"),
    ])
    result = materialize("", changes)
    assert '"001"^^' in result["canonical"]
    assert '"équipe"@fr' in result["canonical"]


def test_literal_whitespace_survives_add_and_exact_delete():
    value = "  Exact label \n\t"
    triple = Triple(subject=NS + "A", predicate=P, object=value, object_type="literal")
    assert triple.object == value
    added = materialize("", ChangeSet(additions=[triple]))
    assert str(next(parse_ttl(added["ttl"]).objects())) == value
    removed = materialize(added["ttl"], ChangeSet(deletions=[triple]))
    assert not parse_ttl(removed["ttl"])


def test_delete_missing_triple_rejected():
    triple = Triple(subject=NS + "A", predicate=P, object="A", object_type="literal")
    with pytest.raises(ValueError, match="missing"):
        materialize("", ChangeSet(deletions=[triple]))


def test_unsupported_blank_node_edit_rejected():
    with pytest.raises(ValidationError):
        Triple(subject="_:b", predicate=P, object="A", object_type="literal")
    with pytest.raises(ValueError, match="blank"):
        canonicalize(parse_ttl("[] <https://example.org/p> <https://example.org/o> ."))


def test_unknown_fields_and_operation_limit_rejected():
    with pytest.raises(ValidationError):
        QuestionRequest(question="hello", actor="approver")
    t = Triple(subject=NS + "A", predicate=P, object="A", object_type="literal")
    with pytest.raises(ValidationError):
        ChangeSet(additions=[t] * 101)
