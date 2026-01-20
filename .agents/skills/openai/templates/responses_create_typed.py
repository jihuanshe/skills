"""
Template: Typed OpenAI Responses API call.

Key pattern:
- Type the INPUT construction (content items, messages)
- Use DIRECT keyword arguments to client.responses.create()
- Do NOT use **kwargs unpack (causes ty no-matching-overload)

Copy into demos/ if you want a minimal repro.
Run:
  mise exec -- ty check demos/<file>.py
"""

from __future__ import annotations

from openai import AsyncOpenAI
from openai.types.responses import ResponseInputFileParam, ResponseInputTextParam
from openai.types.responses.response_input_param import Message
from openai.types.shared_params.reasoning import Reasoning


async def call_model_with_text(*, model: str, text: str) -> str:
    """Simple text input example."""
    client = AsyncOpenAI()

    text_item: ResponseInputTextParam = {"type": "input_text", "text": text}
    message: Message = {"role": "user", "content": [text_item]}

    resp = await client.responses.create(
        model=model,
        input=[message],
        stream=False,
    )
    return resp.output_text or ""


async def call_model_with_file(*, model: str, prompt: str, file_id: str) -> str:
    """File input example (e.g., PDF extraction)."""
    client = AsyncOpenAI()

    text_item: ResponseInputTextParam = {"type": "input_text", "text": prompt}
    file_item: ResponseInputFileParam = {"type": "input_file", "file_id": file_id}
    message: Message = {"role": "user", "content": [text_item, file_item]}

    resp = await client.responses.create(
        model=model,
        input=[message],
        stream=False,
    )
    return resp.output_text or ""


async def call_model_with_reasoning(*, model: str, text: str) -> str:
    """Reasoning example with typed config."""
    client = AsyncOpenAI()

    text_item: ResponseInputTextParam = {"type": "input_text", "text": text}
    message: Message = {"role": "user", "content": [text_item]}
    reasoning: Reasoning = {"effort": "medium"}

    resp = await client.responses.create(
        model=model,
        input=[message],
        reasoning=reasoning,
        stream=False,
    )
    return resp.output_text or ""
