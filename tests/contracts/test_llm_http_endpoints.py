"""The runtime reaches controlled loopback endpoints without transport doubles."""
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread

import pytest

from oe_studio.llm_profiles import Profile, _snapshot, profile_settings
from oe_studio.llm_runtime import complete
from oe_studio.settings import Settings


SCHEMA = {"type": "object", "properties": {"answer": {"type": "string"}},
          "required": ["answer"], "additionalProperties": False}


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_native_client_routes_authenticates_and_parses_controlled_http_endpoint(provider, monkeypatch):
    key = "synthetic-loopback-provider-key"
    monkeypatch.setenv("LOOPBACK_TEST_API_KEY", key)
    requests = []
    text = '{"answer":"synthetic supported answer"}'
    if provider == "anthropic":
        body = {"id": "msg_loopback", "type": "message", "role": "assistant", "model": "claude-sonnet-4-5",
                "content": [{"type": "text", "text": text}], "stop_reason": "end_turn", "stop_sequence": None,
                "usage": {"input_tokens": 9, "output_tokens": 4}}
    else:
        body = {"id": "chat_loopback", "object": "chat.completion", "created": 1, "model": "loopback-model",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 9, "completion_tokens": 4, "total_tokens": 13}}
    encoded = json.dumps(body).encode()

    class Endpoint(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self):
            wire = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.path, dict(self.headers), wire))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Endpoint)
    worker = Thread(target=server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
    worker.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}" + "/v1"
        profile = _snapshot(Profile(id="loopback", provider=provider,
            model="claude-sonnet-4-5" if provider == "anthropic" else "loopback-model",
            base_url=base, api_key_env="LOOPBACK_TEST_API_KEY", purposes=["extraction"],
            max_output_tokens=16, max_response_bytes=4096, timeout=3))
        settings = profile_settings(Settings(_env_file=None), profile, session_id="loopback-session")
        returned, metadata = asyncio.run(complete(settings, "Use the synthetic fixture", "Synthetic source", SCHEMA))
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)

    assert returned == text
    assert metadata["http_attempted"] is True and metadata["finish_reason"] == "stop"
    assert (metadata["input_tokens"], metadata["output_tokens"]) == (9, 4)
    assert key not in json.dumps(metadata)
    assert len(requests) == 1
    path, headers, wire = requests[0]
    headers = {name.lower(): value for name, value in headers.items()}
    assert headers["user-agent"] == "OntologyStudio/0.1.0"
    assert not {"tools", "functions", "tool_choice", "function_call"} & wire.keys()
    assert "cookie" not in headers and key not in json.dumps(wire)
    if provider == "anthropic":
        assert path == "/v1/messages" and headers["x-api-key"] == key
        assert wire["max_tokens"] == 16
        # Claude uses its native output configuration without formatting tools.
        assert wire["output_config"]["format"]["type"] == "json_schema"
        assert wire["output_config"]["format"]["schema"] == SCHEMA
    else:
        assert path == "/v1/chat/completions" and headers["authorization"] == "Bearer " + key
        assert wire["max_completion_tokens"] == 16
        assert wire["response_format"]["json_schema"]["schema"] == SCHEMA
