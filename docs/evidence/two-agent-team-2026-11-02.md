# Two-agent and team development verification — 2 November 2026

**Subsequent API-only setup decision:** the user removed the Qwen installer, launcher and local benchmark option after these observations. The recorded local-model result below is historical evidence, not a current setup requirement. Current generation uses [API profiles](../multi-llm.md).

This milestone was implemented in the existing checkout on Mac. Proposal and test-generation agents have separate versioned contracts and generation records, sharing transport/retrieval utilities. The backend retains persistence, engine execution, review and publication. PostgreSQL team accounts and independent API/worker/frontend startup supplement the unchanged local demo path. No participant study, real expert decision or working-ontology publication was performed.

## Correctness and operation

| Check | Observed result |
| --- | --- |
| Full backend suite with real Mac engine isolation | 593 passed, 8 skipped, 96.71 seconds; `/tmp/oe-team-completion-backend.xml` and `.log` |
| Final contract/access/migration checks | 75 focused tests passed after the typed-contract and credential-error refinements; two workflow repair regressions also passed |
| Frontend | 64 tests passed; standalone and TrustGraph plugin production builds passed |
| Generated contracts and static checks | OpenAPI regeneration/reproducibility, Ruff, TypeScript and diff checks passed |
| PostgreSQL | Seven cases passed in 11.41 seconds; all seven restored database/artifact/Git stores matched; owned container removed ([report](team-postgres-2026-11-02.json)) |
| Actual Chrome team workflow | Four named test accounts; reviewer accepted expectations into revision 2; all 20 real Jena cases passed; real OntoCheck completed; approver accepted/published one exact checked release ([report](team-browser-2026-11-02.md)) |
| Worker processes | Independent startup, competing claims, SIGINT/SIGTERM, abrupt interruption/expired lease and existing publication recovery checked with disposable stores |
| DORA packet | Five documents, nine official representations, 44 matching extracts and all 56 hashes passed the offline verifier |

The eight full-suite skips are seven PostgreSQL tests exercised separately by the provisioned harness and one optional live TrustGraph probe. The run emitted 3,412 dependency warnings. Early enclosing-sandbox engine failures were not counted as passes; host execution retained the application's own Seatbelt isolation. An initial PostgreSQL harness run passed its cases but failed an obsolete six-case count; the count was corrected and a fresh run completed. Existing historical evidence was retained.

Security tests cover project read isolation, viewer write denial, role-specific human decisions, account/session revocation, password reset, throttling, exact Origin/CSRF, multiple-tab CSRF stability, permission changes before queued dispatch and direct backend mutation checks. Model-profile removal during generation leaves the output record but prevents suite commit. Team agent generation requires an accepted current scope, including a final recheck. Accounts and sessions use additive migrations; exact frozen unversioned `0001`/`0002` schemas are adoptable without rewriting workflow records. Unknown schema shapes fail closed.

Both agents reject malformed output and fabricated references. Test suggestions additionally reject unsupported SPARQL, schema/import fixtures, unknown fixture vocabulary and authority fields. Acceptance appends reviewed tests to a successor; mandatory checks and the original revision remain intact. Configured failures never fall back to demo output. Controlled transport and the existing A–D regression suite exercise the preserved experimental restrictions; no held-out study data was used.

Independent reviews found and corrected cross-tab CSRF invalidation, approver-only review-timer access, mid-call model-grant revocation, and stale-PID cleanup risk in the browser helper. Five cleanup regressions verified ownership-first checks, process fingerprints and idempotent stopped state. Configuration errors also suppress raw input dictionaries so invalid team settings do not echo connection credentials; its regression passed. These reviews found no remaining important issue in their scoped follow-ups. Review notes and full logs remain local verification work products; the reports and machine evidence here preserve the relevant conclusions.

## Development comparison

The reproducible [benchmark](../../scripts/benchmark_test_agents.py) compares identical synthetic candidate/source packets against fixed independently authored expectations, four invalid RDFS mutants and three valid variants. Real Jena evaluates the suites. It is separate from registered A–D experiments and makes no human decisions.

| Generator | Attempts / invalid outputs | Generated tests | Defects detected | False positives | Generation time |
| --- | --- | --- | --- | --- | --- |
| Deterministic, final controlled comparison | 1 / 0 | 5 | 4 / 4 | 0 / 3 | 0.0674 s |
| Controlled response through ModelClient | 1 / 0 | 4 | 4 / 4 | 0 / 3 | 0.1664 s |
| Installed local Qwen3 1.7B | 1 / 1 | No admitted suite | Not measured | Not measured | 3.5671 s |

[Controlled comparison evidence](test-agent-comparison-2026-11-02.json) includes inputs, suites, engine reports and implementation hashes. Mock token counts are explicitly synthetic; they are not provider measurements. No network completion occurs in that comparison.

The [actual local-model attempt](test-agent-local-comparison-2026-11-02.json) used the installed repository Ollama/model files, fixed loopback transport, cloud disabled, one attempt, 4,096 output-token and 120-second limits. The model returned an ASK case without a query; semantic admission rejected it. The daemon reported 693 input and 80 output tokens. Raw output and failure metadata were retained; quality metrics are null because no suite was admitted. The owned daemon was stopped and its listener closed. There were no downloads or paid/remote model calls, and no fallback or retry. Provider cost is unavailable; neither run incurs a hosted-provider charge.

These are single-run engineering observations. The controlled response establishes pipeline behavior and defect-detection capacity; it does not establish model quality. The local run demonstrates that this small model did not produce a usable suite on this attempt. No general failure rate, broad semantic quality or statistical performance conclusion follows.

Reproduce without models using `.venv/bin/python scripts/benchmark_test_agents.py --output /absolute/new-report.json`. The former `--local-ollama` option has been removed; the current benchmark uses a controlled OpenAI-compatible API response without starting a local model. Run outside an enclosing sandbox that prevents the application's own engine isolation; never disable that isolation to obtain a pass.

## Remaining scope

Ubuntu engine isolation/deployment, repository splitting, DORA runtime activation, advanced account administration and a real participant study remain deferred. The backend still uses Mac-specific confined engine runners. Team application permissions do not claim OS isolation from the machine's operator. Hosted-provider compatibility and model quality require separate evaluation; the default test-generation mode remains deterministic.
