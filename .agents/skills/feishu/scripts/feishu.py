from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any, Literal

import httpx

if TYPE_CHECKING:
    from collections.abc import Sequence

MAX_PAYLOAD_BYTES = 19_000


def _truncate(s: str, max_len: int) -> str:
    s = (s or "").strip()
    if len(s) <= max_len:
        return s
    return s[: max(0, max_len - 12)] + " ...(truncated)"


def _json_size(obj: dict[str, Any]) -> int:
    return len(json.dumps(obj, ensure_ascii=False).encode("utf-8"))


def _build_button(text: str, url: str) -> dict[str, Any]:
    return {
        "tag": "button",
        "text": {"tag": "plain_text", "content": text},
        "type": "default",
        "behaviors": [{"type": "open_url", "default_url": url}],
    }


def _build_card(
    title: str,
    content: str,
    *,
    subtitle: str = "",
    template: Literal["blue", "green", "yellow", "red"] = "blue",
    buttons: Sequence[dict[str, str]] | None = None,
) -> dict[str, Any]:
    elements: list[dict[str, Any]] = [
        {
            "tag": "markdown",
            "content": content,
        }
    ]

    if buttons:
        btn_elements = [_build_button(b["text"], b["url"]) for b in buttons]
        elements.append(
            {
                "tag": "column_set",
                "flex_mode": "none",
                "horizontal_spacing": "small",
                "columns": [{"tag": "column", "width": "auto", "elements": [btn]} for btn in btn_elements],
            }
        )

    header: dict[str, Any] = {
        "title": {"tag": "plain_text", "content": title},
        "template": template,
    }
    if subtitle:
        header["subtitle"] = {"tag": "plain_text", "content": subtitle}

    return {
        "msg_type": "interactive",
        "card": {
            "schema": "2.0",
            "header": header,
            "body": {"elements": elements},
        },
    }


def send_card(
    title: str,
    content: str,
    *,
    subtitle: str = "",
    template: Literal["blue", "green", "yellow", "red"] = "blue",
    buttons: Sequence[dict[str, str]] | None = None,
    webhook_url: str | None = None,
) -> None:
    """Send a rich-text card message to Feishu webhook.

    Args:
        title: Card title.
        content: Markdown content.
        subtitle: Optional subtitle.
        template: Header color (blue/green/yellow/red).
        buttons: List of {"text": "...", "url": "..."} dicts.
        webhook_url: Feishu webhook URL. Defaults to FEISHU_WEBHOOK env var.

    Raises:
        ValueError: If webhook URL is not configured.
        httpx.HTTPStatusError: If Feishu API returns an error.
    """
    url = webhook_url or os.environ.get("FEISHU_WEBHOOK")
    if not url:
        raise ValueError("FEISHU_WEBHOOK not configured")

    card = _build_card(title, content, subtitle=subtitle, template=template, buttons=buttons)

    if _json_size(card) > MAX_PAYLOAD_BYTES:
        card["card"]["body"]["elements"][0]["content"] = _truncate(content, 1200)

    response = httpx.post(url, json=card, timeout=10)
    response.raise_for_status()


if __name__ == "__main__":
    send_card(
        title="Test Message",
        content="This is a **test** from `feishu.py`",
        template="green",
    )
