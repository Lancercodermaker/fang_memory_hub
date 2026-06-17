"""
Remote-readable skill registry.
"""

import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_SKILL_ID = "brainstorming"
DEFAULT_SKILL_MARKDOWN = """---
name: brainstorming
description: Clarify intent, constraints, and success criteria before creative implementation work.
---

# Brainstorming

Use this skill when a new feature, component, or behavior change needs clear product intent before implementation.

## Process

1. Identify the user's concrete goal.
2. List constraints, risks, and missing inputs.
3. Propose a minimal executable direction.
4. Continue with implementation once intent is clear enough.
"""


class SkillsStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.packages_dir = self.base_dir / "packages"
        self.collections_dir = self.base_dir / "collections"
        self.registry_file = self.base_dir / "registry.json"
        self._seed()

    def _seed(self) -> None:
        self.packages_dir.mkdir(parents=True, exist_ok=True)
        self.collections_dir.mkdir(parents=True, exist_ok=True)
        skill_dir = self.packages_dir / DEFAULT_SKILL_ID
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            skill_file.write_text(DEFAULT_SKILL_MARKDOWN, encoding="utf-8")

        digest = hashlib.sha256(skill_file.read_bytes()).hexdigest()
        manifest = {
            "skill_id": DEFAULT_SKILL_ID,
            "name": "Brainstorming",
            "version": "2026-06-14.1",
            "description": "Remote-readable planning skill for new agent work.",
            "read_url": f"/v1/skills/{DEFAULT_SKILL_ID}/read",
            "sha256": digest,
            "install_requires_user_confirmation": True,
            "tags": ["workflow", "planning"],
        }
        manifest_file = skill_dir / "manifest.json"
        manifest_file.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        if not self.registry_file.exists():
            self.registry_file.write_text(
                json.dumps(
                    {
                        "version": "2026-06-14.1",
                        "remote_read_first": True,
                        "auto_install": False,
                        "skills": [manifest],
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

    def registry(self) -> dict[str, Any]:
        return json.loads(self.registry_file.read_text(encoding="utf-8"))

    def list_skill_ids(self) -> list[str]:
        return [item["skill_id"] for item in self.registry().get("skills", [])]

    def manifest(self, skill_id: str) -> dict[str, Any]:
        manifest_file = self.packages_dir / skill_id / "manifest.json"
        if not manifest_file.exists():
            raise FileNotFoundError(f"Skill manifest not found: {skill_id}")
        return json.loads(manifest_file.read_text(encoding="utf-8"))

    def read_skill(self, skill_id: str) -> str:
        skill_file = self.packages_dir / skill_id / "SKILL.md"
        if not skill_file.exists():
            raise FileNotFoundError(f"Skill not found: {skill_id}")
        return skill_file.read_text(encoding="utf-8")
