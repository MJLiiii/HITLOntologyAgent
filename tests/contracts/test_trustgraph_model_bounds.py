import asyncio
import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[2] / 'infra/portal/bounded_ollama_client.py'
SPEC = importlib.util.spec_from_file_location('bounded_tg_model', PATH)
bounded = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bounded)


def test_nonthinking_schema_and_token_bounds_are_sent_to_real_wire_contract():
    class Client:
        async def generate(self, model, prompt, **kwargs):
            self.request = model, prompt, kwargs
            return {'response': '[]'}
    client = Client()
    schema = {'type': 'array', 'items': {'type': 'string'}}
    asyncio.run(bounded.generate(client, model=bounded.MODEL, system='system', prompt='data', response_format='json', schema=schema))
    assert client.request == (bounded.MODEL, 'system\n\ndata', {'think': False,
                              'options': {'temperature': 0, 'num_predict': 512, 'num_ctx': 4096}, 'format': schema})
    with pytest.raises(ValueError, match='pinned'):
        asyncio.run(bounded.generate(client, model='unapproved', system='', prompt=''))


def test_total_deadline_cancels_stalled_generation(monkeypatch):
    class Client:
        cancelled = False
        async def generate(self, *args, **kwargs):
            try:
                await asyncio.Event().wait()
            finally:
                self.cancelled = True
    monkeypatch.setattr(bounded, 'DEADLINE_SECONDS', 0.01)
    client = Client()
    with pytest.raises(TimeoutError):
        asyncio.run(bounded.generate(client, model=bounded.MODEL, system='', prompt=''))
    assert client.cancelled
