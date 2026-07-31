"""The points ledger.

The invariant worth protecting: the ledger explains the total. If they can
drift apart, the dashboard is telling the learner a story the data does not
support.
"""

from tests.conftest import complete_concept


def _ledger(client, headers):
    response = client.get("/api/v1/progress/points", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_a_new_account_has_an_empty_ledger(client, auth):
    headers, _ = auth()
    assert _ledger(client, headers) == []


def test_completing_a_concept_writes_one_line(client, learner):
    headers, _, _ = learner
    result = complete_concept(client, headers, "internet-and-http")

    events = _ledger(client, headers)
    assert len(events) == 1
    event = events[0]
    assert event["kind"] == "concept"
    assert event["ref_slug"] == "internet-and-http"
    assert event["points"] == result["xp_earned"]
    assert "Internet" in event["label"]


def test_the_ledger_sums_to_the_profile_total(client, learner):
    headers, _, _ = learner
    complete_concept(client, headers, "internet-and-http")
    complete_concept(client, headers, "git-version-control")

    project = client.get(
        "/api/v1/projects/http-message-parser", headers=headers
    ).json()
    client.post(
        f"/api/v1/projects/{project['slug']}/submit",
        json={
            "files": [
                {"path": f["path"], "content": f["content"]} for f in project["files"]
            ],
            "results": [{"test_id": t["id"], "passed": True} for t in project["tests"]],
        },
        headers=headers,
    )

    events = _ledger(client, headers)
    assert {e["kind"] for e in events} == {"concept", "project"}

    profile = client.get("/api/v1/auth/me", headers=headers).json()["profile"]
    assert sum(e["points"] for e in events) == profile["xp"]


def test_prior_knowledge_writes_nothing_to_the_ledger(client, auth):
    """Claiming a concept skips content; it must not appear as points earned."""
    headers, _ = auth()
    client.post(
        "/api/v1/roadmaps",
        json={
            "track_slug": "backend-developer",
            "pace": "steady",
            "known_concept_slugs": ["internet-and-http"],
        },
        headers=headers,
    )
    assert _ledger(client, headers) == []


def test_a_failed_project_pays_nothing(client, auth):
    headers, _ = auth()
    project = client.get(
        "/api/v1/projects/http-message-parser", headers=headers
    ).json()
    client.post(
        f"/api/v1/projects/{project['slug']}/submit",
        json={
            "files": [
                {"path": f["path"], "content": f["content"]} for f in project["files"]
            ],
            "results": [
                {"test_id": t["id"], "passed": False} for t in project["tests"]
            ],
        },
        headers=headers,
    )
    assert _ledger(client, headers) == []


def test_the_ledger_is_newest_first_and_limited(client, learner):
    headers, _, _ = learner
    complete_concept(client, headers, "internet-and-http")
    complete_concept(client, headers, "git-version-control")

    events = _ledger(client, headers)
    assert events[0]["ref_slug"] == "git-version-control"

    limited = client.get("/api/v1/progress/points?limit=1", headers=headers).json()
    assert len(limited) == 1


def test_the_ledger_is_private(client, auth, learner):
    headers, _, _ = learner
    complete_concept(client, headers, "internet-and-http")

    intruder, _ = auth()
    assert _ledger(client, intruder) == []
    assert client.get("/api/v1/progress/points").status_code == 401
