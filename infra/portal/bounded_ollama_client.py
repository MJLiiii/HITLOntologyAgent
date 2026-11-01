"""Bounded local wire call used by the synthetic TrustGraph model processor."""
import asyncio

MODEL = 'oe-qwen3-smoke:1.7b'
DEADLINE_SECONDS = 120


async def generate(client, *, model, system, prompt, response_format=None, schema=None):
    if model != MODEL:
        raise ValueError('Only the pinned synthetic smoke model is admitted')
    text = system + '\n\n' + prompt
    if len(text.encode()) > 65_536:
        raise ValueError('Synthetic model input exceeds64KiB')
    kwargs = {'think': False, 'options': {'temperature': 0, 'num_predict': 512, 'num_ctx': 4096}}
    if response_format == 'json' and schema is not None:
        kwargs['format'] = schema
    response = await asyncio.wait_for(client.generate(model, text, **kwargs), timeout=DEADLINE_SECONDS)
    if not isinstance(response['response'], str) or len(response['response'].encode()) > 65_536:
        raise ValueError('Invalid or oversized synthetic model response')
    return response
