from hashlib import sha256
from uuid import uuid4
from fastapi.testclient import TestClient
from oe_studio.main import create_app
from oe_studio.settings import Settings


def test_pdf_extraction_has_verified_original_page_and_span(tmp_path, monkeypatch):
    source = b"%PDF-1.7\ncontrolled parser fixture"
    text = "Payroll Service is owned by Operations Team."
    monkeypatch.setattr("oe_studio.workflow.run_pdf_extraction", lambda content: {
        "status": "completed", "source_sha256": sha256(content).hexdigest(), "page_count": 1,
        "text": text, "text_sha256": sha256(text.encode()).hexdigest(),
        "pages": [{"page": 1, "status": "completed", "text": text, "char_start": 0, "char_end": len(text)}],
        "diagnostics": [], "engine": {"name": "fixture"}})
    app = create_app(Settings(data_dir=tmp_path, eager_jobs=True))
    with TestClient(app) as c:
        c.get("/api/v1/session", headers={"X-OE-Session-Token": app.state.bootstrap_token})
        p = c.get("/api/v1/projects").json()["items"][0]["id"]
        root = f"/api/v1/projects/{p}"
        doc = c.post(root + "/documents", files={"file": ("policy.pdf", source, "application/pdf")}, data={"title": "PDF policy"})
        assert doc.status_code == 201, doc.text
        job = c.post(root + "/ingestions", json={"document_id": doc.json()["id"]}, headers={"Idempotency-Key": str(uuid4())}).json()
        result = c.get("/api/v1/jobs/" + job["job_id"]).json()
        assert result["status"] == "succeeded" and result["result"]["status"] == "completed"
        corpus = c.post(root + "/corpus-snapshots", json={"ingestion_run_ids": [result["result"]["ingestion_run_id"]]})
        assert corpus.status_code == 201, corpus.text
        evidence = c.get(root + "/evidence/" + corpus.json()["evidence_ids"][0]).json()
        assert evidence["resolved"] is True and evidence["quote"] == text
        assert evidence["page"] == 1 and evidence["source_hash"] == sha256(source).hexdigest()
        (app.state.studio.artifacts.root / evidence["extraction_text"]["sha256"]).write_text("changed")
        assert c.get(root + "/evidence/" + evidence["id"]).json()["resolved"] is False


def test_incomplete_pdf_is_retained_and_cannot_enter_corpus(tmp_path, monkeypatch):
    monkeypatch.setattr("oe_studio.workflow.run_pdf_extraction", lambda content: {
        "status": "unsupported", "source_sha256": sha256(content).hexdigest(), "page_count": 1,
        "text": "", "pages": [{"page": 1, "status": "unsupported", "diagnostics": ["No text; OCR required"]}],
        "diagnostics": [{"code": "incomplete", "message": "Incomplete extraction"}], "engine": {"name": "fixture"}})
    app = create_app(Settings(data_dir=tmp_path, eager_jobs=True))
    with TestClient(app) as c:
        c.get("/api/v1/session", headers={"X-OE-Session-Token": app.state.bootstrap_token})
        p = c.get("/api/v1/projects").json()["items"][0]["id"]
        root = f"/api/v1/projects/{p}"
        doc = c.post(root + "/documents", files={"file": ("scan.pdf", b"%PDF-1.7\nfixture", "application/pdf")}, data={"title": "Scanned PDF"})
        assert doc.status_code == 201, doc.text
        job = c.post(root + "/ingestions", json={"document_id": doc.json()["id"]}, headers={"Idempotency-Key": str(uuid4())}).json()
        result = c.get("/api/v1/jobs/" + job["job_id"]).json()["result"]
        assert result["status"] == "incomplete" and result["extraction"]["status"] == "unsupported"
        assert result["extraction"]["diagnostics"] == ["Incomplete extraction", "Page 1: No text; OCR required"]
        assert c.post(root + "/corpus-snapshots", json={"ingestion_run_ids": [result["ingestion_run_id"]]}).status_code == 409
        docs = c.get(root + "/documents").json()["items"]
        assert next(d for d in docs if d["id"] == doc.json()["id"])["status"] == "incomplete"
