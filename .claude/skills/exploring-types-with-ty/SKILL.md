---
name: exploring-types-with-ty
description: 'Explore SDK types and fix ty diagnostics. Triggers: new SDK/API, TypedDict/Literal construction, ty errors (Unknown, no-matching-overload), `dict[str, Any]` in PRs. Load BEFORE writing code.'
metadata:
  version: '1'
---

# Exploring Python Types with ty

## When to load this skill

| Trigger | Phase |
|---------|-------|
| Introducing a new SDK / API surface | Design-time |
| Planning data model for typed params | Design-time |
| Constructing TypedDict / Literal structures | Build-time |
| `ty` reports `Unknown`, `no-matching-overload`, or type mismatch | Build-time |
| PR contains `dict[str, Any]` or `Any` in SDK call context | Review-time |

## Core principles (also in AGENTS.md)

- **Narrow, don't widen.** Add explicit annotations—never widen to `Any`.
- **Type intermediate values.** Annotate each variable before composing into final structure.
- **SDK calls: direct keywords, not `**kwargs` unpack.** TypedDict unpack is incompatible with keyword-only overloads.
- **Escape hatches are localized.** Unmodeled fields go into `extra_body` / `extra_headers` / `extra_query`.
- **Types are design constraints.** Treat TypedDict/Literal as executable interface specs.

## Design-time: Type Reconnaissance

Use SDK typing as a source of truth for API shape, before writing implementation.

### What to extract from SDK types

| Information | How it helps design |
|-------------|---------------------|
| **Required vs optional fields** | Decide which params to expose in your API |
| **Literal enums** (`Literal["low", "medium", "high"]`) | Define config options, validate user input |
| **Nested structure** (TypedDict hierarchy) | Design internal data model to match or adapt |
| **Type absence** (field not in TypedDict) | Signal SDK lag -> decide: upgrade SDK or use escape hatch |

### Workflow: Inspect SDK types in `.venv`

```bash
# 1. Locate the module
ls .venv/lib/python3.13/site-packages/<sdk>/types/

# 2. Read type definitions (first 200 lines usually cover exports)
sed -n '1,200p' .venv/lib/python3.13/site-packages/<sdk>/types/<module>.py

# 3. Find specific TypedDict or Literal
rg "class.*TypedDict|Literal\[" .venv/lib/python3.13/site-packages/<sdk>/types/
```

### Output: Design decisions

After reconnaissance, document:

1. Which TypedDict/Literal types you'll use
2. Whether internal model mirrors SDK shape or needs adaptation
3. Any escape hatches needed for unmodeled fields

## Build-time: Type Narrowing Workflow

### Step 1: Create minimal repro under `demos/`

```python
# demos/<topic>_ty_repro.py
from <sdk>.types import SomeTypedDict, SomeParam

def build_request() -> SomeTypedDict:
    item: SomeParam = {"key": "value"}  # Type intermediate values
    return {"items": [item]}
```

### Step 2: Run ty

```bash
mise exec -- ty check demos/<topic>_ty_repro.py
```

### Step 3: Fix by narrowing

| Symptom | Fix |
|---------|-----|
| `Unknown` on dict literal | Add TypedDict annotation to variable |
| `Unknown` on list items | Type each item before adding to list |
| `no-matching-overload` on `**kwargs` | Use direct keyword arguments instead |
| `invalid-argument-type` | Check Literal values match SDK definition |

### Step 4: Port to production

Once repro passes `ty`, migrate the pattern to the real call site.

## Common ty diagnostics

### `Unknown` propagation

```python
# ❌ Unknown spreads
data = {"key": value}  # ty infers dict[str, Unknown]

# ✅ Annotate explicitly
data: SomeTypedDict = {"key": value}
```

### `no-matching-overload` with `**TypedDict`

SDK methods with `@overload` and keyword-only args reject TypedDict unpack:

```python
# ❌ ty error
kwargs: RequestParams = {"model": "...", "input": [...]}
await client.create(**kwargs)

# ✅ Direct keywords
await client.create(model="...", input=[...])
```

### `unresolved-import` for internal types

Some TypedDicts are not publicly exported. Import **content types** instead:

```python
# ❌ May not be exported
from sdk.types.internal import InternalParams

# ✅ Use public content types
from sdk.types import ContentParam, MessageParam
```

## Escape hatches (last resort)

- `cast(...)` — only after verifying shape matches target type
- Localized unsafe zone — contain in one function, not spread across codebase

## SDK-specific skills

For SDK-specific rules (overload patterns, escape hatch conventions, observability):

- **OpenAI SDK** -> load `building-with-openai` skill

## Verification checklist

- [ ] No `dict[str, Any]` for SDK request params
- [ ] All nested dicts are TypedDicts
- [ ] List items typed before composition
- [ ] SDK calls use direct keywords (not `**TypedDict`)
- [ ] `mise exec -- ty check <file>` passes
- [ ] Production changes pass `mise lint`
