import hashlib
import importlib.util
from pathlib import Path
import pytest


def test_download_integrity_rejects_modified_artifact(tmp_path):
    path = Path(__file__).resolve().parents[2] / "scripts/setup_model.py"
    spec = importlib.util.spec_from_file_location("setup_model", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    artifact = tmp_path / "artifact"
    artifact.write_bytes(b"pinned content")
    sha = hashlib.sha256(b"pinned content").hexdigest()
    module.verify_file(artifact, sha)
    artifact.write_bytes(b"changed content")
    with pytest.raises(ValueError, match="SHA-256"):
        module.verify_file(artifact, sha)
