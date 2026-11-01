# Durable selected TrustGraph imports

This is a local synthetic engineering integration. No external study, expert observation, or real approval is implied by the simulated decisions in the verification fixtures.

## Design ruling

The application freezes **explicitly selected, verified source passages**, not an upstream job's claimed complete corpus. This uses the plan's mutable candidate-sandbox allowance: TrustGraph processes candidates, while Studio copies an immutable evidence snapshot into its existing content-addressed artifact and Job/Item ledger. Selecting a snapshot cannot approve or publish ontology changes.

The pinned 2.11.1 librarian has no terminal processing-success contract. An `add-processing` response and a processing metadata row prove submission only. Queue silence, elapsed time, successful retrieval, and disappearance of a processing row are never completion proofs. Every imported manifest retains `upstream_completion_supported: false`. A verified selection can be used as evidence; it makes no claim that every source, chunk or processor output was observed.

## Server-owned configuration

Install the exact optional SDK from `uv.lock` with `uv sync --frozen --extra trustgraph`. Set `OE_TRUSTGRAPH_CONFIG_FILE` to an operator-owned JSON file, with mode 0600. It has this shape; placeholders are not working credentials:

```json
{
  "projects": [{
    "binding": {
      "project_id": "<Studio project UUID>",
      "url": "https://<approved gateway host>",
      "workspace": "<fixed workspace>",
      "flow": "<fixed flow>",
      "collection": "<fixed collection>",
      "seed_digest": "<approved ontology SHA-256 or NO_SEED_DIGEST>",
      "config_digest": "<configuration_digest(expected_configuration)>",
      "token": "<private server credential>",
      "timeout": 60
    },
    "seed_mode": "approved_ontology",
    "expected_configuration": {
      "ontology": {"<seed key>": {"<exact projection>": "..."}},
      "flow": {"<flow ID>": {"<exact flow record>": "..."}},
      "flow-blueprint": {"<blueprint ID>": {"<exact blueprint>": "..."}},
      "prompt": {"<relevant prompt key>": {"<exact value>": "..."}},
      "processor:<processor ID>": {"<resolved variant>": {"<exact value>": "..."}}
    }
  }]
}
```

The client can request a registered document, recovery preparation, or explicit chunk selection. It cannot supply a URL, token, workspace, collection, flow or seed. The server resolves the source artifact and deterministic upstream document URI. Credentials are excluded from public binding digests, prepared manifests and results.

Configuration capture includes the selected flow and blueprint, every resolved processor variant, **all** workspace prompt records, and **all** workspace ontology records because the upstream selector sees all of them. IAM/configuration types outside the admitted allowlist are rejected; processor parameter names indicating secrets are rejected. Do not put credentials into prompt text or arbitrary metadata. The capture includes the complete prompt type because templates can affect extraction/synthesis; unrelated configuration types and IAM remain excluded. Private key names are rejected recursively across the selected configuration, including nested flow/processor fields.

The actual config API returns a global monotonic version. Preparation records that version and checks both exact selected values and the version before/after remote effects and import. Unrelated config writes, including a change later reverted, conservatively invalidate further remote work. This is a detected-change guard, not a transactional lock over the upstream processors; workers do not attest which config revision they actually consumed. Selected local artifacts remain readable after invalidation.

## Approved seed projection

For `approved_ontology`, Studio requires accepted scope and the current human-approved version. The helper verifies the actual approved ontology artifact's SHA-256 and requires its deterministic projection to equal the sole configured workspace ontology. Neither an extraction nor an operator-supplied version label creates approval.

`seed.project_seed_ontology` admits 1–100 named HTTP(S) classes/object/datatype properties, literal labels/comments, one named domain/range and one named superclass. Class IDs, property IDs, domain/range references and URI values use full IRIs consistently. Unsupported schema predicates/types on declared terms fail closed. This is a named schema projection; instance facts are intentionally not copied into the extraction vocabulary. It is not an arbitrary OWL serializer or a complete OWL equivalence claim. The full original approved artifact remains bound by hash.

