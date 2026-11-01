"""Explicit smoke-only extension; upstream source and image remain unchanged."""
from trustgraph.base import LlmResult
from trustgraph.model.text_completion.ollama.llm import Processor as UpstreamProcessor

from bounded_ollama_client import generate


class Processor(UpstreamProcessor):
    async def generate_content(self, system, prompt, model=None, temperature=None, response_format=None, schema=None):
        response = await generate(self.llm, model=model or self.default_model, system=system, prompt=prompt,
                                  response_format=response_format, schema=schema)
        return LlmResult(text=response['response'], in_token=int(response['prompt_eval_count']),
                         out_token=int(response['eval_count']), model=model or self.default_model)

    async def generate_content_stream(self, *args, **kwargs):
        raise ValueError('Streaming is not admitted by the bounded synthetic processor')
        yield  # Preserve the upstream async generator interface.
