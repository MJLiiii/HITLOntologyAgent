# TrustGraph integration tooling

Current text completion accepts server-owned OpenAI and Claude API profiles through `prepare_llm.py`; see [profile-bound extraction](../../docs/trustgraph-multi-llm.md). The derived worker uses the shared bounded API runtime and locked dependencies. Staging does not start a worker or call a provider.

The `prepare_pipeline*`, `init_pipeline.py`, `check_pipeline.py`, selected-import smoke helpers and `bounded_ollama*` retain the earlier pinned synthetic host investigation. Their local-model generation paths are retired from current Studio setup and retained only to reproduce historical evidence. Existing private runtime bindings, embedding services, ledgers and recorded hashes are preserved. See the [dated pipeline report](../../docs/evidence/trustgraph-pipeline-smoke.md) for their original scope.
