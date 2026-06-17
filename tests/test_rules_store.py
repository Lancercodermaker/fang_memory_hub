from rules_store import RulesStore


def test_rules_store_seeds_default_rules(cloud_root):
    store = RulesStore(cloud_root / "rules")

    current = store.current()

    assert current["json"]["version"] == "2026-06-14.1"
    assert "Do not store git-managed project source" in current["markdown"]
    assert current["json"]["bootstrap_contract"]["must_not_store_secrets"] is True
