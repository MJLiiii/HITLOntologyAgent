# Verified engine integrations

Verification date: 1 November 2026. `infra/versions.lock.yaml` records the exercised runtimes, dependency artifact hashes and installation provenance. The engine contracts are tested with real subprocesses in `tests/test_validation.py` and `tests/test_assessment.py`. Missing engines cause failures; these tests never skip or substitute scores.

## Reproduction

Use macOS, Python 3.12 and Java 21. The required worker confinement currently supports macOS Seatbelt only. OntoCheck has a separate environment because its reviewed dependency set uses RDFLib 7.6.0 while the API uses RDFLib 7.1.4.

```sh
uv venv --python 3.12 .venv-ontocheck
uv pip sync --python .venv-ontocheck/bin/python requirements-ontocheck.lock
JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home \
  mvn -f services/jena-runner/pom.xml package
.venv/bin/python -m pytest tests/test_validation.py tests/test_assessment.py tests/test_engine_isolation.py -q
```

The installation step needs network access on a new machine. With dependencies already cached, add `--offline` to `uv pip sync` and `-o` to Maven. In a read-only Maven cache sandbox, `-Daether.syncContext.named.factory=noop` avoids lock-file writes; use it only for a cache with no concurrent writers. This exact offline Maven build and both engine test files were exercised here. No dependency installation or download happens during assessment or validation.

The adapters default to the repository's `.venv-ontocheck/bin/python`, generated `services/jena-runner/target/oe-jena-runner.jar` and Homebrew Java 21 when present. Deployment configuration can override `OE_ONTOCHECK_PYTHON`, `OE_JENA_RUNNER_JAR`, and `OE_JAVA_EXECUTABLE`. `OE_ENGINE_ISOLATION` defaults to `macos-seatbelt` on macOS; unsupported platforms/modes fail closed. Request payloads cannot change executable paths, process flags, inference rules or assessment settings. Run the contracts in a normal operator shell: macOS rejects applying Seatbelt from inside some existing sandboxes, including this Codex tool sandbox; the verification commands used authorized execution outside it.

## Apache Jena

All six packaged Jena modules are version **6.2.0**, licensed Apache-2.0. The project-owned runner is **0.1.0**. Maven compiles against Java 21 and creates a shaded executable JAR. Jena 6.2 requires `RDFParser.fromString(text, Lang.TURTLE)`; the older one-argument call does not compile. Shading discards the dependency package manifest, so the report reads Jena's retained Maven `pom.properties` version rather than `Jena.VERSION`, which otherwise reports `<development>`.

The local manifest binds every input file by SHA-256, limits size, rejects symlinks/path traversal, requires the fixed RDFS profile, and preserves the exact supplied bundle identifier, including an optional `sha256:` prefix. The Python adapter checks status/exit-code agreement, engine version, all required stage/case outcomes and the required raw JSON/Turtle reports before accepting success.

The admitted profile is specified in `config/modelling-profile.json`. Ontology and data graphs contain named triples, class/property declarations, subclass/subproperty/domain/range relationships, labels/comments and local data predicates (declared for ontology assertions). OWL imports, restrictions, lists, equivalence, disjointness, inverse and transitive-property declarations are explicitly unsupported. The runner materializes Jena RDFS Simple closure, then runs required SHACL Core constraints and parsed local ASK/SELECT expectations against asserted plus inferred triples. It does not claim OWL DL consistency.

SPARQL is admitted through an algebra/function allowlist. SERVICE, FROM, GRAPH, updates, property paths, extension functions and aggregate/expression projections cannot execute. SHACL-SPARQL and custom targets/functions are outside the shape vocabulary. The process has a 256 MiB heap, 128 MiB metaspace, two active processors, a 30-second wall-clock timeout, 10-second query timeout, 50,000 input-triple limit, 100,000 closure-triple limit and 10,000 SELECT-row limit. Over-limit results fail instead of truncating. The grammar restrictions supplement the separate operating-system boundary below; they are not themselves kernel isolation.

Contract fixtures verify inferred subclass answers, wrong expectations, expected-negative and globally required SHACL violations, typed/language SELECT bindings, unsupported constructs/queries, malformed Turtle, timeouts, missing executables/reports, artifact hash mismatch and bundle identifier preservation. Reports retain `shacl-report.ttl`, `query-results.json`, input hashes, closure hashes and the executed JAR hash.

## OntoCheck

