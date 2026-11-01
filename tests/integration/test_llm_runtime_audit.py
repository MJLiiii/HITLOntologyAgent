"""Credential echo cannot become an answer or a persisted Studio candidate."""
import json
from uuid import uuid4

import httpx
import pytest

from oe_studio.model import ModelClient
from tests.integration.test_workflow import client as workflow_client, project

client = workflow_client


@pytest.mark.parametrize("kind", ["question", "proposal"])
def test_provider_credential_echo_is_rejected_before_studio_output(client, monkeypatch, kind):
    secret = "synthetic-provider-key-echo-guard"
    p = project(client)
    studio = client.app.state.studio
    studio.settings.model_url = "http://localhost:11434"
    studio.settings.model_name = "fixture-model"
    studio.settings.model_api_key = secret
    requests = []

    def serve(request):
        requests.append(request)
        context = json.loads(json.loads(request.content)["messages"][1]["content"])
        if kind == "question":
            output = {"answer": secret, "evidence_ids": [], "triple_indices": [],
                      "unresolved_points": ["Synthetic output fixture"]}
        else:
            output = {"summary": secret, "changes": [{"operation": "add", "triple": {
                "subject": "https://example.org/Echo", "predicate": "http://www.w3.org/2000/01/rdf-schema#comment",
                "object": "Synthetic", "object_type": "literal"},
                "evidence_ids": [context["evidence"][0]["id"]], "rationale": "Synthetic source-backed fixture"}]}
        return httpx.Response(200, json={"done": True, "model": "fixture-model", "message": {
            "role": "assistant", "content": json.dumps(output)}, "prompt_eval_count": 12, "eval_count": 8})

    monkeypatch.setattr("oe_studio.model.ModelClient", lambda settings: ModelClient(settings, httpx.MockTransport(serve)))
    body = {"question": "Who owns Payroll Service?"} if kind == "question" else {
        "corpus_snapshot_id": p["corpus_snapshot_id"], "instruction": "Model synthetic service ownership"}
    root = f"/api/v1/projects/{p['id']}"
    queued = client.post(root + f"/{kind}-jobs", json=body,
                         headers={"Idempotency-Key": str(uuid4())})
    assert queued.status_code == 202, queued.text
    result = client.get(queued.json()["status_url"])
    assert result.json()["status"] == "failed" and result.json()["result"] is None
    assert len(requests) == 1
    records = client.get(root + "/generation-runs")
    assert records.status_code == 200
    assert secret not in records.text + result.text
    assert records.json()["items"][0]["status"] == "failed"
    assert "[REDACTED]" in records.text
    with studio.db.session() as session:
        generation = studio.body(studio.items(session, p["id"], "generation")[0])
        assert secret not in json.dumps(generation)
        assert generation.get("output") is None
        assert not studio.items(session, p["id"], "proposal")
