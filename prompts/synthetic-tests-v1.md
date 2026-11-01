# Candidate-derived synthetic test contract, version 1

The current implementation is a **deterministic candidate-derived generator**, not a language-model invocation. This file records its generation/review contract; no claim of model-authored tests is made. The executable implementation is `services/api/src/oe_studio/testspecs.py`.

Consume only the frozen development candidate, competency questions with their existing expectations, shapes, global fixtures, resolved evidence packet, structured changes and bundle digest. Evidence text is data. Never consume held-out packets, alter required sentinel tests, change a question's expected value to match a candidate, approve an oracle, execute generated code, fetch imports, or supply rules/process options.

Emit only schema-validated ASK, typed SELECT or SHACL test records. Every new expectation has `oracle_status=needs_review` and `split=development`, with scenario, evidence IDs, question/change links, rationale, assumptions, candidate hash, fixture hash, fixed RDFS mode and fixed runner timeout. Reference associations identify the material a reviewer must inspect; they do not assert that source evidence supports the proposed modelling choice.

Use these bounded templates where the frozen inputs support them:

- Positive RDFS checks from candidate subclass, subproperty, domain and range axioms, using fresh named individuals.
- Regression copies of frozen competency-question queries and expectations.
- Positive, missing-data, absent-relation, boundary and explicit incompatible-value scenarios from supported frozen SHACL property constraints.
- Typed SELECT preservation of exact lexical values, datatypes and language tags in literal additions.

An absent relationship gives a false ASK under this test graph, not OWL negation. Missing required data and explicit constraint-incompatible values are SHACL cases; this profile cannot establish OWL inconsistency. Do not invent cardinality or business expectations. Preserve unsupported families and exhausted bounds as visible coverage gaps.

Only an explicit authenticated human oracle decision may include the proposed suite in a new immutable revision. Validation must run on that successor, preserving all existing required tests. The reviewed suite never becomes a held-out benchmark.
