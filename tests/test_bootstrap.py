from models import (
    AgentCapabilities,
    AgentDescriptor,
    BootstrapPreferences,
    BootstrapRequest,
    BootstrapWorkspace,
    ProjectProfile,
)
from bootstrap import BootstrapService
from index_store import IndexStore
from rules_store import RulesStore
from skills_store import SkillsStore


def test_bootstrap_request_defaults():
    request = BootstrapRequest(
        agent=AgentDescriptor(
            name="generic",
            capabilities=AgentCapabilities(),
        ),
        workspace=BootstrapWorkspace(
            path="C:/Users/Fancy/project",
            query="continue the personal cloud work",
        ),
        preferences=BootstrapPreferences(),
    )

    assert request.agent.name == "generic"
    assert request.agent.capabilities.can_read_markdown is True
    assert request.workspace.query == "continue the personal cloud work"
    assert request.preferences.max_contexts == 5
    assert request.preferences.include_raw_logs is False


def test_bootstrap_selects_project_and_returns_rules_skills_contexts(cloud_root):
    index = IndexStore(cloud_root / "indexes")
    index.upsert_project(
        ProjectProfile(
            project_id="personal-cloud",
            aliases=["fang-cloud"],
            tags=["agent-context"],
            description="FastAPI MinIO personal cloud",
        )
    )
    service = BootstrapService(
        index_store=index,
        rules_store=RulesStore(cloud_root / "rules"),
        skills_store=SkillsStore(cloud_root / "skills"),
    )

    response = service.bootstrap(
        BootstrapRequest(
            agent=AgentDescriptor(name="codex"),
            workspace=BootstrapWorkspace(query="fang-cloud"),
        )
    )

    assert response.confidence >= 0.35
    assert response.candidate_projects[0].project_id == "personal-cloud"
    assert response.json.rules.canonical_version == "2026-06-14.1"
    assert response.json.skills.runtime_read_candidates[0].skill_id == "brainstorming"
    assert "Do not store git-managed project source" in response.markdown
