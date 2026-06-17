"""
Setup prompt and offline configuration package generation.
"""

import hashlib
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from rules_store import RulesStore
from skills_store import SkillsStore


class SetupPackageGenerator:
    def __init__(self, rules_store: RulesStore, skills_store: SkillsStore):
        self.rules_store = rules_store
        self.skills_store = skills_store

    def generate_prompt(
        self,
        base_url: str,
        agent_name: str = "generic",
        default_project_id: str = "",
    ) -> str:
        default_project_line = (
            f"Default project ID: {default_project_id}\n" if default_project_id else ""
        )
        return f"""# Fang Agent Cloud Setup

You are connecting to Fang Agent Cloud.

1. Call POST {base_url.rstrip("/")}/v1/bootstrap with the current workspace and capability profile.
2. Read the returned Markdown rules before acting.
3. Use selected_project_id for all future context writes when confidence is high.
4. Use runtime skill reads by default; do not install skills unless the user confirms.
5. Do not upload git-managed source code or plaintext secrets.
6. Before ending the session, save a structured context update.

API base URL: {base_url.rstrip("/")}
Agent name: {agent_name}
{default_project_line}API key: ask the user or read from the configured secret location.
Preferred response format: markdown+json
Recommended env var: FANG_CLOUD_API_KEY
"""

    def generate_package(
        self,
        output_dir: Path,
        base_url: str,
        agent_name: str = "generic",
        default_project_id: str = "",
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.utcnow().strftime("%Y%m%d")
        zip_path = output_dir / f"fang-agent-cloud-setup-{agent_name}-{stamp}.zip"

        rules = self.rules_store.current()
        registry = self.skills_store.registry()
        prompt = self.generate_prompt(base_url, agent_name, default_project_id)
        config = {
            "base_url": base_url.rstrip("/"),
            "agent": {
                "name": agent_name,
                "capabilities": {
                    "can_read_markdown": True,
                    "can_parse_json": True,
                    "can_call_http": True,
                    "can_run_shell": False,
                    "can_install_skills": False,
                    "supports_mcp": False,
                },
            },
            "default_project_id": default_project_id,
            "preferences": {
                "max_contexts": 5,
                "include_raw_logs": False,
                "response_format": "markdown+json",
            },
            "secret_policy": {
                "api_key_included": False,
                "recommended_env_var": "FANG_CLOUD_API_KEY",
            },
        }
        files: dict[str, str] = {
            "fang-agent-cloud-setup/README.md": (
                "# Fang Agent Cloud Setup\n\n"
                "This package contains non-secret bootstrap configuration for a new Agent.\n"
            ),
            "fang-agent-cloud-setup/bootstrap-config.json": json.dumps(
                config,
                indent=2,
                ensure_ascii=False,
            ),
            "fang-agent-cloud-setup/setup-prompt.md": prompt,
            "fang-agent-cloud-setup/rules/agent-rules.md": rules["markdown"],
            "fang-agent-cloud-setup/rules/agent-rules.json": json.dumps(
                rules["json"],
                indent=2,
                ensure_ascii=False,
            ),
            "fang-agent-cloud-setup/skills/registry-snapshot.json": json.dumps(
                registry,
                indent=2,
                ensure_ascii=False,
            ),
            "fang-agent-cloud-setup/skills/recommended-skills.md": self._recommended_skills(registry),
            "fang-agent-cloud-setup/examples/curl-bootstrap.sh": self._curl_example(base_url),
            "fang-agent-cloud-setup/examples/python-bootstrap.py": self._python_example(base_url),
            "fang-agent-cloud-setup/examples/save-context.example.json": json.dumps(
                self._save_context_example(default_project_id),
                indent=2,
                ensure_ascii=False,
            ),
        }
        manifest = self._manifest(files)
        files["fang-agent-cloud-setup/manifest.json"] = json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        )

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in files.items():
                archive.writestr(name, content)
        return zip_path

    @staticmethod
    def _manifest(files: dict[str, str]) -> dict[str, Any]:
        return {
            "version": "2026-06-14.1",
            "generated_at": datetime.utcnow().isoformat(),
            "api_key_included": False,
            "files": {
                name: hashlib.sha256(content.encode("utf-8")).hexdigest()
                for name, content in files.items()
            },
        }

    @staticmethod
    def _recommended_skills(registry: dict[str, Any]) -> str:
        lines = ["# Recommended Remote Skills", ""]
        for item in registry.get("skills", []):
            lines.append(f"- `{item['skill_id']}`: {item.get('description', '')}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _curl_example(base_url: str) -> str:
        return f"""#!/usr/bin/env bash
curl -X POST {base_url.rstrip("/")}/v1/bootstrap \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: $FANG_CLOUD_API_KEY" \\
  -d '{{"agent":{{"name":"generic","capabilities":{{}}}},"workspace":{{"query":"personal cloud"}}}}'
"""

    @staticmethod
    def _python_example(base_url: str) -> str:
        return f"""import os
import requests

response = requests.post(
    "{base_url.rstrip("/")}/v1/bootstrap",
    headers={{"X-API-Key": os.environ["FANG_CLOUD_API_KEY"]}},
    json={{"agent": {{"name": "generic", "capabilities": {{}}}}, "workspace": {{"query": "personal cloud"}}}},
    timeout=30,
)
response.raise_for_status()
print(response.json())
"""

    @staticmethod
    def _save_context_example(default_project_id: str) -> dict[str, Any]:
        return {
            "session_id": "example-session-id",
            "project": default_project_id or "personal-cloud",
            "agent_tool": "generic",
            "summary": "Summarize the current work state.",
            "current_goal": "Continue the project safely.",
            "completed_tasks": [],
            "pending_tasks": [],
            "key_decisions": [],
            "relevant_files": [],
            "environment": {},
            "metadata": {},
        }
