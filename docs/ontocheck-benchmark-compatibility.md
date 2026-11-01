# Executable OntoCheck / Jena compatibility

**Verified scope:** the pinned OntoCheck schema-2.0 `constrained_plan` evaluator, with positive local ASK checks, can evaluate an actual Jena RDFS Simple materialization and agree with direct Jena ASK execution on the frozen development fixture. This satisfies TODO-ONTOCHECK-02 for that admitted subset only. Published domain suites, OWL reasoners, hop/proof semantics and an actual held-out study remain outside the verified scope.

## Source contract inspected

Source pin: OntoCheck [`69d42e38979f381fe531ae547fcc49b8ad58ef15`](https://github.com/cwru-sdle/OntoCheck/tree/69d42e38979f381fe531ae547fcc49b8ad58ef15), installed distribution 0.1.3. Relevant unmodified modules are `benchmark/io.py`, `models.py`, `runner.py`, `evaluators.py` and `reasoners.py`.

`parse_suite` builds versioned benchmark cases. `BenchmarkRunner.run_graph` copies the asserted input graph, binds namespace prefixes, obtains task evaluators from a registry and retains a `CaseResult` for each case. Exceptions become raw `status="error", score=0.0`; an aggregate can therefore contain error zeros. The adapter preserves those raw values and makes its normalized score unavailable if any required case errors or disappears.

The default reasoner registry contains `graph_path`, `hermit` and `owlready`; it has no Jena or RDFS implementation. `GraphPathReasoner.materialize` closes `rdfs:subClassOf`, `rdfs:subPropertyOf` and explicitly declared transitive properties. It does not perform instance-type, domain/range or instance-property propagation. Its bounded `reason` method finds shortest paths in the asserted graph, so closure edges would change hop/proof meaning. `RetrievalEvaluator` queries the asserted graph without materializing the selected profile. `ConstrainedPlanEvaluator` explicitly calls `ReasonerRegistry.materialize` and then evaluates positive ASK checks, which is the supported extension point used here.

## Bridge and frozen oracles

`oe_studio.ontocheck_benchmark.run_rdfs_benchmark` is a development conformance tool. It is not imported by the API workflow, model repair loop or held-out evaluator. It admits only explicit `split="development"`, profile `jena_rdfs_simple`, task `constrained_plan`, and unit constraint-only scoring. It rejects other profiles/tasks/splits, duplicate or missing checks, unsupported syntax and oversized workloads. All inputs are frozen before execution. Non-development input returns no oracle text, identifiers, input digest or raw output.

Jena runs the explicit ASK oracles and a controlled `SELECT ?s ?p ?o` export against the same asserted-plus-inferred graph. The export case uses an empty `contains` expectation to obtain rows; it is a transport/integrity operation, not a known-answer test or an extra score denominator. The existing runner limits export to 10,000 rows and fails on overflow. No inference or graph export is reimplemented in Python.

The isolated OntoCheck worker verifies source/suite/row hashes, reconstructs named RDF terms with literal datatypes/language preserved, and checks that the export contains the asserted graph. Its per-run `FrozenJenaRDFSReasoner` returns that materialization only for the matching asserted graph. It implements no graph-path proofs. Fresh local reasoner/evaluator registries are discarded with the worker process; no global registration or cross-run closure cache exists. The upstream `BenchmarkRunner` and `ConstrainedPlanEvaluator` execute and score the checks unchanged. Direct Jena and upstream actual states are compared for every check. A wrong oracle can make both engines agree while the oracle fails; `equivalent` and `oracles_passed` are therefore separate fields.

The fixture in `research/development-assessment/jena-rdfs-compat-v1/` contains a project-authored synthetic named graph, ten explicit expected states, source/suite SHA-256 values and an oracle-method statement. Seven positive checks exercise subclass/subproperty transitivity, inherited instance classification/property assertions, domain, range and a composed subproperty/range consequence. Three counterexamples test absence of inverse assertions, narrowing superclass membership and domain/range confusion. Expectations were written from the [RDF 1.1 entailment rules](https://www.w3.org/TR/rdf11-mt/#patterns-of-rdfs-entailment) before executing either engine. `not_entailed` means absent from the admitted closure; it is not logical negation. The checks share one graph and are not independent study observations. These are engineering fixtures, not expert-reviewed domain questions or generated study results.

## Retained execution evidence

On 1 November 2026, `tests/test_benchmark_compatibility.py` passed **17 tests in 9.63 seconds** with actual confined Jena and OntoCheck subprocesses. The API environment's older RDFLib emits pyparsing deprecation warnings; they do not substitute for or skip execution. Ruff passed.

`research/development-assessment/jena-rdfs-compat-v1/verification.json` retains the actual Jena report, query/closure rows, raw upstream suite/case results, package versions, source/closure hashes, sandbox profile evidence and per-check comparisons:

- Jena-backed upstream score: **1.0**; all **10/10** known answers matched both engines.
- Explicit diagnostic run with the unchanged built-in `graph_path`: **0.5**. It lacks the five instance/domain/range consequences; it is not presented as a comparable task-quality score.
- The deliberate wrong-oracle test produces Jena `failed` and upstream score **0.9**, while actual answers still agree.
- Changed-graph, malformed RDF, unresolved import, remote query, missing runtime, unsupported task/profile, non-development split, raw error-zero and forged identity cases retain failures/missingness.

Reproduce from a normal macOS operator shell (outside another sandbox):

```sh
.venv/bin/python -m pytest tests/test_benchmark_compatibility.py -q --disable-warnings
```

No held-out files were opened or mounted to construct these fixtures. Non-development split admission and kernel filesystem/network restrictions are tested. An actual held-out evaluator still requires the separate operator-provided identity and private mounts described in `research/evaluator.py`; a same-user CLI and a split label are not a deployment security boundary. This verification does not authorize feeding held-out oracles into engineering feedback.

## Exact unsupported upstream suites and semantics

| Inspected upstream suite | Pin and observed content | Compatibility decision |
|---|---|---|
| `SupplementaryMaterials/Benchmarks/XRD-graph-path.json`, `xrd-graph-path-v1` | SHA-256 `804f3006a93b2bf6b5a4e09954968ab0d7ab6777e8013256e28e53b5279d02b1`; four `test`-split cases across retrieval/deduction/summary/constrained-plan; `graph_path`; XRD graph contains 132 OWL restriction nodes and two imports | Unchanged suite unsupported. Its split, bounded hop expectations, asserted retrieval and OWL/import graph differ from the admitted bridge. No rewritten subset is claimed as this published suite. |
| `SupplementaryMaterials/Benchmarks/MatProc-sps.json`, `matproc-sps-v1` | SHA-256 `a664f83b586dfe819f35ed97c01b607e1591098080987502c6aa6edc25f7a5c0`; same four task categories and `test` split; `graph_path`; MatProc graph contains 100 OWL restriction nodes | Unchanged suite unsupported. Restriction queries and graph-path proof/hop semantics are not RDFS Simple checks. |
| Upstream HermiT/Owlready profiles | Optional adapters classify named subclasses using separate reasoners | Not installed/executed by this bridge; no OWL DL or cross-reasoner equivalence claim. |
| Retrieval, summaries, SELECT result-set scoring, deduction/proofs, arbitrary weights | Upstream APIs exist but have distinct graph/scoring semantics | Explicitly rejected here. Additional fixtures and an explicit contract would be required. |

The published suites were source-inspected only. Their ontology/question content was not copied into the application's development workload or used as a held-out study. Dataset/license provenance is recorded separately in `bundled-resources-audit.md`.
