---
name: building-with-openai
description: "Type-safe OpenAI Responses API usage. Triggers: responses.create, AsyncOpenAI, input, tools, web_search, extra_body. For general type workflows, load exploring-types-with-ty first."
---

# Building with OpenAI (Python)

## Pre-flight check

Scan for anti-patterns before writing new code:

```bash
# Pattern 1: **kwargs unpack in SDK create calls (FORBIDDEN)
ast-grep -p '$OBJ.create(**$KWARGS)' -l python packages apps

# Pattern 2: Untyped kwargs (FORBIDDEN)
ast-grep -p 'create_kwargs: dict[str, Any]' -l python packages apps
ast-grep -p 'openai_kwargs: dict[str, Any]' -l python packages apps
```

If matches exist, **do not copy that pattern**.

## Golden path: Typed Responses API call

1. Type each content item (e.g., `ResponseInputTextParam`, `ResponseInputFileParam`)
2. Type the message (e.g., `Message` from `response_input_param`)
3. Type nested config dicts if needed (e.g., `Reasoning`)
4. Call `client.responses.create(...)` with **direct keyword arguments**

See template: `templates/responses_create_typed.py`

## OpenAI SDK-specific rules

### ❌ Do NOT use `**TypedDict` unpack

The SDK's `create` method uses overloads with keyword-only arguments. Unpacking a TypedDict causes `ty` to report `no-matching-overload`:

```python
# ❌ WRONG: ty reports no-matching-overload
kwargs: ResponseCreateParamsNonStreaming = {"model": "gpt-5.2", "input": [...]}
await client.responses.create(**kwargs)  # ty error!
```

### ✅ DO use direct keyword arguments

```python
# ✅ CORRECT: type the inputs, pass keywords directly
text_item: ResponseInputTextParam = {"type": "input_text", "text": prompt}
message: Message = {"role": "user", "content": [text_item]}

await client.responses.create(
    model="gpt-5.2",
    input=[message],
    stream=False,
)
```

### ❌ Do NOT import internal params types for unpacking

`ResponseCreateParamsNonStreaming` and similar types may not be publicly exported or may not work with `**` unpack. Import **content types** instead:

```python
# ✅ CORRECT: import content/message types
from openai.types.responses import ResponseInputTextParam, ResponseInputFileParam
from openai.types.responses.response_input_param import Message
```

## Escape hatch: Unmodeled fields

When the SDK typing is missing a brand-new parameter:

- Keep typed kwargs intact
- Pass new fields via `extra_body` (or `extra_headers` / `extra_query`) at the call boundary

```python
await client.responses.create(
    model="gpt-5.2",
    input=[message],
    extra_body={"new_experimental_param": True},  # Unmodeled field
)
```

See template: `templates/responses_create_escape_hatch_extra_body.py`

## Observability: logfire spans

Wrap OpenAI calls with stable, low-cardinality spans:

```python
with logfire.span("openai.responses.create", model=model):
    response = await client.responses.create(...)
```

Exception handling:

- Unhandled: traceback recorded automatically, span level set to Error
- Handled: use `span.record_exception(e)` and `span.set_level('warning'|'error')`
- **MUST NOT** use both `logfire.exception(...)` and `span.record_exception(...)` together

See template: `templates/responses_create_typed_with_logfire.py`

## Timeouts and retries

- Prefer explicit timeouts:
  - SDK call boundary: pass `timeout=...`
  - Or wrap with `asyncio.wait_for(...)` as a single choke point
- Retries should be:
  - Bounded
  - Jittered (for rate limits / transient failures)
  - Instrumented (logfire warning spans)

Keep retry policy in one place; do not sprinkle ad-hoc retries.

## Testing strategy

- Unit tests should not hit the real API by default
- For integration tests requiring a live model, mark with `@pytest.mark.live_llm` (skipped by default)
- Test coverage:
  - Typed param construction (static: via ty)
  - Error mapping / retries (dynamic: via mocks)
  - Span naming and exception recording (dynamic: via logfire test hooks)

## Quick validation checklist

- [ ] No `dict[str, Any]` request kwargs
- [ ] TypedDict types used end-to-end (including nested dicts)
- [ ] New/unmodeled fields isolated in `extra_body`/`extra_headers`/`extra_query`
- [ ] logfire span wraps each OpenAI call
- [ ] `mise exec -- ty check <file>` passes
- [ ] Production changes pass `mise lint` and tests
