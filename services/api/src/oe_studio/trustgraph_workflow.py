"""Persist upstream intentions and freeze explicitly selected, verified source passages.

The upstream mutable graph is a candidate sandbox. It never writes approved state.
"""
import asyncio
import hashlib
import json
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .artifacts import digest
from .errors import Problem
from .integrations.trustgraph.contracts import (
    Artifact, Binding, DocumentRegistration, IngestReceipt, IngestRequest, PreparedIngestion,
)
from .integrations.trustgraph.gateway import PinnedTrustGraphGateway

REMOTE_DEADLINE_SECONDS = 180


def remote(coroutine):
    async def bounded():
        try:
            return await asyncio.wait_for(coroutine, timeout=REMOTE_DEADLINE_SECONDS)
        except TimeoutError as exc:
            raise Problem(504, "trustgraph_deadline", "TrustGraph exceeded the operation deadline; inspect retained preparation before recovery") from exc
    return asyncio.run(bounded())


class ProjectConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    binding: Binding
    seed_mode: Literal["ordinary", "approved_ontology"]
    expected_configuration: dict
    extraction_profile_id: str | None = Field(default=None, min_length=1, max_length=120)
    extraction_profile_revision: str | None = Field(default=None, pattern=r"^(sha256:)?[a-f0-9]{64}$")
    llm_session_id: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def complete_profile(self):
        if (self.extraction_profile_id is None) != (self.extraction_profile_revision is None):
            raise ValueError("profile binding requires ID and revision")
        return self

    def public(self):
        return self.model_dump(mode="json", exclude={"binding": {"token"}})


def _configurations(settings, project_id):
    path = settings.trustgraph_config_file
    if not path:
        raise Problem(409, "trustgraph_not_configured", "TrustGraph is not configured for this local server")
    try:
        if path.stat().st_size > 2_097_152:
            raise ValueError("oversized configuration")
        configured = [ProjectConfiguration.model_validate(row) for row in json.loads(path.read_text())["projects"]]
        identities = [(row.binding.project_id, row.extraction_profile_id, row.extraction_profile_revision) for row in configured]
        if len(set(identities)) != len(identities):
            raise ValueError("duplicate project/profile binding")
        flows = [(row.binding.workspace, row.binding.flow) for row in configured]
        if len(set(flows)) != len(flows):
            raise ValueError("flow reused across server bindings")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise Problem(409, "trustgraph_configuration", "The private server TrustGraph configuration is invalid") from exc
    authorized = [row for row in configured if str(row.binding.project_id) == project_id]
    if not authorized:
        raise Problem(403, "trustgraph_project_denied", "No server TrustGraph binding authorizes this project")
    return authorized


def _select_configuration(settings, project_id, profile=None, frozen_configuration=None):
    authorized = _configurations(settings, project_id)
    if frozen_configuration is not None:
        config = next((row for row in authorized if row.public() == frozen_configuration), None)
        if config is None:
            raise Problem(409, "trustgraph_binding_changed", "The recorded TrustGraph binding is no longer authorized or has changed")
    else:
        profile_key = (profile["id"], profile["revision"]) if profile else (None, None)
        config = next((row for row in authorized if (row.extraction_profile_id, row.extraction_profile_revision) == profile_key), None)
        if config is None:
            raise Problem(409, "trustgraph_profile_binding", "No preconfigured TrustGraph flow matches the selected extraction profile revision")
    if profile is not None and (config.extraction_profile_id, config.extraction_profile_revision) != (profile["id"], profile["revision"]):
        raise Problem(409, "trustgraph_profile_binding", "The frozen extraction profile does not match its TrustGraph binding")
    if profile and profile.get("provider") == "opencode_go" and not config.llm_session_id:
        raise Problem(409, "trustgraph_session_binding", "OpenCode Go extraction requires a dedicated flow with a frozen session")
    if profile:
        try:
            _verify_profile_markers(config, profile)
        except (AttributeError, KeyError, TypeError, ValueError):
            raise Problem(409, "trustgraph_profile_markers", "The inspected extraction profile/session marker configuration is invalid") from None
    return config


