"""Projects, submissions and the points they award.

Execution happens in the browser, so what is worth testing here is everything
*around* that: what the API hands out, what it accepts, and that points can
only be banked once.
"""

import json


def _project(client, slug="http-message-parser", headers=None):
    response = client.get(f"/api/v1/projects/{slug}", headers=headers or {})
    assert response.status_code == 200, response.text
    return response.json()


def _passing_payload(project):
    return {
        "files": [{"path": f["path"], "content": f["content"]} for f in project["files"]],
        "results": [{"test_id": t["id"], "passed": True} for t in project["tests"]],
    }


# --- content --------------------------------------------------------------


def test_every_project_hangs_off_a_concept_and_has_tests(client):
    projects = client.get("/api/v1/projects").json()
    assert projects, "the seed should ship projects"

    for summary in projects:
        detail = client.get(f"/api/v1/projects/{summary['slug']}").json()
        assert detail["concept_slug"], f"{summary['slug']} has no concept"
        assert detail["tests"], f"{summary['slug']} has no tests"
        assert any(f["is_entry"] for f in detail["files"]), (
            f"{summary['slug']} has no entry file"
        )


def test_projects_can_be_filtered_to_a_concept(client):
    filtered = client.get("/api/v1/projects?concept=internet-and-http").json()
    assert filtered
    assert {p["concept_slug"] for p in filtered} == {"internet-and-http"}


def test_the_solution_is_withheld_until_you_pass(client, auth):
    headers, _ = auth()
    assert _project(client, headers=headers)["solution_md"] is None


def test_unknown_project_returns_404(client):
    assert client.get("/api/v1/projects/does-not-exist").status_code == 404


# --- submission -----------------------------------------------------------


def test_a_passing_submission_awards_its_points_once(client, auth):
    headers, _ = auth()
    project = _project(client, headers=headers)
    payload = _passing_payload(project)

    first = client.post(
        f"/api/v1/projects/{project['slug']}/submit", json=payload, headers=headers
    )
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["passed"] is True
    assert body["xp_earned"] == project["xp_reward"]
    assert body["solution_md"], "a pass should reveal the worked solution"

    # Re-submitting keeps the record but must not pay again, or the leaderboard
    # becomes a clicking contest.
    again = client.post(
        f"/api/v1/projects/{project['slug']}/submit", json=payload, headers=headers
    ).json()
    assert again["passed"] is True
    assert again["xp_earned"] == 0
    assert again["total_xp"] == body["total_xp"]


def test_omitting_the_tests_you_failed_is_not_a_pass(client, auth):
    """The client reports results, so a partial report must not read as green."""
    headers, _ = auth()
    project = _project(client, headers=headers)

    payload = _passing_payload(project)
    payload["results"] = payload["results"][:1]

    body = client.post(
        f"/api/v1/projects/{project['slug']}/submit", json=payload, headers=headers
    ).json()
    assert body["passed"] is False
    assert body["xp_earned"] == 0


def test_results_for_another_projects_tests_are_ignored(client, auth):
    headers, _ = auth()
    project = _project(client, headers=headers)

    payload = _passing_payload(project)
    payload["results"] = [{"test_id": 9_999_999, "passed": True}]

    body = client.post(
        f"/api/v1/projects/{project['slug']}/submit", json=payload, headers=headers
    ).json()
    assert body["passed"] is False


def test_a_green_run_missing_the_required_api_is_held_back(client, auth):
    """`must_contain` is the one thing the server can check without running code."""
    headers, _ = auth()
    project = _project(client, headers=headers)

    payload = _passing_payload(project)
    payload["files"] = [{"path": project["files"][0]["path"], "content": "pass\n"}]

    body = client.post(
        f"/api/v1/projects/{project['slug']}/submit", json=payload, headers=headers
    ).json()
    assert body["passed"] is False
    assert body["xp_earned"] == 0
    assert body["rejected_reason"], "the learner should be told why"
    assert "def parse_request" in body["rejected_reason"]


def test_submitting_requires_an_account(client):
    project = _project(client)
    response = client.post(
        f"/api/v1/projects/{project['slug']}/submit", json=_passing_payload(project)
    )
    assert response.status_code == 401


def test_attempts_are_recorded_in_order(client, auth):
    headers, _ = auth()
    project = _project(client, headers=headers)
    payload = _passing_payload(project)
    payload["results"] = [{"test_id": payload["results"][0]["test_id"], "passed": False}]

    for _ in range(3):
        client.post(
            f"/api/v1/projects/{project['slug']}/submit", json=payload, headers=headers
        )

    submissions = client.get(
        f"/api/v1/projects/{project['slug']}/submissions", headers=headers
    ).json()
    assert [s["attempt_no"] for s in submissions] == [3, 2, 1]
    assert all(s["status"] == "failed" for s in submissions)


def test_submitted_files_are_kept(client, auth, db):
    from app.models.project import ProjectSubmission

    headers, _ = auth()
    project = _project(client, headers=headers)
    payload = _passing_payload(project)
    payload["files"][0]["content"] = "def parse_request(raw):\n    return {}\n"

    client.post(
        f"/api/v1/projects/{project['slug']}/submit", json=payload, headers=headers
    )

    row = db.query(ProjectSubmission).order_by(ProjectSubmission.id.desc()).first()
    stored = json.loads(row.files_json)
    assert stored[0]["content"] == payload["files"][0]["content"]


# --- badges ---------------------------------------------------------------


def test_shipping_a_project_earns_the_build_badges(client, auth):
    headers, _ = auth()
    project = _project(client, headers=headers)

    body = client.post(
        f"/api/v1/projects/{project['slug']}/submit",
        json=_passing_payload(project),
        headers=headers,
    ).json()

    slugs = {badge["slug"] for badge in body["new_badges"]}
    assert "first-build" in slugs
    # Passed everything on the first submission.
    assert "flawless-build" in slugs
