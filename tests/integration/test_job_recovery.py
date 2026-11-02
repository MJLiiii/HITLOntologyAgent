"""Process-loss checks use synthetic stores and never create study observations."""
from tests.llm_fixtures import configure_studio_model
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from oe_studio.db import Job
from oe_studio.demo import ONTOLOGY
from oe_studio.errors import Problem
from oe_studio.settings import Settings
from oe_studio.workflow import Studio


class ProcessLost(BaseException):
    pass


ACTOR = {"kind": "service", "subject": "recovery-fixture", "roles": ["researcher"]}


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr("oe_studio.workflow.run_validation", lambda ttl, **kw: {
        "id": str(uuid4()), "status": "passed", "bundle_digest": kw["bundle_digest"], "cases": []})
    monkeypatch.setattr("oe_studio.workflow.run_assessment", lambda ttl, **kw: {
        "id": str(uuid4()), "status": "completed", "bundle_digest": kw["bundle_digest"]})
    studio = Studio(Settings(_env_file=None, llm_config_file=None, data_dir=tmp_path, eager_jobs=False))
    with studio.db.session() as session:
        from oe_studio.db import Project
        from sqlalchemy import select
        project = session.scalar(select(Project))
    return studio, project


@pytest.mark.parametrize("kind,method", [
    ("proposal", "create_proposal"), ("seed-import", "seed_import"),
    ("test-generation", "generate_tests"), ("validation", "validate_job"),
    ("assessment", "assessment_job"),
])
def test_effect_and_job_result_survive_the_same_commit(store, monkeypatch, kind, method):
    studio, project = store
    payload = {"instruction": "Create the synthetic source-backed ontology", "corpus_snapshot_id": project.corpus_snapshot_id}
    if kind == "seed-import":
        payload = {"ontology_ttl": ONTOLOGY, "rationale": "Synthetic recovery fixture", "corpus_snapshot_id": project.corpus_snapshot_id}
    elif kind not in {"proposal", "seed-import"}:
        created = studio.create_proposal(project.id, payload, ACTOR)
        payload = {"proposal_id": created["proposal_id"], "revision": 1}
        if kind in {"validation", "assessment"}:
            payload["bundle_digest"] = created["bundle_digest"]
    handle = studio.create_job(project.id, kind, payload, "crash-after-effect", ACTOR)
    original = getattr(studio, method)
    committed = []

    def lose_process(*args, **kwargs):
        committed.append(original(*args, **kwargs))
        raise ProcessLost()

    monkeypatch.setattr(studio, method, lose_process)
    with pytest.raises(ProcessLost):
        studio.execute_job(handle["job_id"])
    restarted = Studio(studio.settings)
    with restarted.db.session(write=True) as session:
        job = session.get(Job, handle["job_id"])
        if job.status == "running":
            job.lease_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    restarted.work_once()
    with restarted.db.session() as session:
        job = session.get(Job, handle["job_id"])
        assert job.status == "succeeded", "A committed effect must not be reported as an abandoned job"
        assert job.result == committed[0]
        assert job.attempt == 1
    again = restarted.create_job(project.id, kind, payload, "crash-after-effect", ACTOR)
    assert again["job_id"] == handle["job_id"]


def test_lost_lease_cannot_commit_a_late_proposal(store, monkeypatch):
    studio, project = store
    payload = {"instruction": "Create seed", "corpus_snapshot_id": project.corpus_snapshot_id}
    handle = studio.create_job(project.id, "proposal", payload, "lost-lease", ACTOR)
    with studio.db.session(write=True) as session:
        job = session.get(Job, handle["job_id"])
        job.status = "running"
        job.lease_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    with pytest.raises(Problem, match="lease"):
        studio.create_proposal(project.id, {**payload, "_job_id": handle["job_id"]}, ACTOR)
    with studio.db.session() as session:
        assert not studio.items(session, project.id, "proposal")
        assert not studio.items(session, project.id, "revision")


