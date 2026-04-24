---
name: fasthtml
description: 'Build web apps in pure Python with FastHTML and MonsterUI. Triggers: fasthtml, fastht.ml, MonsterUI, HTMX Python, server-rendered Python web app.'
metadata:
  version: '3'
---

# FastHTML + MonsterUI

FastHTML is a Python framework that renders HTML on the server using HTMX and Starlette. You write routes as plain functions that return Python objects; FastHTML turns them into hypermedia. MonsterUI is a companion library that provides styled, composable UI components for FastHTML apps.

## Before writing code

Both projects publish machine-readable docs that change with each release. Fetch them before you write anything. Start with the index to see what is available, then pull the full context for API details.

```bash
# FastHTML
curl -sL https://raw.githubusercontent.com/AnswerDotAI/fasthtml/refs/heads/main/nbs/llms.txt
curl -sL https://raw.githubusercontent.com/AnswerDotAI/fasthtml/refs/heads/main/nbs/llms-ctx.txt

# MonsterUI
curl -sL https://raw.githubusercontent.com/AnswerDotAI/MonsterUI/refs/heads/main/docs/llms.txt
curl -sL https://raw.githubusercontent.com/AnswerDotAI/MonsterUI/refs/heads/main/docs/llms-ctx.txt
```

Do not rely on memorized knowledge of these APIs. The docs are the source of truth.