def _verify_profile_markers(config, profile):
    """Bind private mappings to values inspected by the remote drift guard."""
    markers = {"oe-llm-profile-id": profile["id"], "oe-llm-profile-revision": profile["revision"],
               "oe-llm-session-id": config.llm_session_id or ""}
    expected, binding = config.expected_configuration, config.binding
    flow = expected.get("flow", {}).get(binding.flow, {})
    params = flow.get("parameters", {})
    blueprint_name = flow.get("blueprint-name")
    blueprint = expected.get("flow-blueprint", {}).get(blueprint_name, {})
    checked = 0
    valid = all(params.get(key) == value for key, value in markers.items())
    for area in ("flow", "blueprint"):
        for declaration in blueprint.get(area, {}):
            processor, variant = declaration.split(":", 1)
            if "text-completion" not in processor:
                continue
            variant = variant.replace("{id}", binding.flow).replace("{workspace}", binding.workspace).replace("{blueprint}", blueprint_name)
            for key, value in params.items():
                variant = variant.replace("{" + key + "}", str(value))
            processor_params = expected.get("processor:" + processor, {}).get(variant, {}).get("parameters", {})
            valid = valid and all(processor_params.get(key) == value for key, value in markers.items())
            checked += 1
    if not valid or not checked:
        raise Problem(409, "trustgraph_profile_markers", "The inspected flow and completion processor profile/session markers do not match the frozen extraction binding")


def freeze_profile_binding(settings, project_id, profile):
    """Freeze an authorized public binding at enqueue time; never serialize tokens."""
    return _select_configuration(settings, project_id, profile).public()


def provider(studio, project_id, document_id, *, profile=None, frozen_configuration=None):
    config = _select_configuration(studio.settings, project_id, profile, frozen_configuration)
    with studio.db.session() as session:
        document = studio.get(session, project_id, document_id, "document")
        if document.status == "withdrawn":
            raise Problem(409, "source_withdrawn", "The source was withdrawn")
        ref = Artifact(**document.data["artifact"])
        if ref.media_type != "text/plain":
            raise Problem(422, "trustgraph_source_type", "This verified TrustGraph path accepts UTF-8 text; use local ingestion for PDFs")
        studio.artifacts.get_verified(ref.model_dump())
        registration = DocumentRegistration(project_id=project_id, source_id=document.id, artifact=ref,
            upstream_document_id=f"urn:oe:document:{project_id}:{document.id}:{ref.sha256}",
            source_uri=f"urn:oe:source:{document.id}", title=document.data["title"])
    gateway = PinnedTrustGraphGateway(artifacts=studio.artifacts, bindings=[config.binding], documents=[registration])
    return gateway, config, registration


def _seed(studio, session, project_id, config):
    project = studio.project(session, project_id)
    if config.seed_mode == "ordinary":
        return None, None
    if not project.data.get("scope_accepted") or not project.approved_version_id:
        raise Problem(409, "approved_seed_required", "Seeded ingestion requires an accepted scope and a human-approved ontology version")
    version = studio.get(session, project_id, project.approved_version_id, "version")
    if version.status != "approved":
        raise Problem(409, "approved_seed_required", "Only a human-approved ontology can seed ingestion")
    studio.artifacts.get_verified(version.data["ontology"])
    return UUID(version.id), Artifact(**version.data["ontology"])


def _historical_seed(studio, session, project_id, prepared):
    if prepared.seed_mode == "approved_ontology":
        version = studio.get(session, project_id, str(prepared.approved_version_id), "version")
        if version.status != "approved" or Artifact(**version.data["ontology"]) != prepared.approved_ontology:
            raise Problem(409, "approved_seed_changed", "The recorded historical seed is no longer an intact approved version")
        studio.artifacts.get_verified(version.data["ontology"])