For an ordinary extraction flow, use `imports.NO_SEED_DIGEST` and `seed_mode: "ordinary"`; there is no approved seed/version field. A flow containing `kg-extract-ontology` cannot masquerade as ordinary extraction.

## Durable state transitions

The public helper methods live on `PinnedTrustGraphGateway`; DTOs live in `contracts.py`, implementation in `imports.py`:

```python
prepared = await gateway.prepare_ingestion(
    request,
    approved_version_id=version_id,      # None for ordinary extraction
    approved_ontology=ontology_artifact, # None for ordinary extraction
    expected_configuration=configuration,
)
# Commit prepared.model_dump(mode="json") in the existing Job/Item ledger FIRST.
receipt = await gateway.ingest_prepared(prepared)
# Commit the returned receipt and terminal application job result atomically.

# Explicit recovery after a lost response or process:
receipt = await gateway.ingest_prepared(prepared, may_have_submitted=True)

hints = await gateway.list_registered_chunks(prepared, receipt)
snapshot = await gateway.import_snapshot(
    prepared, receipt,
    chunk_uris=tuple(explicit_user_selection), corpus_id=corpus_uuid,
)
```

`PreparedIngestion` contains the request, registered source, public binding digest, seed mode/approved artifact/version, selected configuration artifact/version, and sealed manifest artifact/digest. Its deterministic ID gives one processing URI. Each fresh ingestion intent also gets a distinct source document URI, even for the same source bytes, so earlier-run chunks cannot satisfy a later run's lineage checks. Recovery reconstructs the original URI. Recovery verifies an existing processing row's document, flow and collection and checks the original source bytes. It reattaches that submission without enqueueing it again. If the prior effect might have happened but no exact processing row is visible, recovery fails with `ambiguous_submission_requires_reconciliation`; absence is not permission to replay.

Studio exposes queued jobs at `/projects/{p}/trustgraph-ingestions`, `/trustgraph-ingestion-recoveries` and `/trustgraph-snapshots`. Preparation is committed before an external side effect. Source withdrawal, expired worker lease or a seed changed during preparation prevents enqueue. Recovery uses the original immutable preparation rather than creating an unbound replacement. These routes have no publication authority.

New seeded ingestions require the current approved head. Recovery/import may reattach an already submitted historical intent after that head advances, provided its original version still exists as approved and its exact ontology artifact matches the preparation. It must never relabel that old run with the new head or enqueue it again. Current source-withdrawal and configuration guards still apply.

## Selection and provenance checks

Chunk hints contain `chunk_uris`, `source_id`, `provenance_artifact`, `selection_required: true`, and `upstream_completion_supported: false`. A hint is not approval or a verified snapshot.

Import requires 1–50 explicit unique chunks and a source-graph query below its 2,000-row bound. It verifies the receipt's project/source/seed/configuration/processing identity, the submitted source bytes, exact librarian chunk parent metadata, the source graph's chunk-to-source relationship, and extraction subgraph/activity/agent lineage. The seeded profile requires observed ontology-extraction facts; the ordinary profile requires observed definition and relationship extraction facts. Sources yielding no such facts remain unimportable through this bounded profile, even when their raw text exists.

Each selected chunk must occur exactly once as a byte substring of its registered UTF-8 source. Import computes byte offsets locally, then removes a leading UTF-8 BOM and normalizes CRLF for the separate Unicode character offsets used by Studio. Repeated/ambiguous passages and transformed PDF chunks are rejected. Upstream `charOffset` is not trusted as a source span. The original source, raw upstream chunk, normalized source/chunk, metadata and source graph response all remain content-addressed artifacts. Literal `dt` datatype and `ln` language wire fields are preserved in extracted triples; unsupported terms fail closed.

