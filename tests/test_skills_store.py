from skills_store import SkillsStore


def test_skills_registry_seeds_and_reads_skill(cloud_root):
    store = SkillsStore(cloud_root / "skills")

    registry = store.registry()
    content = store.read_skill("brainstorming")

    assert registry["skills"][0]["skill_id"] == "brainstorming"
    assert registry["remote_read_first"] is True
    assert "Clarify intent" in content
