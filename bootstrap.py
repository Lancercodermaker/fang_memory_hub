"""
Agent bootstrap matching and response assembly.
"""

from uuid import uuid4

from index_store import IndexStore
from models import (
    BootstrapJsonPayload,
    BootstrapRequest,
    BootstrapResponse,
    BootstrapRulesInfo,
    BootstrapSkillCandidate,
    BootstrapSkillsInfo,
)
from rules_store import RulesStore
from skills_store import SkillsStore


class BootstrapService:
    def __init__(
        self,
        index_store: IndexStore,
        rules_store: RulesStore,
        skills_store: SkillsStore,
    ):
        self.index_store = index_store
        self.rules_store = rules_store
        self.skills_store = skills_store

    def bootstrap(self, request: BootstrapRequest) -> BootstrapResponse:
        candidates = self.index_store.search(
            project_id=request.workspace.project_id,
            git_remote=request.workspace.git_remote,
            path_fingerprint=request.workspace.path_fingerprint,
            query=request.workspace.query,
            limit=5,
        )
        confidence = candidates[0].score if candidates else 0.0
        selected_project_id = candidates[0].project_id if candidates and confidence >= 0.75 else ""
        contexts = (
            self.index_store.latest_contexts(
                selected_project_id,
                limit=request.preferences.max_contexts,
            )
            if selected_project_id
            else []
        )

        rules = self.rules_store.current()
        registry = self.skills_store.registry()
        installed = set(request.local_state.installed_skills)
        runtime_candidates = [
            BootstrapSkillCandidate(
                skill_id=item["skill_id"],
                reason="Remote read is available; install only after user confirmation.",
                read_url=item.get("read_url", f"/v1/skills/{item['skill_id']}/read"),
            )
            for item in registry.get("skills", [])
            if item["skill_id"] not in installed
        ]

        payload = BootstrapJsonPayload(
            rules=BootstrapRulesInfo(
                canonical_version=rules["json"]["version"],
                markdown_ref="/v1/rules/render?profile=default-agent-project",
                machine_ref="/v1/rules/current",
            ),
            contexts=contexts,
            skills=BootstrapSkillsInfo(
                runtime_read_candidates=runtime_candidates,
                install_candidates=[],
                already_available=sorted(installed),
                registry_ref="/v1/skills/registry",
            ),
            next_actions=[
                "Read the returned markdown rules first.",
                "Use selected_project_id for future context writes when confidence is high.",
                "Update context before ending the session.",
            ],
        )
        return BootstrapResponse(
            bootstrap_id=str(uuid4()),
            confidence=confidence,
            selected_project_id=selected_project_id,
            candidate_projects=candidates,
            markdown=self._render_markdown(
                request=request,
                selected_project_id=selected_project_id,
                confidence=confidence,
                candidate_count=len(candidates),
                rules_markdown=rules["markdown"],
            ),
            json=payload,
        )

    @staticmethod
    def _render_markdown(
        request: BootstrapRequest,
        selected_project_id: str,
        confidence: float,
        candidate_count: int,
        rules_markdown: str,
    ) -> str:
        if selected_project_id:
            project_line = f"Selected project: `{selected_project_id}` with confidence `{confidence}`."
        elif candidate_count:
            project_line = (
                f"No automatic project selection. Top confidence `{confidence}` is below the "
                "0.75 threshold; ask the user to confirm."
            )
        else:
            project_line = "No candidate project found. Create or request a project profile."

        return f"""# Agent Bootstrap

Agent: `{request.agent.name}`
Workspace: `{request.workspace.path or "unknown"}`

{project_line}

## Rules

{rules_markdown.strip()}

## Next Actions

1. Read these rules before acting.
2. Use the JSON payload for machine-readable refs and candidate context.
3. Save a structured context update before ending the session.
"""
