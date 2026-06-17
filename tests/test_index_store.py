from index_store import IndexStore
from models import AgentContext, ProjectProfile


def test_upsert_project_and_search_by_project_id(cloud_root):
    store = IndexStore(cloud_root / "indexes")
    store.upsert_project(ProjectProfile(project_id="personal-cloud", tags=["fastapi"]))

    result = store.search(project_id="personal-cloud", limit=5)

    assert result[0].project_id == "personal-cloud"
    assert result[0].score == 1.0
    assert "explicit_project_id" in result[0].match_reasons


def test_search_by_keyword_and_recent_activity(cloud_root):
    store = IndexStore(cloud_root / "indexes")
    store.upsert_project(
        ProjectProfile(
            project_id="personal-cloud",
            aliases=["fang-cloud"],
            tags=["agent-context"],
            description="FastAPI MinIO personal cloud",
            last_active_at="2026-06-14T12:00:00Z",
        )
    )

    result = store.search(query="minio agent", limit=5)

    assert result[0].project_id == "personal-cloud"
    assert "keyword" in result[0].match_reasons


def test_context_update_creates_project_and_latest_summary(cloud_root):
    store = IndexStore(cloud_root / "indexes")
    store.update_context(
        AgentContext(
            session_id="s1",
            project="fang-memory-hub",
            agent_tool="codex",
            summary="Bootstrap MVP context",
            current_goal="ship bootstrap",
            pending_tasks=["rules"],
            relevant_files=["main.py"],
        )
    )

    assert store.get_project("fang-memory-hub") is not None
    latest = store.latest_contexts("fang-memory-hub")
    assert latest[0].session_id == "s1"
    assert latest[0].pending_tasks == ["rules"]
