# OntoCheck review and integration decisions

Reviewed on 31 October 2026 for the Human-in-the-Loop Ontology Engineering proposal and implementation plan.

## Review scope and evidence

Reviewed the upstream README, package metadata, LICENSE, assessment entry point, vocabulary metric, query-fitness implementation, benchmark runner and reasoner registry, exports, and relevant test definitions. This was a source review. No OntoCheck install, upstream test execution, performance measurement, or Jena integration test was performed. The bundled Python environment did not contain RDFLib; no dependency environment was changed.

- Repository snapshot: [commit 69d42e38979f381fe531ae547fcc49b8ad58ef15](https://github.com/cwru-sdle/OntoCheck/tree/69d42e38979f381fe531ae547fcc49b8ad58ef15).
- [Package metadata](https://github.com/cwru-sdle/OntoCheck/blob/69d42e38979f381fe531ae547fcc49b8ad58ef15/pyproject.toml): version `0.1.3`, Python `>=3.8`, RDFLib/NetworkX/requests/pyspellchecker/NLTK dependencies, optional HermiT/Owlready integrations. The version string does not prove that a PyPI artifact contains this exact source.
- [License file](https://github.com/cwru-sdle/OntoCheck/blob/69d42e38979f381fe531ae547fcc49b8ad58ef15/LICENSE): identifies CC BY 4.0. The package classifier is less specific; preserve the actual license and attribution and verify the selected install artifact.
- [Vocabulary metric](https://github.com/cwru-sdle/OntoCheck/blob/69d42e38979f381fe531ae547fcc49b8ad58ef15/src/ontocheck/task_based_metric.py).
- [Query fitness](https://github.com/cwru-sdle/OntoCheck/blob/69d42e38979f381fe531ae547fcc49b8ad58ef15/src/ontocheck/query_fitness.py) and [tests](https://github.com/cwru-sdle/OntoCheck/blob/69d42e38979f381fe531ae547fcc49b8ad58ef15/tests/test_query_fitness.py).
- [Assessment API](https://github.com/cwru-sdle/OntoCheck/blob/69d42e38979f381fe531ae547fcc49b8ad58ef15/src/ontocheck/run_assessment.py).
- [Benchmark runner](https://github.com/cwru-sdle/OntoCheck/blob/69d42e38979f381fe531ae547fcc49b8ad58ef15/src/ontocheck/benchmark/runner.py), [reasoner registry](https://github.com/cwru-sdle/OntoCheck/blob/69d42e38979f381fe531ae547fcc49b8ad58ef15/src/ontocheck/benchmark/reasoners.py), and [leaderboard exports](https://github.com/cwru-sdle/OntoCheck/blob/69d42e38979f381fe531ae547fcc49b8ad58ef15/src/ontocheck/leaderboard_export.py).

## Assessment and research positioning

OntoCheck covers a substantial part of the previously unspecified ontology-assessment layer: vocabulary workload measures, structural/annotation diagnostics, conceptual and structural query fitness, and executable benchmarks. Reuse is appropriate and avoids presenting those existing capabilities as a new contribution.

The proposed contribution remains the source-grounded extension/repair workflow, versioned evidence and change history, controlled human approval, and experiments on repair correctness, source fidelity, explanation-assisted decisions, and expert effort. This review does not establish the novelty of that whole contribution against all other literature.

OntoCheck belongs alongside Jena in the architecture. Its presence does not eliminate Jena SHACL, executable entailment/regression checks, separately reviewed expected answers, or expert assessment of source meaning. Optional reasoner integrations do not demonstrate full consistency validation or compatibility with the selected project profile.

## Findings that affect the alignment design

| Finding in the inspected source | Consequence in the revised design |
|---|---|
| Vocabulary `recall` is required-term overlap divided by required vocabulary; `precision` is overlap divided by ontology vocabulary. Aliases include `task_coverage` and `ontology_utilization`. | Use coverage/utilisation labels. Do not confuse either with answer correctness, entailment precision or semantic fidelity. Broader legitimate vocabulary can reduce utilisation. |
| Basic overlap stores local names, not complete IRIs; SPARQL extraction uses a regex over configured prefixes. | Distinct namespace IRIs ending in the same name can collide. Flag such cases, record exact term sets and separately verify full-IRI support. This limitation is inferred from the implementation, not an executed bug reproduction. |
| Namespace fragments restrict ontology term extraction, and unresolved prefix derivation can fall back to broad inclusion. | Freeze explicit namespace scope and local imported snapshots. A missing binding is an input problem, not permission to change the assessment denominator. |
| Empty required or ontology vocabulary yields raw `0.0` overlap values; question records without `sparql_query` can be skipped. | Preserve raw outputs, normalize undefined ratios to missing with reasons, and reject silently skipped required questions. |
| Conceptual fitness distinguishes exact/explicit-equivalence support from approximate local-name/label matches. It exposes a separate approximate-inclusive score and ambiguity. | Present tiers separately. An approximate match needs explicit expert approval; matcher similarity cannot silently authorise an ontology equivalence axiom. The implementation's equivalence support is not a general DL entailment guarantee. |
| Fitness functions default `authorize_prefix_mapping=True`, permitting correspondence based on shared prefix names despite different namespace bindings. | Use explicit approved `mappings` and `authorize_prefix_mapping=False`. Reusing a prefix spelling must not establish identity. |
| Fitness signatures accept `domain_prefixes` and `domain_ns_fragments`, but their docstrings specify that these are unused. | Control the precise graph/import and mapping inputs. Do not assume the basic vocabulary metric's scope arguments also constrain fitness. |
| Structural fitness evaluates admissible schema paths, with path bounds, decay and task weights. | Freeze settings and task graphs. Schema-path availability is not evidence of correct answers on instance data or source fidelity. |
| Benchmark execution uses replaceable reasoners; built-in profiles include `graph_path`, `hermit` and `owlready`. | Verify task format and inference behaviour before reuse. There is no inspected built-in Jena adapter. Unverified benchmark measures remain unavailable. |
| `run_assessment` defaults `allow_network=True`; accessibility metrics inspect remote resources. | Use selected offline metrics, restricted execution, explicit network disabling where supported, and prepared local language resources. Do not select every metric indiscriminately. |

## Revised architecture and workflow

1. Freeze development competency questions, task graphs where required, full-IRI bindings, approved reuse mappings, namespace/import scope, and metric configuration.
2. Materialize an immutable candidate and compare it with its accepted base using identical assessment inputs.
3. Produce a Jena validation report and a separate OntoCheck assessment report linked to the same approval bundle.
4. Present development diagnostics and mapping suggestions during expert review. Changes to ontology, mappings or configuration create a successor bundle and require reruns and fresh review.
5. Require completion of policy-required assessment reports; interpret diagnostic scores using the agreed task and domain criteria. No universal utilisation threshold or score-driven automatic publication.
6. Assess all frozen experimental outputs with an evaluator-only held-out workload. Held-out deficits, mappings, expected answers and importance measures never enter development feedback.

The adapter owns translation and status handling, not independent reimplementations of OntoCheck metrics. Raw upstream outputs, hashes and the selected source version remain inspectable.

## Experiment alignment

The original implementation plan contained three conditions and three broad research questions; the supplied proposal specified four of each. The plan now follows the proposal:

| Condition | Production workflow | Permitted feedback |
|---|---|---|
| A | One-shot generation | No repair feedback |
| B | LLM self-revision | Same sources and revision instructions; no automated reports or expert feedback |
| C | Reasoner-guided repair | Failed entailment-test diagnostics; no OntoCheck diagnostics or expert feedback |
| D | Same automated stage as C, followed by expert review | Expert stage may inspect development assessments and source evidence |

B/C use the same initial candidates and equal budgets; all conditions use the same frozen evidence packet. OntoCheck is the common assessment layer. Feeding its diagnostics to automated repair is a separately labelled future comparison, because adding another feedback source would change the RQ1 intervention.

The RQ2 pre/post comparison evaluates assessment-assisted expert review. RQ3 holds assessment displays and source access constant between explanation arms. RQ4 counts all expert time and uses the same development-assessment display policy in the common correction stage, with unsuccessful cases retained and time to acceptance censored at the common limit.

## Files revised and completion boundaries

- `CODEX_DEVELOPMENT_PLAN.md`: architecture, contracts, immutable assessment artifacts, mappings, API, UI, publication linkage, four-condition research protocol, metrics, compatibility TODOs, milestones and backlog.
- Proposal `Methods.tex`: assessment method, existing-work positioning, reuse/alignment safeguards and held-out split.
- Proposal `SystemArchitecture.tex`: explicit OntoCheck component and workflow.
- Proposal `ResearchQuestions.tex`: common assessment layer, condition-specific feedback and effort-comparison controls.
- Proposal `Abstract.tex`, `ExpectedResearchOutcomes.tex`, `custom.bib`: consistent scope, deliverables and verified software citation.
- Proposal `Ontology.tex`: compact reference spacing to keep the bibliography together; preserve the existing pdfLaTeX/BibTeX backend. Compile with `latexmk -pdf Ontology.tex`.

The revised files specify future software work. They do not claim that the prototype or OntoCheck integration has been implemented. Runtime acceptance remains in TODO-ONTOCHECK-01; benchmark/inference compatibility remains in TODO-ONTOCHECK-02.

## Document verification

Rebuilt the proposal with pdfLaTeX/BibTeX and inspected the rendered ten-page PDF, including the assessment text, architecture, experiment table and bibliography. All 15 cited entries render and have matching bibliography records; no unresolved citation placeholders or overfull/underfull boxes were found. The build emits the BibTeX fallback warning and a generic rerun/undefined-reference warning despite the rendered citations being resolved. These compiler warnings remain recorded here; the output is not represented as a warning-free build.

Original proposal files and PDF, together with the original development plan, were backed up under `backups/ontocheck-2026-10-31/` before revision. The proposal's `.agents` directory was not edited or treated as a request to run additional work.
