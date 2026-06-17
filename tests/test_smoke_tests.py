from smoke_tests import SmokeTestRunner


def test_smoke_runner_collects_named_results():
    runner = SmokeTestRunner()

    report = runner.run_static_checks()

    assert isinstance(report["results"][0], dict)
    assert {item["name"] for item in report["results"]} >= {
        "health_contract",
        "rules_contract",
        "skills_contract",
    }
    assert report["overall"] in {"pass", "fail"}
