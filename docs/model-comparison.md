# Multi-LLM functional comparison evidence

On 1 November 2026, the bounded comparison command staged the same synthetic ownership chat and proposal cases for `go-glm-flash` (`glm-5.3-flash`) and `go-kimi-code` (`kimi-k2.7-code`). It uses actual `Studio.question` and `Studio.create_proposal` orchestration in a disposable isolated Studio store, including original schema/citation checks and persisted generation/candidate artifacts. No review, approval, publication or engine execution occurs.

**Initial live provider outcome (before credential configuration): blocked for both profiles.** `OPENCODE_API_KEY` was absent from the current process and project `.env`. The runner wrote all four observations as `blocked_missing_credential`. The shared ledger reports **zero reserved HTTP completion attempts** and **USD 0.000000000 reserved**. No paid request, provider availability, latency, token usage, returned-model identity, schema compliance or semantic quality result is claimed. Other applications' credentials were not inspected.

The detailed generated report is `.runtime/multi-llm/smoke-report.md`; each run stages disposable synthetic artifacts under `.runtime/multi-llm/synthetic-*`. These local runtime files are intentionally ignored by Git. This checked-in note preserves the distinction between implementation verification and unavailable live evidence.

Offline verification exercised actual Studio chat/proposal orchestration and the real pinned LiteLLM/OpenAI SDK path against an HTTPX fake wire. The fake provider returned deterministic schema-valid ownership outputs with literal token counts; both profiles passed those fixture checks, four fake HTTP dispatches were atomically reserved, and the conservative full-context full-price total was exactly USD 0.834937600. This demonstrates request routing, schema processing, usage retention, shared accounting and workflow persistence under controlled inputs. It does not demonstrate a response from either real model. Additional tests cover missing credentials, invalid schema, unsupported evidence, provider failures, stale/mismatched prices, cross-caller concurrency and the hard attempt/USD ceilings.

The public official [Go model metadata](https://opencode.ai/inference/go/v1/models) was fetched without a key on 1 November 2026. It agreed with the [Go rate/endpoint documentation](https://opencode.ai/v2/docs/console/go/) for the selected models. The saved selected-model evidence file is `.runtime/multi-llm/opencode-go-models-2026-11-01.json`, SHA-256 `0084f082ebf6fe5ffadf0130e9570db6e5ac853018691098423d8096482d4d70`. The exact revision-bound price artifact expires within 24 hours of verification and must be refreshed from official evidence before a later live run. Full model-context reservations avoid an unverified tokenizer/envelope estimate.

See [configuration, shared TrustGraph mount requirements and reproduction command](multi-llm.md). A privately configured key and current verified price artifact permit the already authorized bounded synthetic run; changing the credential, account settings or provider does not create additional authorized attempts.

## Live follow-up — 1 November 2026, 18:54 UTC

After private credential configuration, the actual Studio comparison completed four OpenCode Go requests in a disposable synthetic store. Current public model metadata was fetched again before dispatch; the exact revision-bound prices are retained in `.runtime/multi-llm/verified-prices-live.json`, with metadata in `opencode-go-models-current.json`. The append-only shared ledger was reused without resetting it.

| Model | Grounded chat | Ontology proposal | Latency (chat / proposal) |
| --- | --- | --- | --- |
| GLM-5.3-Flash | Passed | Rejected: unresolved modelling questions | 3.69 s / 10.32 s |
| Kimi K2.7 Code | Passed | Passed | 14.82 s / 43.97 s |

All four responses passed schema and citation checks and reported the configured model identity. GLM returned the exact requested ownership triple, but also raised questions about adding class, subclass, domain and range declarations outside the narrow requested change. `checked_proposal` rejects nonempty `unresolved_questions`; the runner consequently labels this observation `expected_facts_failed`. That label conflates proposal acceptance with triple correctness here: the retained triple itself matches the expected assertion. Kimi returned the expected assertion with no unresolved questions. The command exited 2 because one observation failed; it is not an all-pass run.

The shared budget now retains **4/20 attempts and USD 0.834937600/1.00 reserved**. Provider-reported cost was zero for each call; reported list costs total USD 0.014945400. These fields do not establish account billing or remaining Go allowance, and reservations are not refunded. No retry or fallback occurred.

Detailed rows, usage, timing and fixture hashes: `.runtime/multi-llm/live-go-report.md`. The report identifies the disposable store containing retained generations. No engine validation, human approval, ontology publication or TrustGraph live extraction/import was performed. This is a four-case functional smoke, not a comparative quality study. Historical missing-key observations above remain evidence of the earlier run.

## DeepSeek and Argon follow-up — 1 November 2026, 18:57 UTC

The user requested Argon or DeepSeek V4.1 Flash. Fresh official Go metadata confirmed `deepseek-v4.1-flash` on the supported OpenAI-compatible endpoint and `gemini-4-argon` on a Google generate-content endpoint, which the current Studio adapter does not support. Argon's full-context reservation would also exceed the existing USD 1 ceiling, so no Argon request was dispatched.

DeepSeek's grounded ownership chat passed schema, citations and the expected answer in 7.879 seconds, with the matching returned model identity, 2,760 input tokens and 569 output tokens. The provider reported zero cost and USD 0.000755400 list cost. Its proposal was blocked before dispatch by the shared budget; the command therefore exited 2. One additional completion attempt was reserved, bringing the unchanged shared campaign to **5/20 attempts and USD 0.987395200/1.00 reserved**. No retry, budget reset or ceiling increase occurred.

The disposable profile and price artifact are `.runtime/multi-llm/deepseek-profiles.json` and `deepseek-prices.json`; evidence is `opencode-go-models-followup.json` and `deepseek-live-report.md` in the same directory. The price artifact uses the verified Sunday off-peak rate and expires within one hour, before any peak window. Fixture contents use the same synthetic scenario but newly staged source identifiers; their hashes differ from the earlier run. No engine validation, publication, human decision or live TrustGraph extraction/import was included.
