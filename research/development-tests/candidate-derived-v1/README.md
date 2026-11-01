# Candidate-derived engineering fixture

This neutral, authored synthetic fixture verifies generator and runner behavior. It is development data, not a benchmark, expert-approved domain oracle or real study. The suite retains `oracle_status=needs_review` even though its expectations matched the real engine.

`inputs.json` freezes the candidate, shapes, global fixtures, development questions, one Dutch language-tagged label addition and an explicitly synthetic evidence reference. `suite.json` contains the generator's 12 constrained specs, input identities, assumptions and coverage report. `verification.json` retains the complete real Jena output, raw query/SHACL artifacts, input manifest and macOS isolation metadata. `manifest.json` records the exact file hashes and non-approval status.

All 12 cases matched their expected results across positive, negative, missing-data, boundary, constraint-contradictory and regression scenarios. Expected SHACL violations count as passing expectations. The Jena runner SHA-256 was `6a6e7e3ed45f98607d20b935e1c6f15b973f6dcde5504eff1d4bc284a5abda53`; an independent fresh source-directory Maven build produced identical JAR bytes. These results establish this finite software contract, not semantic correctness or comprehensive coverage.

Separate integration tests exercise an explicit synthetic oracle decision in a temporary database and validate its immutable successor. They create no decision in application runtime data and confer no study authorization. See [the generation contract](../../../docs/synthetic-test-generation.md) for supported templates and remaining limitations.
