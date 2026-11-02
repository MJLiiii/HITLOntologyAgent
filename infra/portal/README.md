# TrustGraph integration tooling

Current model completion uses server-owned API profiles through `prepare_litellm.py`; see [profile-bound extraction](../../docs/trustgraph-multi-llm.md). Studio does not install or launch a Qwen model.

The `prepare_pipeline*`, `init_pipeline.py`, `check_pipeline.py`, selected-import smoke helpers and `bounded_ollama*` retain the earlier pinned synthetic host investigation. Their Qwen-specific settings reproduce historical evidence only; they are not steps in current API-backed Studio setup. Existing runtime bindings, embedding configuration and recorded hashes are preserved. See the [dated pipeline report](../../docs/evidence/trustgraph-pipeline-smoke.md) for their original scope.
