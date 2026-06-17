"""
JSON-backed metadata index for Agent Bootstrap.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from models import AgentContext, BootstrapContextSummary, CandidateProject, ProjectProfile


class IndexStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.projects_file = self.base_dir / "projects.json"
        self.contexts_file = self.base_dir / "contexts.json"
        self._ensure_files()

    def _ensure_files(self) -> None:
        if not self.projects_file.exists():
            self._write_json(self.projects_file, {"projects": {}})
        if not self.contexts_file.exists():
            self._write_json(self.contexts_file, {"contexts": {}})

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        tmp.replace(path)

    def upsert_project(self, profile: ProjectProfile) -> ProjectProfile:
        data = self._read_json(self.projects_file)
        if not profile.last_active_at:
            profile.last_active_at = datetime.utcnow().isoformat()
        data["projects"][profile.project_id] = profile.model_dump()
        self._write_json(self.projects_file, data)
        return profile

    def get_project(self, project_id: str) -> ProjectProfile | None:
        data = self._read_json(self.projects_file)
        raw = data["projects"].get(project_id)
        return ProjectProfile(**raw) if raw else None

    def list_projects(self) -> list[ProjectProfile]:
        data = self._read_json(self.projects_file)
        return [ProjectProfile(**raw) for raw in data["projects"].values()]

    def update_context(self, context: AgentContext) -> BootstrapContextSummary:
        data = self._read_json(self.contexts_file)
        summary = BootstrapContextSummary(
            session_id=context.session_id,
            summary=context.summary,
            current_goal=context.current_goal,
            pending_tasks=context.pending_tasks,
            relevant_files=context.relevant_files,
            updated_at=str(context.updated_at),
        )
        data["contexts"][context.session_id] = {
            "project_id": context.project,
            "agent_tool": context.agent_tool,
            **summary.model_dump(),
        }
        self._write_json(self.contexts_file, data)

        project = self.get_project(context.project) or ProjectProfile(
            project_id=context.project,
            display_name=context.project,
        )
        project.description = project.description or context.summary[:240]
        project.last_active_at = str(context.updated_at)
        self.upsert_project(project)
        return summary

    def latest_contexts(self, project_id: str, limit: int = 5) -> list[BootstrapContextSummary]:
        data = self._read_json(self.contexts_file)
        rows = [
            row for row in data["contexts"].values()
            if row.get("project_id") == project_id
        ]
        rows.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return [BootstrapContextSummary(**row) for row in rows[:limit]]

    def search(
        self,
        project_id: str = "",
        git_remote: str = "",
        path_fingerprint: str = "",
        query: str = "",
        limit: int = 5,
    ) -> list[CandidateProject]:
        candidates: list[CandidateProject] = []
        query_terms = {term.lower() for term in query.split() if term.strip()}

        for profile in self.list_projects():
            score = 0.0
            reasons: list[str] = []

            if project_id and profile.project_id == project_id:
                score += 1.0
                reasons.append("explicit_project_id")

            if git_remote and git_remote in profile.git_remotes:
                score += 0.85
                reasons.append("git_remote")

            if path_fingerprint and path_fingerprint in profile.path_fingerprints:
                score += 0.7
                reasons.append("path_fingerprint")

            searchable = " ".join(
                [profile.project_id, profile.display_name, profile.description]
                + profile.aliases
                + profile.tags
            ).lower()
            if query_terms and any(term in searchable for term in query_terms):
                score += 0.35
                reasons.append("keyword")

            if profile.last_active_at and score > 0:
                score += 0.05
                reasons.append("recent_activity")

            if score > 0:
                candidates.append(
                    CandidateProject(
                        project_id=profile.project_id,
                        score=round(min(score, 1.0), 2),
                        match_reasons=sorted(set(reasons)),
                    )
                )

        candidates.sort(key=lambda item: item.score, reverse=True)
        return candidates[:limit]
