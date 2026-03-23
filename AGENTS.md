# AGENTS.md

21 flat AI agent skills. Each `<name>/SKILL.md` is an SOP; `scripts/` and `templates/` are bundled tooling.
Full inventory and categorization paradigms → see `README.md`.

## Conventions

- **SKILL.md frontmatter**: YAML with `name`, `description`, `metadata.version` — required for skill discovery.
- **Scripts**: Bash or Python (inline `uv` script metadata). Must be runnable standalone.
- **Templates**: Example code referenced by SKILL.md via relative paths (`./templates/`, `./scripts/`).
- **Language**: Chinese or mixed Chinese-English. Technical terms keep English.
- **Naming**: Skill directories use `kebab-case`. No nesting — all skills are top-level siblings.

## Editing Rules

- Edit SKILL.md content freely, but never remove the YAML frontmatter.
- When adding a new skill, add it to the table in `README.md`.
- Do not re-introduce category subdirectories; skills stay flat. Classification lives only in README.
- Relative paths in SKILL.md (`./scripts/`, `./templates/`) must stay valid after edits.