def ingest(studio, project_id, payload, actor):
    recovery = payload.get("preparation_id")
    if recovery:
        with studio.db.session() as session:
            record = studio.get(session, project_id, recovery, "trustgraph_preparation")
            prepared = PreparedIngestion.model_validate(record.data["prepared"])
            _historical_seed(studio, session, project_id, prepared)
            document_id = record.data["document_id"]
        gateway, config, registration = provider(studio, project_id, document_id,
            profile=record.data.get("llm_profile"), frozen_configuration=record.data.get("server_configuration"))
    else:
        document_id = payload["document_id"]
        profile = payload.get("_resolved_llm_profile")
        gateway, config, registration = provider(studio, project_id, document_id, profile=profile,
            frozen_configuration=payload.get("_trustgraph_configuration"))
        with studio.db.session() as session:
            version_id, ontology = _seed(studio, session, project_id, config)
        request = IngestRequest(project_id=project_id, source_id=document_id, artifact=registration.artifact,
            seed_digest=config.binding.seed_digest, config_digest=config.binding.config_digest,
            idempotency_key=payload["_job_id"])
        prepared = remote(gateway.prepare_ingestion(request, approved_version_id=version_id,
            approved_ontology=ontology, expected_configuration=config.expected_configuration))
        with studio.db.session(write=True) as session:
            studio._running_job(session, payload["_job_id"])
            if studio.get(session, project_id, document_id, "document").status == "withdrawn":
                raise Problem(409, "source_withdrawn", "Source withdrawn during preparation; no source was submitted")
            current_id, current_ontology = _seed(studio, session, project_id, config)
            if (current_id, current_ontology) != (version_id, ontology):
                raise Problem(409, "seed_changed", "Approved seed changed during preparation; no source was submitted")
            if profile and profile.get("provider") == "opencode_go":
                # Database.session(write=True) serializes writes with BEGIN
                # IMMEDIATE / a PostgreSQL transaction advisory lock. Reserve
                # the dedicated run session atomically with its preparation.
                for prior in studio.items(session, project_id, "trustgraph_preparation"):
                    studio.body(prior)
                    if prior.data.get("llm_session_id") == config.llm_session_id:
                        raise Problem(409, "trustgraph_session_reused", "This dedicated extraction session already has a preparation; recover it or provision a new flow and session")
            record = studio.add(session, project_id, "trustgraph_preparation", {
                "job_id": payload["_job_id"], "document_id": document_id,
                "prepared": prepared.model_dump(mode="json"), "actor": actor,
                "server_configuration": config.public(), "llm_profile": profile,
                "llm_session_id": config.llm_session_id}, "submission_started")
            studio.audit(session, project_id, actor, "trustgraph_prepared", record.id, record.data)
    # The immutable intent is committed before any upstream mutation. Recovery
    # only reattaches a proven existing submission; absence never triggers replay.
    with studio.db.session() as session:
        studio._running_job(session, payload["_job_id"])
    receipt = remote(gateway.ingest_prepared(prepared, may_have_submitted=bool(recovery)))
    with studio.db.session(write=True) as session:
        prior = next((i for i in studio.items(session, project_id, "trustgraph_ingestion")
                      if i.data["preparation_id"] == record.id), None)
        result = prior or studio.add(session, project_id, "trustgraph_ingestion", {
            "preparation_id": record.id, "document_id": document_id, "job_id": payload["_job_id"],
            "llm_profile": record.data.get("llm_profile"), "llm_session_id": record.data.get("llm_session_id"),
            "receipt": receipt.model_dump(mode="json"), "upstream_completion_supported": False}, receipt.status)
        return studio._complete_job(session, payload, studio.body(result))


def _registered(studio, project_id, ingestion_id):
    with studio.db.session() as session:
        record = studio.get(session, project_id, ingestion_id, "trustgraph_ingestion")
        preparation = studio.get(session, project_id, record.data["preparation_id"], "trustgraph_preparation")
        prepared = PreparedIngestion.model_validate(preparation.data["prepared"])
        _historical_seed(studio, session, project_id, prepared)
        receipt = IngestReceipt.model_validate(record.data["receipt"])
    gateway, _, registration = provider(studio, project_id, record.data["document_id"],
        profile=preparation.data.get("llm_profile"), frozen_configuration=preparation.data.get("server_configuration"))
    return gateway, prepared, receipt, registration


