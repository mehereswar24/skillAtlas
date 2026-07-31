"""Content, roadmap, dashboard and community endpoints."""

from tests.conftest import complete_concept


# --- content --------------------------------------------------------------


def test_every_domain_has_content(client):
    """No domain may be listed without a route behind it."""
    domains = client.get("/api/v1/domains").json()
    tracks = client.get("/api/v1/tracks").json()

    assert len(domains) >= 27
    without = [d["slug"] for d in domains if not d["has_content"]]
    assert without == [], f"domains with no track: {without}"

    tracked = {t["domain_slug"] for t in tracks}
    assert tracked == {d["slug"] for d in domains}


def test_quiz_answers_are_never_sent_to_the_client(client):
    concept = client.get("/api/v1/concepts/internet-and-http").json()
    assert concept["quiz"], "this concept should have a quiz"
    serialised = str(concept)
    assert "is_correct" not in serialised
    assert "correct" not in {k for q in concept["quiz"] for o in q["options"] for k in o}


def test_concept_detail_includes_graph_edges(client):
    concept = client.get("/api/v1/concepts/rest-api-design").json()
    assert {p["slug"] for p in concept["prerequisites"]} == {
        "internet-and-http",
        "programming-language-python",
    }
    assert "caching-strategies" in {u["slug"] for u in concept["unlocks"]}


def test_unknown_concept_returns_404(client):
    assert client.get("/api/v1/concepts/does-not-exist").status_code == 404


def test_lock_state_is_only_computed_for_a_signed_in_caller(client, auth):
    anonymous = client.get("/api/v1/concepts/rest-api-design").json()
    assert anonymous["status"] is None
    assert anonymous["is_locked"] is False  # nothing to compute against

    headers, _ = auth()
    identified = client.get("/api/v1/concepts/rest-api-design", headers=headers).json()
    assert identified["is_locked"] is True


# --- roadmaps -------------------------------------------------------------


def test_pace_changes_the_number_of_weeks(client, auth):
    slow_headers, _ = auth()
    fast_headers, _ = auth()

    slow = client.post(
        "/api/v1/roadmaps",
        json={"track_slug": "backend-developer", "daily_hours": 1},
        headers=slow_headers,
    ).json()
    fast = client.post(
        "/api/v1/roadmaps",
        json={"track_slug": "backend-developer", "daily_hours": 8},
        headers=fast_headers,
    ).json()

    assert len(slow["weeks"]) > len(fast["weeks"])
    assert slow["total_concepts"] == fast["total_concepts"]


def test_prior_knowledge_shortens_the_plan(client, auth):
    headers, _ = auth()
    baseline_headers, _ = auth()

    baseline = client.post(
        "/api/v1/roadmaps",
        json={"track_slug": "backend-developer", "daily_hours": 3},
        headers=baseline_headers,
    ).json()
    reduced = client.post(
        "/api/v1/roadmaps",
        json={
            "track_slug": "backend-developer",
            "daily_hours": 3,
            "known_concept_slugs": ["internet-and-http", "git-version-control"],
        },
        headers=headers,
    ).json()

    assert reduced["total_concepts"] == baseline["total_concepts"] - 2
    scheduled = {i["concept"]["slug"] for w in reduced["weeks"] for i in w["items"]}
    assert "internet-and-http" not in scheduled


def test_prior_knowledge_does_not_award_xp(client, auth):
    """Claiming knowledge skips content; it must not inflate the score."""
    headers, _ = auth()
    client.post(
        "/api/v1/roadmaps",
        json={
            "track_slug": "backend-developer",
            "daily_hours": 3,
            "known_concept_slugs": ["internet-and-http"],
        },
        headers=headers,
    )
    assert client.get("/api/v1/auth/me", headers=headers).json()["profile"]["xp"] == 0


def test_roadmap_persists_across_requests(client, learner):
    headers, _, created = learner
    fetched = client.get("/api/v1/roadmaps/current", headers=headers).json()
    assert fetched["id"] == created["id"]
    assert fetched["total_concepts"] == created["total_concepts"]


def test_no_roadmap_returns_404(client, auth):
    headers, _ = auth()
    assert client.get("/api/v1/roadmaps/current", headers=headers).status_code == 404


def test_unknown_goal_is_rejected_rather_than_guessed(client, auth):
    headers, _ = auth()
    response = client.post(
        "/api/v1/roadmaps", json={"goal": "Become a Wizard", "daily_hours": 2}, headers=headers
    )
    assert response.status_code == 404


