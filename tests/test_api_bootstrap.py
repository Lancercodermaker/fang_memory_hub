from fastapi.testclient import TestClient

import config
from main import app


def auth_headers():
    _, key = next(iter(config.API_KEYS.items()))
    return {"X-API-Key": key}


def test_rules_and_skills_endpoints():
    with TestClient(app) as client:
        rules = client.get("/v1/rules/current", headers=auth_headers())
        skills = client.get("/v1/skills/registry", headers=auth_headers())
        skill = client.get("/v1/skills/brainstorming/read", headers=auth_headers())

    assert rules.status_code == 200
    assert rules.json()["json"]["version"] == "2026-06-14.1"
    assert skills.status_code == 200
    assert skills.json()["skills"][0]["skill_id"] == "brainstorming"
    assert skill.status_code == 200
    assert "Clarify intent" in skill.json()["content"]


def test_index_and_bootstrap_endpoints():
    headers = auth_headers()
    with TestClient(app) as client:
        upsert = client.post(
            "/v1/index/projects",
            headers=headers,
            json={
                "project_id": "personal-cloud",
                "display_name": "Personal Cloud",
                "aliases": ["fang-cloud"],
                "tags": ["agent-context"],
                "description": "FastAPI MinIO personal cloud",
            },
        )
        search = client.post(
            "/v1/index/search",
            headers=headers,
            json={"query": "fang-cloud", "limit": 5},
        )
        bootstrap = client.post(
            "/v1/bootstrap",
            headers=headers,
            json={
                "agent": {"name": "generic", "capabilities": {}},
                "workspace": {"query": "fang-cloud"},
            },
        )

    assert upsert.status_code == 200
    assert search.status_code == 200
    assert search.json()["candidates"][0]["project_id"] == "personal-cloud"
    assert bootstrap.status_code == 200
    assert bootstrap.json()["bootstrap_id"]
    assert bootstrap.json()["json"]["rules"]["canonical_version"] == "2026-06-14.1"


def test_protected_endpoint_requires_api_key():
    with TestClient(app) as client:
        response = client.get("/v1/rules/current")

    assert response.status_code == 401