The source pin is [`69d42e38979f381fe531ae547fcc49b8ad58ef15`](https://github.com/cwru-sdle/OntoCheck/tree/69d42e38979f381fe531ae547fcc49b8ad58ef15), distribution metadata **0.1.3**. The installed wheel's SHA-256 is `69adeecf9d0c6c6286d55860a4b582b9d1ba08dff60c85c2adc838a0b5ef6307`. All **40 Python files** were byte-compared across the cached source checkout, built wheel and isolated installation with **zero mismatches**. The worker checks `direct_url.json` for the exact Git commit. A generic PyPI `ontocheck==0.1.3` installation is not an accepted substitute for this source provenance.

Attribution: OntoCheck by the **SDLE Research Center, Case Western Reserve University**, copyright 2025, is licensed [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/). The upstream package files are unmodified. The project adds an external adapter, isolation and contract checks. This records package license metadata; organizational approval of a deployment remains separate.

The actual inspected and exercised public signatures are:

```python
task_based_metric_v_0_0_1(ttl_file, questions, domain_prefixes,
    domain_ns_fragments=None, auto_derive_fragments=True)
conceptual_fitness(ttl_file, questions=None, domain_prefixes=None,
    domain_ns_fragments=None, weighting='canonical', query_weights=None,
    mappings=None, authorize_prefix_mapping=True)
structural_fitness(ttl_file, questions=None, domain_prefixes=None,
    domain_ns_fragments=None, weighting='canonical', query_weights=None,
    mappings=None, authorize_prefix_mapping=True,
    lam=0.6931471805599453, max_hops=8)
```

The adapter freezes `ex:` to `https://example.org/oe-demo/`, explicitly passes that namespace fragment, disables fragment derivation and automatic prefix mapping, uses only explicit reviewed mappings, uses canonical weighting and sets structural decay to `ln(2)` with eight hops. The application exports its own `demo:` questions as canonical `ex:` before freezing them. The worker preserves the exact exported question set and its hash. It intentionally rejects unbound/mismatched prefixes and full-IRI workloads because upstream vocabulary extraction only recognizes prefixed local names. Imports and duplicate local names in different namespaces are unsupported. Embedded namespace substrings cannot redefine domain membership.

RDFLib parses every question. Only ASK/SELECT basic graph patterns, projection and DISTINCT are admitted for assessment: upstream fitness otherwise flattens optional/filter/union patterns or drops property-path edges. Parsed domain terms must equal the upstream regex term set, so comments and string literals cannot invent vocabulary denominators. Query records are exported from `sparql_query` only; an untrusted `graph_query` cannot silently replace the workload. The adapter also uses the pinned private helpers `_extract_terms_from_sparql`, `_get_ontology_terms` and `load_query_patterns` to verify exact input accounting and preserve raw term sets. These helpers are tied to the commit, not a claimed stable upstream API.

An isolated `python -I` subprocess has a bounded wall-clock timeout, a temporary working directory and a sanitized environment. Before importing OntoCheck it installs a supplementary Python audit hook that rejects networking and child-process launches. The kernel profile also applies. Filesystem confinement exposed an upstream import-time English stopwords lookup: setting `NLTK_DATA` alone still searched the user's home. The worker now verifies the bundled English file hash and explicitly replaces `nltk.data.path` with `resources/nltk`. The exact file and original corpus README were copied from the verified cached NLTK archive; see `resources/nltk/NOTICE.md` for provenance and the unresolved corpus-license metadata. No runtime downloads, remote OOPS! calls or executable benchmark are invoked.

`assess(..., mappings=[...])` accepts `ApprovedMapping` records containing full requirement/ontology IRIs, `relation_type="canonical_correspondence"`, rationale, evidence IDs, reviewer and review ID. The API must authenticate/stamp the review and resolve its evidence; the adapter validates the frozen record shape, uniqueness, evaluated requirement membership and declared target kinds. It never translates a mapping into an ontology axiom. Both snapshots use the same mapping dictionary, complete records and canonical UTF-8 JSON hash. Missing targets remain unsupported requirements with zero strict support, allowing comparison when a candidate adds a mapped term. Per-snapshot target-presence diagnostics remain separate from raw upstream output. A changed reviewer/rationale/evidence/review ID changes mapping identity even when numerical results stay the same. Unknown relations, prefix/label keys, duplicate requirements and class/property mismatches cannot become scores.

In the renamed-class fixture, lexical similarity produces strict fitness **0.6667** and approximate-inclusive fitness **1.0**, with an aligned tier and nonzero ambiguity. An approved full-IRI correspondence raises strict/structural fitness to **1.0** without changing the Turtle bytes, vocabulary overlap (**2/3**) or query text. Raw conceptual, structural and vocabulary objects remain upstream values; fitness is rounded to four decimals upstream. Explicit property correspondences are tested too. An approximate score alone never grants mapping approval.

The exact fixture has three ontology terms, three task terms, three overlapping terms, vocabulary coverage/utilisation **1.0**, strict conceptual fitness **1.0**, and structural fitness **1.0**. Removing a property range leaves vocabulary coverage **1.0** but structural fitness **0.0**. Rebinding ontology prefixes cannot become an authorized mapping: strict fitness stays **0.0**, even if lexical support exists. Empty vocabulary denominators stay null; class-only workloads keep structural fitness null with a reason. Missing/unsupported questions, malformed inputs, process failure and timeout cannot become completed reports. Repeated identical inputs reproduce raw outputs and hashes. Base/candidate reports use the same questions and fixed settings and retain raw outputs, denominator counts, term sets and nullable deltas.

`TODO-ONTOCHECK-01` is verified for this narrow offline metric allowlist and synthetic domain. The tests establish library/adapter behavior, not universal ontology quality. **`TODO-ONTOCHECK-02` is verified only for the admitted development `constrained_plan` subset:** the genuine upstream runner, using a frozen Jena RDFS materialization, agrees with direct Jena on ten independent known-answer checks. Published XRD/MatProc suites, OWL/proof/hop semantics and an actual held-out study remain unsupported/unverified. See `evidence/ontocheck-benchmark-compatibility.md` for raw evidence, exact boundaries and rejection tests. Jena remains the workflow validation authority. Richer namespace/import scopes, query forms and additional metrics require explicit extensions and new contract fixtures.

## macOS worker boundary

`engine_isolation.py` renders the versioned `config/macos-engine.sb` profile for each run and launches `/usr/bin/sandbox-exec`. The profile denies networking and file-content reads/writes, then permits reads of selected operating-system libraries, the chosen runtime/environment, the exact worker/JAR, bundled language resources and the run directory. Writes are limited to that run directory and `/dev/null`. The repository, canonical artifact store and home credentials are not read roots. `/System/Volumes/Data` is deliberately excluded from the system allowlist. Reports retain the profile and rendered-profile hashes. A missing launcher, unsupported platform, rejected profile or denied runtime dependency returns an engine error; no plain-process fallback exists.

Verification on macOS **27.2 (26B123)**: native libc TCP connection/UDP send calls succeed against local listeners without Seatbelt and return `EPERM` with the profile, including a launched descendant. The probe does not rely on Python's socket audit events. Real Jena/OntoCheck cases run with the same profile. Canary tests verify permitted input reads/output writes and denied state/credential reads, runtime-dependency overwrites, outside writes, symlink and hard-link escapes, and Data-volume aliases. `tests/probes/macos_network.py` also preserves the standalone network experiment.

This is a bounded local prototype, not a full process capability sandbox: metadata, selected system resources, IPC and other default operations remain accessible; an operator who owns the server/runtime can change its code/configuration. The installed Apple man page marks `sandbox-exec` deprecated and recommends App Sandbox. A packaged deployment should evaluate a signed helper with [App Sandbox capabilities](https://developer.apple.com/documentation/security/protecting-user-data-with-app-sandbox); [Apple's entitlement reference](https://developer.apple.com/library/archive/documentation/Miscellaneous/Reference/EntitlementKeyReference/Chapters/EnablingAppSandbox.html) describes explicit network and child-inheritance rights. That packaged deployment is unimplemented. Linux needs a separately verified container/namespace profile (no network, read-only runtime/declared inputs, ephemeral writable run directory, resource limits); merely running this Python audit hook is not an equivalent substitute.

## Other integration boundaries

This evidence does not close TrustGraph host/backend compatibility. The standalone Studio build and a plugin export are not a live Workbench mount, authenticated read, ingestion or publication-boundary proof. Backend, host and template source commits were subsequently inspected and recorded in `infra/versions.lock.yaml`; live compatible releases and image digests remain unverified. See `docs/integrations.md` for the source findings and open gates. No external service or real-study result is fabricated by the engine adapters.