def test_roadmap_can_be_created_from_a_goal_title(client, auth):
    headers, _ = auth()
    response = client.post(
        "/api/v1/roadmaps",
        json={"goal": "Become a Backend Developer", "daily_hours": 2},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["track"]["slug"] == "backend-developer"


def test_adding_a_concept_also_adds_its_prerequisites(client, learner):
    headers, _, _ = learner
    updated = client.post(
        "/api/v1/roadmaps/current/items",
        json={"concept_slugs": ["nlp-transformers"]},
        headers=headers,
    ).json()

    slugs = {i["concept"]["slug"] for w in updated["weeks"] for i in w["items"]}
    assert "nlp-transformers" in slugs
    assert "pytorch-fundamentals" in slugs  # its prerequisite came along


def test_roadmap_items_belong_to_their_owner(client, learner, auth):
    _, _, roadmap = learner
    item_id = roadmap["weeks"][0]["items"][0]["id"]

    intruder_headers, _ = auth()
    response = client.patch(
        f"/api/v1/roadmaps/items/{item_id}",
        json={"status": "skipped"},
        headers=intruder_headers,
    )
    assert response.status_code == 404


# --- dashboard ------------------------------------------------------------


def test_new_account_dashboard_shows_zeros_not_fiction(client, auth):
    headers, _ = auth()
    data = client.get("/api/v1/dashboard", headers=headers).json()

    assert data["stats"]["concepts_completed"] == 0
    assert data["stats"]["xp"] == 0
    assert data["stats"]["streak_days"] == 0
    assert data["current_track"] is None
    assert data["badges"] == []
    assert all(role["percent"] == 0 for role in data["roles"])
    # With no goal chosen, the "biggest gaps" ranking would be arbitrary.
    assert data["missing_skills"] == []


def test_dashboard_readiness_rises_with_real_progress(client, learner):
    headers, _, _ = learner
    before = client.get("/api/v1/dashboard", headers=headers).json()

    complete_concept(client, headers, "internet-and-http")
    complete_concept(client, headers, "git-version-control")

    after = client.get("/api/v1/dashboard", headers=headers).json()
    junior_before = next(r for r in before["roles"] if r["slug"] == "junior-backend-developer")
    junior_after = next(r for r in after["roles"] if r["slug"] == "junior-backend-developer")

    assert junior_after["percent"] > junior_before["percent"]
    assert after["stats"]["concepts_completed"] == 2
    assert after["stats"]["hours_invested"] == 2  # two 60-minute sessions


def test_missing_skills_target_the_chosen_goal(client, learner):
    headers, _, _ = learner
    complete_concept(client, headers, "internet-and-http")

    data = client.get("/api/v1/dashboard", headers=headers).json()
    assert data["missing_skills"], "there should be gaps left"
    assert {s["role_slug"] for s in data["missing_skills"]} == {"backend-developer"}
    assert all(s["percent_contribution"] > 0 for s in data["missing_skills"])


def test_next_up_only_suggests_unlocked_concepts(client, learner):
    headers, _, _ = learner
    data = client.get("/api/v1/dashboard", headers=headers).json()

    suggested = {c["slug"] for c in data["next_up"]}
    assert suggested
    for slug in suggested:
        assert not client.get(f"/api/v1/concepts/{slug}", headers=headers).json()["is_locked"]


# --- community ------------------------------------------------------------


def test_community_writes_require_an_account(client):
    response = client.post(
        "/api/v1/community/posts", json={"title": "Hello there", "content": "Hi"}
    )
    assert response.status_code == 401


def test_post_comment_and_vote_round_trip(client, auth):
    headers, _ = auth()
    post = client.post(
        "/api/v1/community/posts",
        json={
            "title": "How do you revise system design?",
            "content": "Looking for a routine that sticks.",
            "domain_slug": "backend",
        },
        headers=headers,
    ).json()

    client.post(
        f"/api/v1/community/posts/{post['id']}/comments",
        json={"content": "Draw the diagram from memory every day."},
        headers=headers,
    )
    vote = client.post(f"/api/v1/community/posts/{post['id']}/vote", headers=headers).json()
    assert vote == {"upvotes": 1, "viewer_has_voted": True}

    detail = client.get(f"/api/v1/community/posts/{post['id']}", headers=headers).json()
    assert detail["comment_count"] == 1
    assert len(detail["comments"]) == 1
    assert detail["domain"]["slug"] == "backend"


def test_voting_twice_removes_the_vote(client, auth):
    headers, _ = auth()
    post = client.post(
        "/api/v1/community/posts",
        json={"title": "Toggle test post", "content": "body"},
        headers=headers,
    ).json()

    client.post(f"/api/v1/community/posts/{post['id']}/vote", headers=headers)
    second = client.post(
        f"/api/v1/community/posts/{post['id']}/vote", headers=headers
    ).json()

    assert second == {"upvotes": 0, "viewer_has_voted": False}


def test_a_post_can_only_be_deleted_by_its_author(client, auth):
    author_headers, _ = auth()
    other_headers, _ = auth()

    post = client.post(
        "/api/v1/community/posts",
        json={"title": "Ownership test post", "content": "body"},
        headers=author_headers,
    ).json()

    assert client.delete(
        f"/api/v1/community/posts/{post['id']}", headers=other_headers
    ).status_code == 404
    assert client.delete(
        f"/api/v1/community/posts/{post['id']}", headers=author_headers
    ).status_code == 204
