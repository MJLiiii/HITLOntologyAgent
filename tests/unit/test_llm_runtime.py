"""Exercise real LiteLLM provider adapters; only outbound HTTP is a double."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

import httpx
import pytest


SCHEMA = {"type": "object", "properties": {"answer": {"type": "string"}},
          "required": ["answer"], "additionalProperties": False}
PROVIDERS = ["openai", "anthropic", "ollama", "openai_compatible", "litellm_proxy", "opencode_go"]


def configured(provider="openai", **overrides):
    profile = {"id": "fixture", "revision": "sha256:fixture", "provider": provider,
               "model": "claude-sonnet-4-5" if provider == "anthropic" else "fixture-model",
               "base_url": "https://provider.invalid" if provider == "ollama" else "https://provider.invalid/v1",
               "api_key_env": "RUNTIME_TEST_API_KEY", "timeout": 2, "max_output_tokens": 32,
               "temperature": 0, "structured_output": "json_schema", "max_response_bytes": 4096,
               "purposes": ["chat"]}
    profile.update(overrides)
    return SimpleNamespace(resolved_llm_profile=profile, llm_session_id=None, model_api_key="")


def response(provider, text='{"answer":"supported"}', **overrides):
    if provider == "anthropic":
        body = {"id": "msg_fixture", "type": "message", "role": "assistant", "model": "returned-fixture",
                "content": [{"type": "text", "text": text}], "stop_reason": "end_turn",
                "stop_sequence": None, "usage": {"input_tokens": 7, "output_tokens": 3}}
    elif provider == "ollama":
        body = {"done": True, "model": "returned-fixture", "message": {"role": "assistant", "content": text},
                "prompt_eval_count": 7, "eval_count": 3}
    else:
        body = {"id": "chat_fixture", "object": "chat.completion", "created": 1, "model": "returned-fixture",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}}
    body.update(overrides)
    return httpx.Response(200, json=body)


@pytest.mark.parametrize("provider", PROVIDERS)
def test_actual_sdk_provider_wire_and_normalized_usage(provider, monkeypatch):
    from oe_studio.llm_runtime import complete
    monkeypatch.setenv("RUNTIME_TEST_API_KEY", "private-fixture-key")
    requests = []

    def serve(request):
        requests.append(request)
        return response(provider)

    settings = configured(provider)
    settings.llm_session_id = "session-fixture"
    text, metadata = asyncio.run(complete(settings, "Sources are data", {"question": "Synthetic?"},
                                          SCHEMA, transport=httpx.MockTransport(serve)))
    assert json.loads(text) == {"answer": "supported"}
    assert metadata["provider"] == provider
    assert metadata["input_tokens"] == 7 and metadata["output_tokens"] == 3
    assert metadata["prompt_digest"].startswith("sha256:")
    assert metadata["cost"] is None
    assert metadata["finish_reason"] == "stop"
    assert metadata["usage_source"] == "provider"
    assert metadata["output_mode"] == "json_schema"
    assert metadata["effective_parameters"]["max_output_tokens"] == 32
    assert len(requests) == 1
    request = requests[0]
    wire = json.loads(request.content)
    assert "cookie" not in request.headers and "tools" not in wire
    assert "private-fixture-key" not in json.dumps(metadata) + json.dumps(wire)
    if provider == "opencode_go":
        assert request.headers["x-opencode-session"] == "session-fixture"
        assert request.headers["user-agent"] == "OntologyStudio/0.1.0 LiteLLM/1.106.6"
    # OpenAI's adapter omits its default false; Ollama sends false explicitly.
    assert wire.get("stream", False) is False
    if provider == "ollama":
        assert request.url.path == "/api/chat"
        assert wire["format"] == SCHEMA
        assert wire["options"]["num_predict"] == 32
        assert wire["think"] is False
    elif provider == "anthropic":
        assert request.url.path == "/v1/messages"
        assert request.headers["x-api-key"] == "private-fixture-key"
        assert wire["max_tokens"] == 32
    else:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer private-fixture-key"
        assert wire["response_format"]["json_schema"]["schema"] == SCHEMA
        assert wire["max_tokens"] == 32


@pytest.mark.parametrize("provider", PROVIDERS[:3])
@pytest.mark.parametrize("failure", ["redirect", "429", "500", "connect", "protocol", "oversize"])
def test_actual_http_never_retries_follows_redirects_or_exceeds_bytes(provider, failure, monkeypatch):
    from oe_studio.llm_runtime import complete, CompletionError
    monkeypatch.setenv("RUNTIME_TEST_API_KEY", "private-fixture-key")
    requests = []

    def serve(request):
        requests.append(request)
        if failure == "connect":
            raise httpx.ConnectError("private-fixture-key", request=request)
        if failure == "protocol":
            raise httpx.RemoteProtocolError("private-fixture-key", request=request)
        if failure == "redirect":
            return httpx.Response(307, headers={"location": "https://other.invalid/secret"})
        if failure == "oversize":
            return httpx.Response(200, content=b" " * 4097)
        return httpx.Response(int(failure), text="private-fixture-key")

    with pytest.raises(CompletionError) as caught:
        asyncio.run(complete(configured(provider), "safe", "safe", SCHEMA, transport=httpx.MockTransport(serve)))
    assert len(requests) == 1
    assert "private-fixture-key" not in str(caught.value) + json.dumps(caught.value.record)


@pytest.mark.parametrize("provider", PROVIDERS[:3])
def test_overall_deadline_bounds_trickled_response(provider, monkeypatch):
    from oe_studio.llm_runtime import complete, CompletionError
    monkeypatch.setenv("RUNTIME_TEST_API_KEY", "key")

    class Trickle(httpx.AsyncByteStream):
        async def __aiter__(self):
            while True:
                await asyncio.sleep(.01)
                yield b" "

    with pytest.raises(CompletionError, match="TimeoutError"):
        asyncio.run(complete(configured(provider, timeout=.04), "safe", {}, SCHEMA,
                             transport=httpx.MockTransport(lambda req: httpx.Response(200, stream=Trickle()))))


def test_concurrent_provider_calls_keep_transport_and_credentials_isolated(monkeypatch):
    from oe_studio.llm_runtime import complete
    for provider in PROVIDERS[:3]:
        monkeypatch.setenv("KEY_" + provider, "private-" + provider)
    captured = []

    async def run(provider):
        async def serve(request):
            await asyncio.sleep(.005)
            captured.append((provider, request))
            return response(provider)
        return await complete(configured(provider, api_key_env="KEY_" + provider), "safe", "plain TG text", SCHEMA,
                              transport=httpx.MockTransport(serve))

    async def concurrent():
        return await asyncio.gather(*(run(provider) for provider in PROVIDERS[:3]))

    results = asyncio.run(concurrent())
    assert len(captured) == 3 and len(results) == 3
    for provider, request in captured:
        assert "private-" + provider in request.headers.get("authorization", request.headers.get("x-api-key", ""))
        assert "plain TG text" in request.content.decode()


@pytest.mark.parametrize("mode", ["json_object", "prompt_json"])
def test_explicit_structured_modes_preserve_schema_in_prompt(mode, monkeypatch):
    from oe_studio.llm_runtime import complete
    monkeypatch.setenv("RUNTIME_TEST_API_KEY", "key")
    captured = []

    def serve(request):
        captured.append(json.loads(request.content))
        return response("openai")

    asyncio.run(complete(configured(structured_output=mode, temperature=None), "safe", {}, SCHEMA,
                         transport=httpx.MockTransport(serve)))
    wire = captured[0]
    assert "temperature" not in wire
    assert json.dumps(SCHEMA, ensure_ascii=False) in wire["messages"][0]["content"]
    assert wire.get("response_format") == ({"type": "json_object"} if mode == "json_object" else None)


def test_model_client_profile_keeps_dynamic_citations_and_original_validation(monkeypatch):
    from oe_studio.model import ModelClient, GroundedAnswer, ModelGenerationError
    monkeypatch.setenv("RUNTIME_TEST_API_KEY", "key")
    captured = []

    def serve(request):
        captured.append(json.loads(request.content))
        return response("openai", '{"answer":"supported","evidence_ids":["real"],"triple_indices":[0]}')

    context = {"evidence": [{"id": "real", "resolved": True}, {"id": "unresolved", "resolved": False}],
               "ontology_triples": [{"subject": "synthetic"}]}
    result, metadata = ModelClient(configured(), httpx.MockTransport(serve)).generate("safe", context, GroundedAnswer)
    assert result.evidence_ids == ["real"] and metadata["model_profile"]["id"] == "fixture"
    grammar = captured[0]["response_format"]["json_schema"]["schema"]
    assert grammar["properties"]["evidence_ids"]["items"]["enum"] == ["real"]
    assert grammar["properties"]["triple_indices"]["items"]["maximum"] == 0
    with pytest.raises(ModelGenerationError) as caught:
        ModelClient(configured(), httpx.MockTransport(lambda req: response("openai", '{"publish":true}'))).generate(
            "safe", context, GroundedAnswer)
    assert caught.value.record["raw_output"] == '{"publish":true}'
    assert caught.value.record["validation_errors"]


def test_anthropic_schema_mode_never_grants_formatting_tools_on_old_models(monkeypatch):
    from oe_studio.llm_runtime import complete, CompletionError
    monkeypatch.setenv("RUNTIME_TEST_API_KEY", "key")
    requests = []
    with pytest.raises(CompletionError):
        asyncio.run(complete(configured("anthropic", model="claude-sonnet-4-20250514"), "safe", {}, SCHEMA,
                             transport=httpx.MockTransport(lambda req: requests.append(req) or response("anthropic"))))
    assert requests == []


@pytest.mark.parametrize("provider", PROVIDERS[:3])
def test_missing_provider_usage_is_unknown_not_sdk_token_estimates(provider, monkeypatch):
    from oe_studio.llm_runtime import complete
    monkeypatch.setenv("RUNTIME_TEST_API_KEY", "key")

    def serve(request):
        original = response(provider).json()
        for key in ("usage", "prompt_eval_count", "eval_count"):
            original.pop(key, None)
        if provider == "anthropic":
            # The Anthropic protocol requires the container; test absent counters.
            original["usage"] = {}
        return httpx.Response(200, json=original)

    _, metadata = asyncio.run(complete(configured(provider), "safe", {}, SCHEMA,
                                       transport=httpx.MockTransport(serve)))
    assert metadata["input_tokens"] is None and metadata["output_tokens"] is None


@pytest.mark.parametrize("provider", PROVIDERS[:3])
def test_partial_budget_configuration_blocks_actual_dispatch(provider, monkeypatch, tmp_path):
    from oe_studio.llm_runtime import complete, CompletionError
    monkeypatch.setenv("RUNTIME_TEST_API_KEY", "key")
    settings = configured(provider)
    settings.llm_smoke_budget_file = tmp_path / "budget.sqlite"
    requests = []
    with pytest.raises(CompletionError) as caught:
        asyncio.run(complete(settings, "safe", {}, SCHEMA,
                             transport=httpx.MockTransport(lambda req: requests.append(req) or response(provider))))
    assert requests == [] and not settings.llm_smoke_budget_file.exists()
    assert caught.value.record["failure_kind"] == "budget"
    assert caught.value.record["http_attempted"] is False


@pytest.mark.parametrize("provider", PROVIDERS[:3])
def test_credential_echo_is_redacted_from_audit_and_errors(provider, monkeypatch):
    from oe_studio.llm_runtime import complete, CompletionError
    monkeypatch.setenv("RUNTIME_TEST_API_KEY", "private-fixture-key")
    with pytest.raises(CompletionError) as echoed:
        asyncio.run(complete(configured(provider), "safe", {}, SCHEMA,
                             transport=httpx.MockTransport(lambda req: response(provider, "private-fixture-key"))))
    assert "private-fixture-key" not in str(echoed.value) + json.dumps(echoed.value.record)
    invalid = {"stop_reason": "max_tokens"} if provider == "anthropic" else (
        {"done": False} if provider == "ollama" else {"choices": []})
    with pytest.raises(CompletionError) as caught:
        asyncio.run(complete(configured(provider), "safe", {}, SCHEMA,
                             transport=httpx.MockTransport(lambda req: response(provider, "private-fixture-key", **invalid))))
    assert "private-fixture-key" not in str(caught.value) + json.dumps(caught.value.record)


@pytest.mark.parametrize("provider", PROVIDERS[:3])
def test_text_only_trustgraph_call_sends_plain_prompt_without_schema(provider, monkeypatch):
    from oe_studio.llm_runtime import complete
    monkeypatch.setenv("RUNTIME_TEST_API_KEY", "key")
    captured = []

    def serve(request):
        captured.append(json.loads(request.content))
        return response(provider, "synthetic plain text")

    text, metadata = asyncio.run(complete(configured(provider), "safe", "TG input", None,
                                          transport=httpx.MockTransport(serve)))
    assert text == "synthetic plain text" and metadata["http_attempted"] is True
    assert "response_format" not in captured[0] and "format" not in captured[0]
    assert "Return only JSON" not in json.dumps(captured[0])


def test_sdk_import_uses_bundled_catalog_without_network_or_background_fetch():
    program = '''
import httpx, socket, threading
attempts = []
def denied(*args, **kwargs):
    attempts.append("network")
    raise AssertionError("Unexpected SDK network")
httpx.get = denied
socket.socket.connect = denied
original_start = threading.Thread.start
def start(self):
    attempts.append(self.name)
    return original_start(self)
threading.Thread.start = start
from oe_studio import llm_runtime
assert attempts == [], attempts
assert not llm_runtime.litellm.callbacks
assert not llm_runtime.litellm.success_callback
assert not llm_runtime.litellm.input_callback
'''
    environment = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "services/api/src"),
                   "LITELLM_LOCAL_MODEL_COST_MAP": "False"}
    result = subprocess.run([sys.executable, "-c", program], env=environment, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_ambient_sdk_base_url_cannot_send_credentials_to_another_endpoint(monkeypatch):
    from oe_studio.llm_runtime import complete, CompletionError, litellm
    monkeypatch.setenv("RUNTIME_TEST_API_KEY", "private-fixture-key")
    monkeypatch.setattr(litellm, "api_base", "https://wrong-provider.invalid")
    requests = []
    with pytest.raises(CompletionError) as caught:
        asyncio.run(complete(configured("ollama"), "safe", {}, SCHEMA,
                             transport=httpx.MockTransport(lambda req: requests.append(req) or response("ollama"))))
    assert requests == []
    assert caught.value.record["http_attempted"] is False


@pytest.mark.parametrize("schema_name", ["GroundedAnswer", "ProposalDraft"])
def test_openai_strict_wire_schema_requires_all_fields_without_changing_local_schema(schema_name, monkeypatch):
    from oe_studio import model
    from oe_studio.llm_runtime import complete
    schema = getattr(model, schema_name).model_json_schema()
    original = json.dumps(schema, sort_keys=True)
    monkeypatch.setenv("RUNTIME_TEST_API_KEY", "key")

    def check(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert set(node.get("required", [])) == set(node.get("properties", {}))
                assert node["additionalProperties"] is False
            assert "default" not in node
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for value in node:
                check(value)

    def serve(request):
        check(json.loads(request.content)["response_format"]["json_schema"]["schema"])
        return response("openai")

    asyncio.run(complete(configured(), "safe", {}, schema, transport=httpx.MockTransport(serve)))
    assert json.dumps(schema, sort_keys=True) == original


@pytest.mark.parametrize("session", [None, "", "contains\nnewline"])
def test_opencode_requires_safe_frozen_session_before_dispatch(session, monkeypatch):
    from oe_studio.llm_runtime import complete, CompletionError
    monkeypatch.setenv("RUNTIME_TEST_API_KEY", "private-fixture-key")
    settings = configured("opencode_go")
    settings.llm_session_id = session
    requests = []
    with pytest.raises(CompletionError) as caught:
        asyncio.run(complete(settings, "safe", {}, SCHEMA,
                             transport=httpx.MockTransport(lambda req: requests.append(req) or response("openai"))))
    assert requests == [] and caught.value.record["http_attempted"] is False


@pytest.mark.parametrize("estimated", [False, True])
def test_opencode_reported_charge_and_estimate_are_distinct_from_list_cost(estimated, monkeypatch):
    from oe_studio.llm_runtime import complete
    monkeypatch.setenv("RUNTIME_TEST_API_KEY", "key")
    settings = configured("opencode_go")
    settings.llm_session_id = "frozen-session"
    usage = {"prompt_tokens": 7, "completion_tokens": 3, "cost": 0,
             "opencode": {"billing_source": "byok" if estimated else "go", "list_cost": .02,
                          "estimated": estimated, "allowance": .04}}
    _, metadata = asyncio.run(complete(settings, "safe", {}, SCHEMA,
                                       transport=httpx.MockTransport(lambda req: response("openai", usage=usage))))
    assert metadata["cost"] == 0 and metadata["cost_missing_reason"] is None
    assert metadata["cost_is_estimate"] is estimated
    assert metadata["provider_list_cost"] == .02


def test_serialized_request_size_is_bounded_before_http_dispatch(monkeypatch):
    from oe_studio.llm_runtime import complete, CompletionError
    monkeypatch.setenv("RUNTIME_TEST_API_KEY", "key")
    requests = []
    with pytest.raises(CompletionError) as caught:
        asyncio.run(complete(configured(), "safe", "x" * 1_048_577, None,
                             transport=httpx.MockTransport(lambda req: requests.append(req) or response("openai"))))
    assert requests == [] and caught.value.record["http_attempted"] is False


def test_budget_lock_wait_respects_total_deadline_and_never_dispatches_late(monkeypatch, tmp_path):
    import sqlite3
    from oe_studio.llm_runtime import complete, CompletionError
    from oe_studio.llm_budget import reserve_from_settings
    from tests.unit.test_llm_budget import configured as budget_configuration
    monkeypatch.setenv("RUNTIME_TEST_API_KEY", "key")
    budget, profile = budget_configuration(tmp_path)
    reserve_from_settings(budget, profile, {"max_tokens": 1})
    settings = configured(**profile, timeout=.05)
    # Warm the exact provider route, so the lock test reaches the reservation.
    asyncio.run(complete(configured(**profile), "safe", {}, SCHEMA,
                         transport=httpx.MockTransport(lambda req: response("openai"))))
    settings.llm_smoke_budget_file = budget.llm_smoke_budget_file
    settings.llm_smoke_price_file = budget.llm_smoke_price_file
    reservations = []

    def reserve(*args, **kwargs):
        reservations.append(kwargs.get("timeout"))
        return reserve_from_settings(*args, **kwargs)

    monkeypatch.setattr("oe_studio.llm_budget.reserve_from_settings", reserve)
    requests = []
    with sqlite3.connect(budget.llm_smoke_budget_file) as lock:
        lock.execute("BEGIN EXCLUSIVE")
        started = time.monotonic()
        with pytest.raises(CompletionError) as caught:
            asyncio.run(complete(settings, "safe", {}, SCHEMA,
                                 transport=httpx.MockTransport(lambda req: requests.append(req) or response("openai"))))
        assert time.monotonic() - started < .5
    assert requests == [] and caught.value.record["http_attempted"] is False
    assert len(reservations) == 1 and 0 < reservations[0] <= .05


def test_reservation_finishing_after_deadline_cannot_dispatch(monkeypatch):
    from oe_studio.llm_runtime import complete, CompletionError
    monkeypatch.setenv("RUNTIME_TEST_API_KEY", "key")
    asyncio.run(complete(configured(), "safe", {}, SCHEMA,
                         transport=httpx.MockTransport(lambda req: response("openai"))))
    reservations = []

    def reserve(*args, **kwargs):
        reservations.append(True)
        time.sleep(.07)

    monkeypatch.setattr("oe_studio.llm_budget.reserve_from_settings", reserve)
    requests = []
    with pytest.raises(CompletionError):
        asyncio.run(complete(configured(timeout=.05), "safe", {}, SCHEMA,
                             transport=httpx.MockTransport(lambda req: requests.append(req) or response("openai"))))
    assert requests == [] and reservations == [True]


def test_anthropic_json_object_cannot_silently_drop_the_requested_mode(monkeypatch):
    from oe_studio.llm_runtime import complete, CompletionError
    monkeypatch.setenv("RUNTIME_TEST_API_KEY", "key")
    requests = []
    with pytest.raises(CompletionError):
        asyncio.run(complete(configured("anthropic", structured_output="json_object"), "safe", {}, SCHEMA,
                             transport=httpx.MockTransport(lambda req: requests.append(req) or response("anthropic"))))
    assert requests == []
