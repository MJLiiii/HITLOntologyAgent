"""Test the evidence comparison, not a mock of the real native editor exercise."""
import importlib.util
from pathlib import Path
import sqlite3
import subprocess


PATH = Path(__file__).resolve().parents[2] / "infra/portal/check_native_boundary.py"
SPEC = importlib.util.spec_from_file_location("native_boundary", PATH)
boundary = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(boundary)


def test_snapshot_detects_artifact_ref_and_approved_head_changes(tmp_path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    artifact = artifacts / "ontology.ttl"
    artifact.write_text("synthetic canonical bytes")
    git = tmp_path / "ontology.git"
    subprocess.run(["git", "init", "--bare", str(git)], check=True, capture_output=True)
    obj = subprocess.check_output(["git", f"--git-dir={git}", "hash-object", "-w", "--stdin"], input=b"synthetic object").decode().strip()
    with sqlite3.connect(tmp_path / "studio.sqlite") as db:
        db.execute("CREATE TABLE projects(id,approved_version_id,pending_publication_id)")
        db.execute("INSERT INTO projects VALUES ('project','approved',NULL)")
        db.execute("CREATE TABLE items(id,project_id,kind,status,data)")
        db.execute("INSERT INTO items VALUES ('version','project','version','approved','{}')")
    baseline = boundary.canonical_snapshot(tmp_path)
    assert baseline == boundary.canonical_snapshot(tmp_path)
    artifact.write_text("changed canonical bytes")
    assert boundary.canonical_snapshot(tmp_path)["artifacts"] != baseline["artifacts"]
    subprocess.run(["git", f"--git-dir={git}", "update-ref", "refs/tags/extra", obj], check=True)
    assert boundary.canonical_snapshot(tmp_path)["git_refs"] != baseline["git_refs"]
    with sqlite3.connect(tmp_path / "studio.sqlite") as db:
        db.execute("UPDATE projects SET approved_version_id='other'")
        db.execute("UPDATE items SET data='changed'")
    changed = boundary.canonical_snapshot(tmp_path)
    assert changed["projects"] != baseline["projects"]
    assert changed["canonical_records_sha256"] != baseline["canonical_records_sha256"]
