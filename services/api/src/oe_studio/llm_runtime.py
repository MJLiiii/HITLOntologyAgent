"""One bounded, non-retrying LiteLLM request shared by Studio and TrustGraph."""
import asyncio
from copy import deepcopy
import json
import logging
import math
import os
import time

import httpx

from .artifacts import digest

# Must precede the SDK import: its default import starts a remote catalog fetch.
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
os.environ["DO_NOT_TRACK"] = "1"
import litellm  # noqa: E402
from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler  # noqa: E402
from openai import AsyncOpenAI  # noqa: E402
from openai.lib._pydantic import _ensure_strict_json_schema  # noqa: E402

litellm.drop_params = False
litellm.suppress_debug_info = True
litellm.turn_off_message_logging = True
litellm.set_verbose = False
litellm.num_retries = 0
litellm.num_retries_per_request = 0
for _logger in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy", "openai", "httpx", "httpcore"):
    logging.getLogger(_logger).setLevel(logging.CRITICAL)


class CompletionError(ValueError):
    def __init__(self, message, record):
        super().__init__(message)
        self.record = record


def _profile(settings):
    profile = getattr(settings, "resolved_llm_profile", None)
    if profile:
        return deepcopy(profile)
    if not getattr(settings, "model_url", "") or not getattr(settings, "model_name", ""):
        raise ValueError("No language model configured")
    from .llm_profiles import legacy_profile
    return legacy_profile(settings)


def _secret(settings, profile):
    if profile["id"] == "legacy-ollama":
        return getattr(settings, "model_api_key", "")
    env_name = profile.get("api_key_env")
    if not env_name:
        return ""
    from .llm_profiles import secret_value
    value = secret_value(settings, env_name)
    if not value:
        raise ValueError("Configured model credential is unavailable")
    return value


def _redact(value, secret):
    if not secret:
        return value
    if isinstance(value, str):
        return value.replace(secret, "[REDACTED]")
    if isinstance(value, dict):
        return {key: _redact(item, secret) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item, secret) for item in value]
    return value


def _strict_wire_schema(schema):
    """Use the locked OpenAI SDK's own strict conversion, preserving caller grammar."""
    schema = deepcopy(schema)

    def strip_defaults(node):
        node.pop("default", None)
        for key in ("properties", "$defs", "definitions"):
            for child in node.get(key, {}).values():
                strip_defaults(child)
        if isinstance(node.get("items"), dict):
            strip_defaults(node["items"])
        for key in ("anyOf", "allOf", "oneOf"):
            for child in node.get(key, []):
                strip_defaults(child)

    strip_defaults(schema)
    return _ensure_strict_json_schema(schema, path=(), root=schema)


