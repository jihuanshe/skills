"""Prompt templates for tool outputs."""

from __future__ import annotations


def build_prompt(
    *,
    findings: list[str],
    recommendations: list[str],
    next_checks: list[str],
) -> str:
    def section(title: str, items: list[str]) -> list[str]:
        lines = [title]
        lines.extend(f"- {item}" for item in items)
        return lines

    parts: list[str] = []
    parts.extend(section("Findings", findings))
    parts.append("")
    parts.extend(section("Recommendations", recommendations))
    parts.append("")
    parts.extend(section("Next checks", next_checks))
    return "\n".join(parts).strip()
