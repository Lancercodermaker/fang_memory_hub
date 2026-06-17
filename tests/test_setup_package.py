import zipfile

from rules_store import RulesStore
from setup_package import SetupPackageGenerator
from skills_store import SkillsStore


def test_setup_package_does_not_embed_api_key(cloud_root):
    generator = SetupPackageGenerator(
        rules_store=RulesStore(cloud_root / "rules"),
        skills_store=SkillsStore(cloud_root / "skills"),
    )

    path = generator.generate_package(
        cloud_root / "setup-packages",
        base_url="https://fang-cloud.mardio.top",
        agent_name="codex",
        default_project_id="personal-cloud",
    )

    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        combined = "\n".join(
            archive.read(name).decode("utf-8")
            for name in names
            if name.endswith((".md", ".json", ".py", ".sh"))
        )

    assert "fang-agent-cloud-setup/setup-prompt.md" in names
    assert "change-me-to-strong-random-api-key" not in combined
    assert "FANG_CLOUD_API_KEY" in combined
    assert "api_key_included" in combined
