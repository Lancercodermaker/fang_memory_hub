from context import ContextManager
from index_store import IndexStore
from models import AgentContext


def test_context_save_can_update_project_index(cloud_root):
    index = IndexStore(cloud_root / "indexes")
    manager = ContextManager(base_dir=cloud_root / "contexts", index_store=index)

    manager.save(
        AgentContext(
            session_id="session-1",
            project="personal-cloud",
            agent_tool="codex",
            summary="Finished bootstrap routes.",
            current_goal="Verify agent onboarding.",
            pending_tasks=["Open console"],
            relevant_files=["main.py"],
        )
    )

    project = index.get_project("personal-cloud")
    latest = index.latest_contexts("personal-cloud")

    assert project is not None
    assert "Finished bootstrap routes" in project.description
    assert latest[0].session_id == "session-1"
    assert latest[0].current_goal == "Verify agent onboarding."
