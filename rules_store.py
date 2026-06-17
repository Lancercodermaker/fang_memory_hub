"""
Canonical rule storage and rendering.
"""

import json
from pathlib import Path
from typing import Any


DEFAULT_RULES_JSON: dict[str, Any] = {
    "version": "2026-06-14.1",
    "scope": "fang-personal-cloud-agent-workflow",
    "storage_boundaries": {
        "personal_cloud": "Store non-git personal files.",
        "agent_context": "Store project context, summaries, decisions, and index metadata.",
        "git_projects": "Do not store git-managed project source as long-term cloud files.",
        "secrets": "Never store plaintext secrets, API keys, SSH private keys, cookies, or .env files.",
    },
    "required_agent_behaviors": [
        "Call bootstrap before starting work when possible.",
        "Use selected_project_id for context writes.",
        "Read the returned markdown rules before acting.",
        "Update context after major milestones and before ending a session.",
        "Ask user when project match confidence is low.",
    ],
    "bootstrap_contract": {
        "must_use_project_id": True,
        "must_update_context": True,
        "must_not_store_git_source": True,
        "must_not_store_secrets": True,
    },
    "skill_policy": {
        "remote_read_first": True,
        "auto_install": False,
        "install_requires_user_confirmation": True,
    },
}


DEFAULT_RULES_MARKDOWN = """# Fang Agent Cloud Rules

Canonical version: 2026-06-14.1

## Storage Boundaries

- Do not store git-managed project source as long-term cloud files.
- Store project summaries, indexes, context, decisions, and non-secret configuration notes.
- Never store plaintext secrets, API keys, SSH private keys, cookies, browser profiles, or `.env` files.
- Personal files and non-git materials belong in personal cloud storage.
- Agent relay information belongs in contexts and indexes.

## Agent Behavior

- Call bootstrap before starting work when possible.
- Read returned Markdown rules before acting.
- Use `selected_project_id` for future context writes.
- Update context after major milestones and before ending a session.
- Ask the user before selecting a low-confidence project match.
- Read remote skills first; do not install skills unless the user confirms.
"""


class RulesStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.canonical_dir = self.base_dir / "canonical"
        self.adapters_dir = self.base_dir / "adapters"
        self.markdown_file = self.canonical_dir / "agent-rules.md"
        self.json_file = self.canonical_dir / "agent-rules.json"
        self._seed()

    def _seed(self) -> None:
        self.canonical_dir.mkdir(parents=True, exist_ok=True)
        self.adapters_dir.mkdir(parents=True, exist_ok=True)
        if not self.markdown_file.exists():
            self.markdown_file.write_text(DEFAULT_RULES_MARKDOWN, encoding="utf-8")
        if not self.json_file.exists():
            self.json_file.write_text(
                json.dumps(DEFAULT_RULES_JSON, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        generic_adapter = self.adapters_dir / "generic-markdown.md"
        if not generic_adapter.exists():
            generic_adapter.write_text(DEFAULT_RULES_MARKDOWN, encoding="utf-8")

    def current(self) -> dict[str, Any]:
        return {
            "markdown": self.markdown_file.read_text(encoding="utf-8"),
            "json": json.loads(self.json_file.read_text(encoding="utf-8")),
        }

    def render(self, profile: str = "default-agent-project", agent: str = "generic") -> str:
        current = self.current()
        return (
            current["markdown"].rstrip()
            + f"\n\nRendered profile: `{profile}`\nRendered agent: `{agent}`\n"
        )

    def machine_rules(self) -> dict[str, Any]:
        return self.current()["json"]