`ImportedSnapshot` records `status: "verified_selection"`, `selection_kind: "explicit_registered_chunks"`, the selected chunks, source/config/provenance artifacts and a sealed manifest. Each `ImportedChunk` contains its evidence UUID, upstream URI, registered source/artifacts, exact quote, byte/Unicode spans, extraction subgraph URIs and normalized quoted facts. The application rechecks every quote against its local registered source before creating Evidence and Corpus Items. Future reads need no upstream connection. Withdrawal invalidates evidence eligibility without rewriting the copied artifacts.

Question reads default to the ontology version's historical source snapshot. An explicit frozen `corpus_snapshot_id` may be selected to read a new source corpus with the unchanged approved ontology; the response identifies that source choice. A candidate question cannot override its own frozen source scope. Neither reading nor importing changes approved Git refs.

## Reproduction and retained attempts

The pinned local synthetic processors must be running. Use a new output directory and a new flow ID; never overwrite a failed attempt:

```sh
PYTHONPATH=services/api/src .venv/bin/python infra/portal/check_studio_import.py \
  --output research/results/trustgraph-pipeline/studio-ledger-NEW \
  --flow-id oe-studio-ledger-NEW
```

The script creates a separate Studio store, runs real Jena and OntoCheck, records explicitly simulated review/publication inputs, prepares and submits through the real provider, reconstructs the recovery request, freezes a selected passage and checks a sourced read. It retains failed intermediate selection jobs while extraction is not yet observed. A `--resume-read` mode finishes local read checks on an already frozen selection without any new upstream effect. The private provider config and session key stay inside the ignored output tree; reports contain paths and hashes, never secrets.

Retained diagnostic v5 bound a consistent three-term approved-seed fixture before submission at config version 32, recovered the same processing ID and copied one exact source chunk with four distinct ontology-stage facts. Its actual log shows all three ontology terms selected, then ten entity records and zero relationship records. The ownership predicate was absent, and the known-answer check failed. Fixing inconsistent seed identifiers removed a concrete configuration defect but did not establish model extraction quality. This result is retained alongside v1–v4, not replaced by a success claim.

The application-ledger v1 probe stopped before source submission because of a script file-opening error; its simulated publication is retained. v2 reached real prepared ingestion, recovery and selected local evidence. Its initial question assertion exposed the historical-source default, leading to the explicit read-scope contract above. Its resumed local-only read passed after upstream configuration changed, proving that frozen reads no longer require that provider. v3 stopped before preparation/enqueue because its script captured only selected prompts while the hardened helper required the entire prompt type.

The final **application-ledger v4** passed with the final run-specific source registration, recursive private-key rejection and explicit question source scope. Actual Jena 6.2.0 and OntoCheck 0.1.3 reports preceded the explicitly simulated isolated approval. Preparation captured config version 48 before source submission; recovery reattached the same queued receipt; one exact 98-byte source chunk with eight quoted extraction facts became a local frozen corpus. A question explicitly selected that corpus, quoted the passage and identified Atlas as absent from the approved ontology. The approved version and Git refs did not change during import/read. Three premature selection jobs failed closed while extraction-stage provenance was absent, and remain in the ledger. [The sanitized evidence packet](../infra/portal/import-evidence.json) records hashes, IDs, retained failures and exact verification boundaries; private credentials remain excluded.

Focused gateway/import/reconciliation/provider-bound/application tests produced **53 passed, 1 opt-in live probe skipped** in the installed pinned SDK environment. The separate actual lifecycle script supplies the live result above; a skipped generic probe is not counted as live verification. Controlled tests cover wrong scope, altered/reverted config, receipt mismatch, lost responses, exact Unicode spans, changed bytes, incomplete stage provenance and literal metadata. Live evidence is specific to this bounded synthetic deployment; shared identity, processor config attestation, remote immutable storage and semantic quality remain separate gates.

The separate [live workspace denial receipt](workspace-denial-evidence.json) used a real non-administrator `writer` in its own newly created workspace. Own source read/write and config read returned 200; foreign source read/write and config read returned 403, with the foreign source SHA-256 unchanged. The probe disabled only its created identity/workspaces afterward. This establishes those actual gateway checks, not a shared Studio identity bridge or a general authorization audit.