def list_chunks(studio, project_id, ingestion_id):
    gateway, prepared, receipt, _ = _registered(studio, project_id, ingestion_id)
    return remote(gateway.list_registered_chunks(prepared, receipt))


def import_snapshot(studio, project_id, payload, actor):
    selected = payload["chunk_uris"]
    if len(set(selected)) != len(selected) or any(not isinstance(uri, str) or not 1 <= len(uri) <= 2048 for uri in selected):
        raise Problem(422, "invalid_selection", "Select unique bounded registered chunk URIs")
    gateway, prepared, receipt, registration = _registered(studio, project_id, payload["ingestion_run_id"])
    corpus_id = uuid5(NAMESPACE_URL, "urn:oe:trustgraph-snapshot:" + payload["_job_id"])
    imported = remote(gateway.import_snapshot(prepared, receipt, chunk_uris=tuple(selected), corpus_id=corpus_id))
    if (imported.id != corpus_id or str(imported.project_id) != project_id or not imported.chunks
            or {chunk.upstream_chunk_uri for chunk in imported.chunks} != set(selected)
            or imported.source_artifact != registration.artifact):
        raise Problem(409, "snapshot_scope", "Verified snapshot does not match the registered selection")
    with studio.db.session(write=True) as session:
        document = studio.get(session, project_id, str(registration.source_id), "document")
        if document.status == "withdrawn":
            raise Problem(409, "source_withdrawn", "The source was withdrawn before snapshot freeze")
        original = studio.artifacts.get_verified(document.data["artifact"]).decode("utf-8-sig").replace("\r\n", "\n")
        evidence_ids = []
        for chunk in imported.chunks:
            if (chunk.source_id != registration.source_id or chunk.source_artifact != registration.artifact
                    or chunk.quote != original[chunk.span_start:chunk.span_end]
                    or studio.artifacts.get_verified(chunk.normalized_source_artifact.model_dump()).decode() != original
                    or studio.artifacts.get_verified(chunk.chunk_artifact.model_dump()).decode() != chunk.quote):
                raise Problem(409, "snapshot_integrity", "Imported source passage does not match the immutable source")
            for ref in (chunk.upstream_chunk_artifact, chunk.metadata_artifact):
                studio.artifacts.get_verified(ref.model_dump())
            evidence = studio.add(session, project_id, "evidence", {
                "document_id": document.id, "title": document.data["title"], "quote": chunk.quote,
                "locator": f"TrustGraph selection · Characters {chunk.span_start}–{chunk.span_end}",
                "span_start": chunk.span_start, "span_end": chunk.span_end, "source_hash": registration.artifact.sha256,
                "chunk": chunk.chunk_artifact.model_dump(), "content_hash": hashlib.sha256(chunk.quote.encode()).hexdigest(),
                "adapter": "trustgraph_snapshot", "resolved": True, "provenance": chunk.model_dump(mode="json")}, item_id=str(chunk.evidence_id))
            evidence_ids.append(evidence.id)
        for ref in (imported.manifest_artifact, imported.provenance_artifact, imported.configuration_artifact):
            studio.artifacts.get_verified(ref.model_dump())
        manifest = {"ingestion_run_ids": [payload["ingestion_run_id"]], "document_ids": [document.id],
            "evidence_ids": evidence_ids, "provider": "trustgraph", "selection_kind": imported.selection_kind,
            "upstream_completion_supported": False, "provider_snapshot": imported.model_dump(mode="json")}
        corpus = studio.add(session, project_id, "corpus", {**manifest, "digest": digest(manifest)}, "frozen", str(corpus_id))
        studio.project(session, project_id).corpus_snapshot_id = corpus.id
        studio.audit(session, project_id, actor, "trustgraph_selection_frozen", corpus.id, manifest)
        return studio._complete_job(session, payload, studio.body(corpus))