def test_repair_revision_attempt_and_result_commit_together(store, monkeypatch):
    from rdflib import Graph, URIRef, RDFS
    studio, project = store
    graph = Graph().parse(data=ONTOLOGY, format="turtle")
    graph.remove((URIRef("https://example.org/oe-demo/CriticalService"), RDFS.subClassOf, None))
    graph.remove((URIRef("https://example.org/oe-demo/hasOwner"), RDFS.domain, None))
    proposal = studio.seed_import(project.id, {"ontology_ttl": graph.serialize(format="turtle"),
        "rationale": "Synthetic broken hierarchy fixture", "corpus_snapshot_id": project.corpus_snapshot_id}, ACTOR)
    with studio.db.session(write=True) as session:
        revision = studio.revision(session, project.id, proposal["proposal_id"], 1)
        studio.add(session, project.id, "validation", {"revision_id": revision.id, "status": "failed",
            "bundle_digest": revision.data["bundle_digest"], "cases": [{"id": "CQ-01", "status": "failed"}]}, "failed")
    handle = studio.create_job(project.id, "repair", proposal, "repair-crash", ACTOR)
    original = studio.revise

    def lose_process(*args, **kwargs):
        original(*args, **kwargs)
        raise ProcessLost()

    monkeypatch.setattr(studio, "revise", lose_process)
    with pytest.raises(ProcessLost):
        studio.execute_job(handle["job_id"])
    restarted = Studio(studio.settings)
    with restarted.db.session() as session:
        job = session.get(Job, handle["job_id"])
        assert job.status == "succeeded"
        assert job.result["revision"] == 2 and job.result["repair_attempt"] == 1
        assert len(restarted.revisions(session, project.id, proposal["proposal_id"])) == 2
        attempts = restarted.items(session, project.id, "repair_attempt")
        assert len(attempts) == 1 and attempts[0].status == "completed"
        assert len(restarted.items(session, project.id, "repair_result")) == 1


def test_generation_crash_retains_output_without_replay_or_duplicate_revision(store, monkeypatch):
    studio, project = store
    configure_studio_model(studio, monkeypatch)
    def model(self, system, context, schema):
        return schema.model_validate({"summary": "Synthetic service declaration", "changes": [{"operation": "add",
            "triple": {"subject": "https://example.org/oe-demo/Service", "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "object": "http://www.w3.org/2002/07/owl#Class"},
            "evidence_ids": [context["evidence"][0]["id"]], "rationale": "The source names a service"}]}), {"provider": "fixture"}
    monkeypatch.setattr("oe_studio.model.ModelClient.generate", model)
    original = studio.generate
    def lose_process(*args, **kwargs):
        original(*args, **kwargs)
        raise ProcessLost()
    monkeypatch.setattr(studio, "generate", lose_process)
    payload = {"instruction": "Create the source-backed ontology", "corpus_snapshot_id": project.corpus_snapshot_id}
    handle = studio.create_job(project.id, "proposal", payload, "generation-crash", ACTOR)
    with pytest.raises(ProcessLost):
        studio.execute_job(handle["job_id"])
    restarted = Studio(studio.settings)
    with restarted.db.session(write=True) as session:
        session.get(Job, handle["job_id"]).lease_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    restarted.work_once()
    repeated = restarted.create_job(project.id, "proposal", payload, "generation-crash", ACTOR)
    assert repeated["job_id"] == handle["job_id"]
    with restarted.db.session() as session:
        job = session.get(Job, handle["job_id"])
        assert job.status == "failed" and job.result is None and job.attempt == 1
        generations = restarted.items(session, project.id, "generation")
        assert len(generations) == 1 and generations[0].data["job_id"] == job.id
        assert generations[0].data["output"]["summary"] == "Synthetic service declaration"
        assert not restarted.items(session, project.id, "revision")
