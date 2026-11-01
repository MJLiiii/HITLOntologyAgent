"""Human-registered synthetic tasks; real study activation is intentionally absent."""
import json

from .artifacts import canonical_json, digest
from .auth import human
from .errors import Problem
from .experiments import FrozenSyntheticTask, execute_synthetic_task, freeze_synthetic_task


def register(studio, project_id, request, actor):
    human(actor)
    with studio.db.session(write=True) as session:
        project = studio.project(session, project_id)
        if project.domain != "demo" or not project.data.get("scope_accepted"):
            raise Problem(409, "synthetic_scope_required", "Accept a synthetic scope before registering an engineering task")
        if project.pending_publication_id:
            raise Problem(409, "publication_pending", "Finish pending publication before registering a task")
        revision = studio.revision(session, project_id, request.proposal_id, request.revision)
        studio.exact_bundle(revision, request.bundle_digest)
        if (revision != studio.revisions(session, project_id, request.proposal_id)[-1]
                or revision.data["base_version_id"] != project.approved_version_id
                or revision.data["manifest"]["scope_digest"] != project.data["scope_digest"]
                or revision.data["manifest"]["engine_configuration"] != studio.engine_configuration()
                or revision.data["manifest"]["assessment_mappings_digest"] != project.data.get("assessment_mappings_digest", digest([]))):
            raise Problem(409, "stale_task_inputs", "Register the latest revision under the current base, scope, mappings and engine configuration")
        if any(item.data["task_id"] == request.task_id for item in studio.items(session, project_id, "synthetic_task")):
            raise Problem(409, "task_id_exists", "Task IDs are immutable and unique within this project; use a new ID for a changed task")
        data = revision.data
        evidence_ids = list(dict.fromkeys(data["evidence_ids"] + [e["id"] for e in data["manifest"].get("mapping_evidence", [])]))
        evidence = []
        for identity in evidence_ids:
            ref = studio.evidence(session, project_id, identity)
            document = studio.get(session, project_id, ref["document_id"], "document")
            if not ref["resolved"] or document.data["classification"] != "synthetic":
                raise Problem(409, "synthetic_evidence_required", "Registered engineering tasks require resolved, explicitly synthetic sources")
            evidence.append({"id": ref["id"], "quote": ref["quote"], "resolved": True, "classification": "synthetic",
                "source_sha256": ref["source_hash"], "document_id": ref["document_id"], "locator": ref["locator"]})
        tests = json.loads(studio.artifacts.get_verified(data["tests"]))
        for test in tests:
            if test.get("oracle_status") == "accepted":
                decision = studio.get(session, project_id, test["oracle_decision_id"], "oracle_decision")
                if decision.data["decision"] != "accept":
                    raise Problem(409, "oracle_not_accepted", "Additional task tests require a recorded acceptance")
        required = {test["test_id"]: test for test in tests}
        questions = [{**question, "expected": required[question["id"]]["expected"]}
                     for question in json.loads(studio.artifacts.get_verified(data["questions"]))]
        base = studio.artifacts.get_verified(studio.get(session, project_id, project.approved_version_id, "version").data["ontology"]).decode() if project.approved_version_id else ""
        packet = freeze_synthetic_task(task_id=request.task_id, instruction=request.instruction, bundle_digest=data["bundle_digest"],
            base_ontology=base, seed_ontology=studio.artifacts.get_verified(data["ontology"]).decode(),
            questions=questions, tests=tests, shapes_ttl=studio.artifacts.get_verified(data["shapes"]).decode(),
            fixtures_ttl=studio.artifacts.get_verified(data["fixtures"]).decode(), evidence=evidence,
            mappings=json.loads(studio.artifacts.get_verified(data["mappings"])))
        context = {"base_version_id": project.approved_version_id, "corpus_snapshot_id": data["corpus_snapshot_id"],
                   "scope_digest": project.data["scope_digest"], "evidence_ids": evidence_ids,
                   "proposal_evidence_ids": data["evidence_ids"],
                   "engine_configuration": data["manifest"]["engine_configuration"],
                   "assessment_mappings_digest": data["manifest"]["assessment_mappings_digest"]}
        item = studio.add(session, project_id, "synthetic_task", {
            **request.model_dump(), "protocol_id": "synthetic-task-v1", "classification": "synthetic",
            "revision_id": revision.id, "registration_digest": packet.digest,
            "packet": studio.artifacts.put(packet.packet_json.encode(), "application/json"),
            "project_context": context, "actor": actor}, "registered")
        studio.audit(session, project_id, actor, "synthetic_task_registered", item.id, item.data)
        return studio.body(item)


def execute(studio, project_id, payload, actor):
    with studio.db.session() as session:
        project = studio.project(session, project_id)
        registration = studio.get(session, project_id, payload["registration_id"], "synthetic_task")
        context = {**registration.data["project_context"], "registration_id": registration.id}
        if registration.data["registration_digest"] != payload["registration_digest"]:
            raise Problem(409, "registration_changed", "The request must match the exact registered task digest")
        if (project.domain != "demo" or not project.data.get("scope_accepted")
                or context["scope_digest"] != project.data["scope_digest"]
                or context["engine_configuration"] != studio.engine_configuration()):
            raise Problem(409, "registered_configuration_changed", "The registered scope or engine configuration changed; freeze a new task")
        if not all(studio.evidence(session, project_id, identity)["resolved"] for identity in context["evidence_ids"]):
            raise Problem(409, "unresolved_evidence", "Registered source evidence was changed or withdrawn")
        packet = FrozenSyntheticTask(studio.artifacts.get_verified(registration.data["packet"]).decode())
    runs = execute_synthetic_task(packet, registration_digest=payload["registration_digest"], settings=studio.settings,
                                 condition=payload["condition"], replicate_ids=payload["replicate_ids"])
    with studio.db.session(write=True) as session:
        results = []
        for run in runs:
            ref = studio.artifacts.put(canonical_json(run), "application/json")
            results.append(studio.body(studio.add(session, project_id, "experiment", {
                **run, "sealed_record": ref, "project_context": context}, run["status"], run["id"])))
        return studio._complete_job(session, payload, {"runs": results})