def _reported_usd(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


class _BoundedClient(httpx.AsyncClient):
    """Budget at dispatch and bound decoded bytes before either SDK buffers them."""
    def __init__(self, settings, profile, payload, transport, deadline):
        super().__init__(timeout=profile["timeout"], transport=transport, follow_redirects=False, trust_env=False)
        self.settings, self.profile, self.payload = settings, profile, payload
        self.deadline = deadline
        self.dispatched = False
        self.http_attempted = False
        self.budget_blocked = False
        self.returned_model = None
        self.input_tokens = None
        self.output_tokens = None
        self.reported_cost = None
        self.cost_is_estimate = None
        self.provider_list_cost = None

    async def send(self, request, **kwargs):
        # Some provider adapters have their own retries independent of num_retries.
        # A per-completion guard prevents any second HTTP attempt, even after errors.
        if self.dispatched:
            raise ValueError("Model request already dispatched; retries are disabled")
        provider = self.profile["provider"]
        base = self.profile["base_url"].rstrip("/")
        endpoint = (base + "/api/chat" if provider == "ollama" else
                    (base + "/messages" if base.endswith("/v1") else base + "/v1/messages")
                    if provider == "anthropic" else base + "/chat/completions")
        if request.method != "POST" or request.url != httpx.URL(endpoint):
            raise ValueError("SDK request differs from the frozen model endpoint")
        if len(request.content) > 1_048_576:
            raise ValueError("Model request exceeded the input bound")
        wire = json.loads(request.content)
        if {"tools", "tool_choice", "functions", "function_call"} & wire.keys():
            raise ValueError("Model requests cannot grant tools; select a supported structured output mode")
        if wire.get("stream", False) is not False:
            raise ValueError("Streaming model responses are disabled")
        limit = (wire.get("options", {}).get("num_predict") if provider == "ollama" else
                 wire.get("max_completion_tokens", wire.get("max_tokens")))
        if type(limit) is not int or not 0 < limit <= self.profile["max_output_tokens"]:
            raise ValueError("SDK request omitted or increased the output token limit")
        temperature = wire.get("options", {}).get("temperature") if provider == "ollama" else wire.get("temperature")
        if self.profile.get("temperature") is not None and temperature != self.profile["temperature"]:
            raise ValueError("SDK request omitted or changed the configured temperature")
        requested_format = self.payload.get("response_format")
        if requested_format:
            if provider == "ollama":
                expected = "json" if requested_format["type"] == "json_object" else requested_format["json_schema"]["schema"]
                honored = wire.get("format") == expected
            elif provider == "anthropic":
                actual = wire.get("output_config", {}).get("format", wire.get("output_format", {}))
                honored = actual.get("type") == requested_format["type"]
            else:
                honored = wire.get("response_format") == requested_format
            if not honored:
                raise ValueError("SDK request omitted or changed the configured structured output mode")
        request.headers["User-Agent"] = "OntologyStudio/0.1.0 LiteLLM/1.106.6"
        if provider == "opencode_go":
            request.headers["x-opencode-session"] = self.settings.llm_session_id
        self.dispatched = True
        from .llm_budget import BudgetExceeded, reserve_from_settings
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Model completion deadline expired before reservation")
        try:
            reserve_from_settings(self.settings, self.profile, self.payload, timeout=remaining)
        except BudgetExceeded:
            self.budget_blocked = True
            raise
        if time.monotonic() >= self.deadline:
            raise TimeoutError("Model completion deadline expired before dispatch")
        self.http_attempted = True
        kwargs.update(stream=True, follow_redirects=False)
        response = await super().send(request, **kwargs)
        try:
            if 300 <= response.status_code < 400:
                raise ValueError("Model redirects are disabled")
            chunks, size = [], 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > self.profile["max_response_bytes"]:
                    raise ValueError("Model response exceeded the output bound")
                chunks.append(chunk)
            content = b"".join(chunks)
            if response.is_success:
                raw = json.loads(content)
                self.returned_model = raw.get("model")
                provider = self.profile["provider"]
                if provider == "ollama":
                    if raw.get("done") is not True:
                        raise ValueError("Model response was incomplete")
                    self.input_tokens, self.output_tokens = raw.get("prompt_eval_count"), raw.get("eval_count")
                else:
                    usage = raw.get("usage") or {}
                    self.input_tokens = usage.get("input_tokens" if provider == "anthropic" else "prompt_tokens")
                    self.output_tokens = usage.get("output_tokens" if provider == "anthropic" else "completion_tokens")
                    if provider == "opencode_go":
                        # OpenCode documents usage.cost in USD; allowance is a plan
                        # counter and list_cost is a separate full-price amount.
                        self.reported_cost = _reported_usd(usage.get("cost"))
                        opencode = usage.get("opencode") or {}
                        self.cost_is_estimate = opencode.get("estimated") is True
                        self.provider_list_cost = _reported_usd(opencode.get("list_cost"))
                if type(self.input_tokens) is not int or self.input_tokens < 0:
                    self.input_tokens = None
                if type(self.output_tokens) is not int or self.output_tokens < 0:
                    self.output_tokens = None
            # Body is decoded; do not ask HTTPX to decompress it a second time.
            headers = [(key, value) for key, value in response.headers.multi_items()
                       if key.lower() not in {"content-encoding", "content-length"}]
            return httpx.Response(response.status_code, headers=headers, content=content,
                                  request=request, extensions=response.extensions)
        finally:
            await response.aclose()


class _NoRetryHandler(AsyncHTTPHandler):
    """The stock handler retries connection/protocol errors even with SDK retries=0."""
    def __init__(self, client):
        self.client = client
        self.timeout = client.timeout

    async def post(self, url, data=None, json=None, params=None, headers=None, timeout=None,
                   stream=False, logging_obj=None, files=None, content=None):
        if isinstance(data, (str, bytes)):
            content, data = data, None
        request = self.client.build_request("POST", url, data=data, json=json, params=params,
                                            headers=headers, timeout=timeout, files=files, content=content)
        response = await self.client.send(request, stream=stream)
        response.raise_for_status()
        return response


async def complete(settings, system, context, output_schema, *, transport=None):
    """Return text plus credential-free audit metadata; validate output at the caller."""
    profile = _profile(settings)
    started = time.monotonic()
    deadline = started + profile["timeout"]
    provider = profile["provider"]
    sdk_provider = {"openai": "openai", "anthropic": "anthropic", "ollama": "ollama_chat",
                    "openai_compatible": "openai", "litellm_proxy": "openai", "opencode_go": "openai"}
    if provider not in sdk_provider:
        raise ValueError("Unsupported configured model provider")
    mode = profile["structured_output"]
    if mode not in {"json_schema", "json_object", "prompt_json"}:
        raise ValueError("Unsupported structured output mode")
    if output_schema is not None and mode != "json_schema":
        system += "\nReturn only JSON conforming to this schema:\n" + json.dumps(output_schema, ensure_ascii=False)
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": context if isinstance(context, str) else json.dumps(context, ensure_ascii=False)}]
    payload = {"model": sdk_provider[provider] + "/" + profile["model"], "messages": messages,
               "stream": False, "max_tokens": profile["max_output_tokens"]}
    if profile.get("temperature") is not None:
        payload["temperature"] = profile["temperature"]
    if output_schema is not None and mode == "json_schema":
        payload["response_format"] = {"type": "json_schema", "json_schema": {
            "name": "structured_output", "strict": True,
            "schema": _strict_wire_schema(output_schema) if sdk_provider[provider] == "openai" else output_schema}}
    elif output_schema is not None and mode == "json_object":
        payload["response_format"] = {"type": "json_object"}
    if provider == "ollama":
        payload["reasoning_effort"] = "none"
    metadata = {"provider": provider, "model": profile["model"], "model_profile_id": profile["id"],
                "model_profile_revision": profile["revision"], "model_profile": profile,
                "session_id": getattr(settings, "llm_session_id", None),
                "prompt_digest": digest(payload), "system_prompt": system, "temperature": profile.get("temperature"),
                "seed": None, "cost": None, "cost_missing_reason": "Provider did not report cost",
                "output_mode": mode if output_schema is not None else "text",
                "effective_parameters": {key: profile.get(key) for key in (
                    "temperature", "max_output_tokens", "timeout", "max_response_bytes", "structured_output")},
                "input_tokens": None, "output_tokens": None, "raw_output": None, "http_attempted": False}
    metadata["effective_parameters"]["structured_output"] = metadata["output_mode"]
    secret = ""
    http_client = None
    try:
        if provider == "opencode_go":
            session = getattr(settings, "llm_session_id", None)
            if not isinstance(session, str) or not 1 <= len(session) <= 200 or any(
                    ord(char) < 33 or ord(char) > 126 for char in session):
                raise ValueError("OpenCode Go requires a frozen session identifier")
        secret = _secret(settings, profile)
        async with _BoundedClient(settings, profile, payload, transport, deadline) as http_client:
            api_base = profile["base_url"]
            if provider == "anthropic" and api_base.rstrip("/").endswith("/v1"):
                api_base = api_base.rstrip("/")[:-3]
            if provider in {"anthropic", "ollama"}:
                client = _NoRetryHandler(http_client)
            else:
                client = AsyncOpenAI(api_key=secret or "unused-local-key", base_url=profile["base_url"],
                                     http_client=http_client, max_retries=0, timeout=profile["timeout"])
            result = await asyncio.wait_for(litellm.acompletion(
                **payload, api_base=api_base, api_key=secret or "unused-local-key", client=client,
                timeout=profile["timeout"], num_retries=0, max_retries=0, drop_params=False,
                fallbacks=[], caching=False, **{"no-log": True}), timeout=max(0, deadline - time.monotonic()))
            choice = result.choices[0]
            metadata.update(returned_model=http_client.returned_model,
                            input_tokens=http_client.input_tokens,
                            output_tokens=http_client.output_tokens,
                            raw_output=choice.message.content, http_attempted=http_client.http_attempted,
                            finish_reason=choice.finish_reason,
                            input_tokens_source="provider" if http_client.input_tokens is not None else "unavailable",
                            output_tokens_source="provider" if http_client.output_tokens is not None else "unavailable",
                            usage_source="provider" if all(value is not None for value in (
                                http_client.input_tokens, http_client.output_tokens)) else "partial" if any(
                                value is not None for value in (http_client.input_tokens, http_client.output_tokens)) else "unavailable")
            if http_client.reported_cost is not None:
                metadata.update(cost=http_client.reported_cost, cost_missing_reason=None,
                                cost_source="provider", cost_is_estimate=http_client.cost_is_estimate,
                                provider_list_cost=http_client.provider_list_cost)
            if choice.finish_reason != "stop" or choice.message.tool_calls or not isinstance(choice.message.content, str):
                raise ValueError("Model response was incomplete or requested a tool")
            if secret and secret in choice.message.content:
                raise ValueError("Model output contained a configured credential")
            metadata["elapsed_seconds"] = time.monotonic() - started
            return choice.message.content, _redact(metadata, secret)
    except Exception as exc:
        message = "Configured model unavailable or returned an invalid response: " + type(exc).__name__
        metadata.update(status="failed", error=message, validation_errors=[],
                        elapsed_seconds=time.monotonic() - started)
        if http_client is not None:
            metadata.update(http_attempted=http_client.http_attempted,
                            failure_kind="budget" if http_client.budget_blocked else "provider")
        raise CompletionError(message, _redact(metadata, secret)) from None
