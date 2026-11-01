"""Discovery collections paginate without losing lineage or timer scope."""
from copy import deepcopy
from uuid import uuid4

from tests.integration.test_task_registration import registration
from tests.integration.test_trustgraph_workflow import provider as provider_fixture, run
from tests.integration.test_workflow import client as workflow_client, candidate

client = workflow_client
provider = provider_fixture


def collect(client, url, *, keys=("items",), params=None):
    result = {key: [] for key in keys}
    cursor, seen = None, set()
    while True:
        response = client.get(url, params={**(params or {}), "limit": 7,
                                          **({"cursor": cursor} if cursor else {})})
        assert response.status_code == 200, response.text
        page = response.json()
        assert sum(len(page[key]) for key in keys) <= 7
        for key in keys:
            result[key].extend(page[key])
        cursor = page["next_cursor"]
        if cursor is None:
            return result
        assert cursor not in seen
        seen.add(cursor)


def assert_limits(client, url, params=None):
    for limit in (0, 201):
        assert client.get(url, params={**(params or {}), "limit": limit}).status_code == 422
    assert client.get(url, params={**(params or {}), "cursor": str(uuid4())}).status_code == 422


def test_registered_task_discovery_defaults_to_fifty_and_returns_every_registration(client):
    p, _, request, first = registration(client)
    url = f"/api/v1/projects/{p['id']}/synthetic-tasks"
    expected = {first["id"]}
    for number in range(50):
        created = client.post(url, json={**request, "task_id": f"pagination-task-{number}"})
        assert created.status_code == 201, created.text
        expected.add(created.json()["id"])
    page = client.get(url).json()
    assert len(page["items"]) == 50 and page["next_cursor"]
    rows = collect(client, url)["items"]
    assert len(rows) == len(expected) == 51
    assert {row["id"] for row in rows} == expected
    assert_limits(client, url)


def test_trustgraph_discovery_shares_one_bounded_page_across_receipts_and_preparations(provider, client):
    studio, p, document, _ = provider
    receipt = run(client, p["id"], "trustgraph-ingestions", {"document_id": document["id"]})
    assert receipt["status"] == "succeeded", receipt
    # Populate historical discovery entries from valid controlled-provider records;
    # this fixture does not claim 26 real upstream submissions.
    with studio.db.session(write=True) as session:
        originals = {kind: studio.items(session, p["id"], kind)[0]
                     for kind in ("trustgraph_preparation", "trustgraph_ingestion")}
        for _ in range(25):
            for kind, record in originals.items():
                studio.add(session, p["id"], kind,
                           {key: deepcopy(value) for key, value in record.data.items() if key != "_payload"},
                           record.status)
        expected = {key: {row.id for row in studio.items(session, p["id"], kind)}
                    for key, kind in (("items", "trustgraph_ingestion"), ("preparations", "trustgraph_preparation"))}
    url = f"/api/v1/projects/{p['id']}/trustgraph-ingestions"
    page = client.get(url).json()
    assert page["configured"] is True
    assert len(page["items"]) + len(page["preparations"]) == 50
    assert page["next_cursor"]
    rows = collect(client, url, keys=("items", "preparations"))
    for key in expected:
        assert len(rows[key]) == len(expected[key]) == 26
        assert {row["id"] for row in rows[key]} == expected[key]
    assert_limits(client, url)


def test_review_session_pages_preserve_revision_and_actor_scope(client):
    p, revision = candidate(client)
    url = f"/api/v1/projects/{p['id']}/review-sessions"
    expected = set()
    for number in range(52):
        response = client.post(url, json={"revision_id": revision["revision_id"],
                                         "event": "start" if number % 2 == 0 else "end"})
        assert response.status_code == 201, response.text
        expected.add(response.json()["id"])
    params = {"revision_id": revision["revision_id"]}
    first = client.get(url, params=params).json()
    assert len(first["items"]) == 50 and first["next_cursor"]
    rows = collect(client, url, params=params)["items"]
    assert len(rows) == len(expected) == 52
    assert {row["id"] for row in rows} == expected
    assert all(row["revision_id"] == revision["revision_id"] for row in rows)
    assert_limits(client, url, params)
    other = client.post(f"/api/v1/projects/{p['id']}/proposals/{revision['id']}/revisions",
                        json={"parent_revision": 1, "structured_changes": {}, "rationale": "Separate timer scope"},
                        headers={"If-Match": "1"}).json()
    outside = client.post(url, json={"revision_id": other["revision_id"], "event": "start"}).json()
    assert client.get(url, params={**params, "cursor": outside["id"]}).status_code == 422


def test_registered_chunk_pages_keep_snapshot_provenance_and_reject_drift(client, monkeypatch):
    p, _ = candidate(client)
    studio = client.app.state.studio
    artifact = studio.artifacts.put(b'{"synthetic": "chunk discovery"}', "application/json")
    observation = {"chunk_uris": [f"urn:chunk:{number:04d}" for number in range(251)],
                   "source_id": str(uuid4()), "provenance_artifact": artifact,
                   "selection_required": True, "upstream_completion_supported": False}
    monkeypatch.setattr("oe_studio.trustgraph_workflow.list_chunks", lambda *args: deepcopy(observation))
    url = f"/api/v1/projects/{p['id']}/trustgraph-ingestions/{uuid4()}/chunks"
    first = client.get(url).json()
    assert len(first["chunk_uris"]) == 50 and first["next_cursor"]
    assert first["provenance_artifact"] == artifact
    assert first["upstream_completion_supported"] is False
    rows = collect(client, url, keys=("chunk_uris",))["chunk_uris"]
    assert rows == observation["chunk_uris"]
    maximum = client.get(url, params={"limit": 200}).json()
    assert len(maximum["chunk_uris"]) == 200 and maximum["next_cursor"]
    assert_limits(client, url)
    different = url.replace(url.split("/")[-2], str(uuid4()))
    assert client.get(different, params={"cursor": first["next_cursor"]}).status_code in (409, 422)
    observation["provenance_artifact"] = studio.artifacts.put(b'{"synthetic": "changed graph"}', "application/json")
    changed = client.get(url, params={"cursor": first["next_cursor"]})
    assert changed.status_code == 409, changed.text
    assert changed.json()["code"] == "chunk_discovery_changed"
