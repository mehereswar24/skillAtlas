"""The public portfolio, and the privacy model around it.

This is the one feature that publishes a learner's data to the open internet,
so most of what is worth testing is what *does not* happen: an unpublished
profile is invisible, a failed attempt is not a shipped project, and an email
address never appears in a response no matter which switches are on.
"""

import itertools
import json

from tests.conftest import complete_concept

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


# Handles are globally unique, and the rollback in `conftest.db` does not
# reliably undo committed writes on SQLite — pysqlite's SAVEPOINT handling is
# the same reason the email fixture there counts rather than reusing a fixed
# address. So every test mints its own handle rather than trusting that the
# previous test's is gone.
_handles = itertools.count(1)


def new_handle(stem: str = "ada") -> str:
    return f"{stem}-{next(_handles)}"


def _create(client, headers, handle=None, **fields):
    """Create (or update) the caller's portfolio. Returns the settings body."""
    response = client.put(
        "/api/v1/portfolio/me",
        json={"handle": handle or new_handle(), **fields},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _publish(client, headers):
    response = client.post("/api/v1/portfolio/me/publish", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _live(client, headers, **fields):
    """A created *and* published portfolio. Returns its handle."""
    handle = _create(client, headers, **fields)["handle"]
    _publish(client, headers)
    return handle


def _ship(client, headers, slug="http-message-parser"):
    """Pass a project for real, through the normal submission endpoint."""
    project = client.get(f"/api/v1/projects/{slug}", headers=headers).json()
    payload = {
        "files": [
            {"path": f["path"], "content": f["content"]} for f in project["files"]
        ],
        "results": [{"test_id": t["id"], "passed": True} for t in project["tests"]],
    }
    result = client.post(
        f"/api/v1/projects/{slug}/submit", json=payload, headers=headers
    )
    assert result.status_code == 201, result.text
    assert result.json()["passed"] is True
    return project


def _fail(client, headers, slug="retry-with-backoff"):
    """Submit a genuinely failing attempt for a different project."""
    project = client.get(f"/api/v1/projects/{slug}", headers=headers).json()
    payload = {
        "files": [
            {"path": f["path"], "content": f["content"]} for f in project["files"]
        ],
        "results": [{"test_id": t["id"], "passed": False} for t in project["tests"]],
    }
    result = client.post(
        f"/api/v1/projects/{slug}/submit", json=payload, headers=headers
    )
    assert result.status_code == 201, result.text
    assert result.json()["passed"] is False
    return project


# --------------------------------------------------------------------------
# defaults
# --------------------------------------------------------------------------


def test_a_new_account_has_no_portfolio_and_nothing_public(client, auth):
    headers, _ = auth()
    body = client.get("/api/v1/portfolio/me", headers=headers).json()

    assert body["exists"] is False
    assert body["handle"] is None
    assert body["is_published"] is False
    assert body["public_url"] is None
    assert body["public_summary"], "the owner is always told what is public"


def test_creating_a_portfolio_does_not_publish_it(client, auth):
    headers, _ = auth()
    handle = new_handle()
    body = _create(client, headers, handle=handle, headline="Backend, mostly")

    assert body["exists"] is True
    assert body["is_published"] is False
    assert body["published_at"] is None
    assert body["public_url"] == f"/u/{handle}"
    assert body["headline"] == "Backend, mostly"


def test_the_owners_settings_page_requires_a_session(client):
    assert client.get("/api/v1/portfolio/me").status_code == 401


# --------------------------------------------------------------------------
# privacy: the part that matters
# --------------------------------------------------------------------------


def test_an_unpublished_profile_is_404_for_a_stranger_but_visible_to_its_owner(
    client, auth
):
    owner_headers, _ = auth()
    handle = _create(client, owner_headers)["handle"]

    # Anonymous.
    assert client.get(f"/api/v1/portfolio/{handle}").status_code == 404

    # A different, signed-in learner is just as much a stranger.
    other_headers, _ = auth()
    assert (
        client.get(f"/api/v1/portfolio/{handle}", headers=other_headers).status_code
        == 404
    )

    # The owner sees it, flagged as a preview rather than as a live page.
    mine = client.get(f"/api/v1/portfolio/{handle}", headers=owner_headers)
    assert mine.status_code == 200, mine.text
    assert mine.json()["is_preview"] is True


def test_publishing_then_unpublishing_takes_effect_immediately(client, auth):
    headers, _ = auth()
    handle = _create(client, headers)["handle"]

    published = _publish(client, headers)
    assert published["is_published"] is True
    assert published["published_at"] is not None

    live = client.get(f"/api/v1/portfolio/{handle}")
    assert live.status_code == 200
    assert live.json()["is_preview"] is False

    taken_down = client.post("/api/v1/portfolio/me/unpublish", headers=headers)
    assert taken_down.status_code == 200
    assert taken_down.json()["is_published"] is False

    # No cache, no grace period: the very next request is gone.
    assert client.get(f"/api/v1/portfolio/{handle}").status_code == 404

    # And it can be put back up.
    _publish(client, headers)
    assert client.get(f"/api/v1/portfolio/{handle}").status_code == 200


def test_a_missing_handle_and_a_hidden_one_are_indistinguishable(client, auth):
    """A 403 would confirm the handle exists. Both are plain 404s."""
    headers, _ = auth()
    handle = _create(client, headers)["handle"]

    hidden = client.get(f"/api/v1/portfolio/{handle}")
    absent = client.get("/api/v1/portfolio/nobody-here-at-all")
    assert hidden.status_code == absent.status_code == 404
    assert hidden.json() == absent.json()


def test_the_email_address_never_appears_in_any_response(client, auth):
    headers, user = auth()
    email = user["email"]
    assert "@" in email

    _ship(client, headers)
    handle = _create(client, headers, headline="Backend engineer")["handle"]
    client.put(
        "/api/v1/portfolio/me", json={"show_project_code": True}, headers=headers
    )
    _publish(client, headers)

    for response in (
        client.get(f"/api/v1/portfolio/{handle}"),
        client.get(f"/api/v1/portfolio/{handle}", headers=headers),
        client.get("/api/v1/portfolio/me", headers=headers),
    ):
        assert response.status_code == 200, response.text
        assert email not in response.text
        # Not even the local part, which is usually the person's name.
        assert email.split("@")[0] not in response.text


def test_only_passed_submissions_appear(client, auth):
    headers, _ = auth()
    shipped = _ship(client, headers)
    failed = _fail(client, headers)

    handle = _live(client, headers)

    body = client.get(f"/api/v1/portfolio/{handle}").json()
    slugs = {p["slug"] for p in body["projects"]}
    assert shipped["slug"] in slugs
    assert failed["slug"] not in slugs

    # And the owner's settings page lists the same set — you cannot configure
    # a project you never shipped.
    settings = client.get("/api/v1/portfolio/me", headers=headers).json()
    assert {p["slug"] for p in settings["projects"]} == {shipped["slug"]}


def test_source_code_is_only_published_when_asked_for(client, auth):
    headers, _ = auth()
    _ship(client, headers)
    handle = _live(client, headers)

    default = client.get(f"/api/v1/portfolio/{handle}").json()
    assert default["projects"], "the ship itself is shown"
    assert default["projects"][0]["files"] == []
    assert default["projects"][0]["tests"] == []
    assert default["projects"][0]["entry_path"] is None

    client.put(
        "/api/v1/portfolio/me", json={"show_project_code": True}, headers=headers
    )
    opted_in = client.get(f"/api/v1/portfolio/{handle}").json()
    project = opted_in["projects"][0]
    assert project["files"], "the demo needs the files to run"
    assert project["entry_path"]
    assert project["tests"], "and the tests, so a visitor can re-run them"


def test_sections_can_be_switched_off_individually(client, auth):
    headers, _ = auth()
    _ship(client, headers)
    handle = _live(client, headers)

    assert client.get(f"/api/v1/portfolio/{handle}").json()["projects"]

    client.put(
        "/api/v1/portfolio/me",
        json={
            "show_projects": False,
            "show_points": False,
            "show_badges": False,
            "show_readiness": False,
            "show_concepts": False,
        },
        headers=headers,
    )
    stripped = client.get(f"/api/v1/portfolio/{handle}").json()
    assert stripped["projects"] == []
    assert stripped["tracks"] == []
    assert stripped["badges"] == []
    assert stripped["readiness"] == []
    assert stripped["points"] is None
    assert stripped["level"] is None
    # The handle and the words they wrote are still theirs to show.
    assert stripped["handle"] == handle


def test_a_single_project_can_be_hidden_without_hiding_the_rest(client, auth):
    headers, _ = auth()
    project = _ship(client, headers)
    handle = _live(client, headers)

    settings = client.get("/api/v1/portfolio/me", headers=headers).json()
    project_id = settings["projects"][0]["project_id"]

    hidden = client.patch(
        f"/api/v1/portfolio/me/projects/{project_id}",
        json={"is_visible": False, "note": "Wrote this one in a hurry"},
        headers=headers,
    )
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["projects"][0]["is_visible"] is False

    body = client.get(f"/api/v1/portfolio/{handle}").json()
    assert project["slug"] not in {p["slug"] for p in body["projects"]}

    shown = client.patch(
        f"/api/v1/portfolio/me/projects/{project_id}",
        json={"is_visible": True},
        headers=headers,
    )
    assert shown.status_code == 200
    body = client.get(f"/api/v1/portfolio/{handle}").json()
    assert body["projects"][0]["note"] == "Wrote this one in a hurry"


def test_a_project_you_never_shipped_cannot_be_configured(client, auth):
    headers, _ = auth()
    _create(client, headers)
    response = client.patch(
        "/api/v1/portfolio/me/projects/999999",
        json={"is_visible": True},
        headers=headers,
    )
    assert response.status_code == 404


def test_deleting_the_portfolio_frees_the_handle_and_takes_the_page_down(client, auth):
    headers, _ = auth()
    handle = _live(client, headers)
    assert client.get(f"/api/v1/portfolio/{handle}").status_code == 200

    assert client.delete("/api/v1/portfolio/me", headers=headers).status_code == 204
    assert client.get(f"/api/v1/portfolio/{handle}").status_code == 404
    assert client.get("/api/v1/portfolio/me", headers=headers).json()["exists"] is False

    # The handle is genuinely free again.
    other_headers, _ = auth()
    _create(client, other_headers, handle=handle)


# --------------------------------------------------------------------------
# handles
# --------------------------------------------------------------------------


def test_reserved_handles_are_rejected(client, auth):
    headers, _ = auth()
    for handle in ("admin", "API", "login", "signup", "settings", "u", "support"):
        response = client.put(
            "/api/v1/portfolio/me", json={"handle": handle}, headers=headers
        )
        assert response.status_code == 422, f"{handle} was allowed: {response.text}"

    # And none of them left a half-created profile behind.
    assert client.get("/api/v1/portfolio/me", headers=headers).json()["exists"] is False


def test_handles_are_unique_case_insensitively(client, auth):
    first_headers, _ = auth()
    handle = _create(client, first_headers, handle=new_handle("Alice"))["handle"]

    second_headers, _ = auth()
    for attempt in (handle.lower(), handle.upper(), handle):
        response = client.put(
            "/api/v1/portfolio/me", json={"handle": attempt}, headers=second_headers
        )
        assert response.status_code == 409, f"{attempt} was allowed: {response.text}"


def test_a_handle_resolves_whatever_case_it_is_typed_in(client, auth):
    headers, _ = auth()
    handle = _live(client, headers, handle=new_handle("Alice"))

    for typed in (handle, handle.lower(), handle.upper()):
        response = client.get(f"/api/v1/portfolio/{typed}")
        assert response.status_code == 200, typed
        # The capitalisation they chose is what gets displayed.
        assert response.json()["handle"] == handle


def test_keeping_your_own_handle_is_not_a_conflict(client, auth):
    headers, _ = auth()
    handle = _create(client, headers, handle=new_handle("Alice"))["handle"]

    again = client.put(
        "/api/v1/portfolio/me",
        json={"handle": handle.lower(), "headline": "Renamed the case"},
        headers=headers,
    )
    assert again.status_code == 200, again.text
    assert again.json()["handle"] == handle.lower()


def test_malformed_handles_are_rejected(client, auth):
    headers, _ = auth()
    for handle in (
        "ab",  # too short
        "a" * 31,  # too long
        "has spaces",
        "has.dots",
        "-leading",
        "trailing-",
        "emoji-\U0001f642",
        "slash/es",
        "",
    ):
        response = client.put(
            "/api/v1/portfolio/me", json={"handle": handle}, headers=headers
        )
        assert response.status_code == 422, f"{handle!r} was allowed: {response.text}"


def test_links_must_be_http(client, auth):
    headers, _ = auth()
    _create(client, headers)
    response = client.put(
        "/api/v1/portfolio/me",
        json={"website_url": "javascript:alert(1)"},
        headers=headers,
    )
    assert response.status_code == 422


def test_handle_check_answers_before_you_commit(client, auth):
    headers, _ = auth()
    handle = _create(client, headers, handle=new_handle("Alice"))["handle"]

    other_headers, _ = auth()
    taken = client.get(
        f"/api/v1/portfolio/handle-check?handle={handle.upper()}", headers=other_headers
    ).json()
    assert taken["available"] is False

    reserved = client.get(
        "/api/v1/portfolio/handle-check?handle=admin", headers=other_headers
    ).json()
    assert reserved["available"] is False

    free = client.get(
        f"/api/v1/portfolio/handle-check?handle={new_handle('grace')}",
        headers=other_headers,
    ).json()
    assert free["available"] is True

    # Your own handle is not "taken" from your side.
    mine = client.get(
        f"/api/v1/portfolio/handle-check?handle={handle.lower()}", headers=headers
    ).json()
    assert mine["available"] is True


def test_a_reserved_word_never_resolves_as_a_public_page(client):
    for handle in ("me", "admin", "settings"):
        assert client.get(f"/api/v1/portfolio/{handle}").status_code in (401, 404)


# --------------------------------------------------------------------------
# content
# --------------------------------------------------------------------------


def test_the_page_shows_completed_concepts_grouped_by_track(client, learner):
    headers, _, _ = learner
    complete_concept(client, headers, "backend-introduction")

    handle = _live(client, headers)

    body = client.get(f"/api/v1/portfolio/{handle}").json()
    assert body["tracks"], "a completed concept should surface under its track"
    group = body["tracks"][0]
    assert group["completed"]
    assert group["track_total"] >= len(group["completed"])
    assert body["concepts_completed"] == sum(
        len(g["completed"]) for g in body["tracks"]
    )


def test_the_embedded_demo_carries_what_the_runtime_needs(client, auth):
    headers, _ = auth()
    project = _ship(client, headers)
    handle = _create(client, headers)["handle"]
    client.put(
        "/api/v1/portfolio/me", json={"show_project_code": True}, headers=headers
    )
    _publish(client, headers)

    published = client.get(f"/api/v1/portfolio/{handle}").json()["projects"][0]

    assert published["runtime"] == project["runtime"]
    assert published["entry_path"] in {f["path"] for f in published["files"]}
    assert {f["path"] for f in published["files"]} == {
        f["path"] for f in project["files"]
    }
    assert {t["id"] for t in published["tests"]} == {t["id"] for t in project["tests"]}


def test_the_owner_is_told_in_words_what_is_public(client, auth):
    headers, _ = auth()
    _create(client, headers)

    private = client.get("/api/v1/portfolio/me", headers=headers).json()
    assert any("private" in line.lower() for line in private["public_summary"])

    _publish(client, headers)
    public = client.get("/api/v1/portfolio/me", headers=headers).json()
    assert any("email" in line.lower() for line in public["public_summary"])


def test_publishing_without_a_handle_is_refused(client, auth):
    headers, _ = auth()
    assert (
        client.post("/api/v1/portfolio/me/publish", headers=headers).status_code == 404
    )


def test_the_public_payload_has_no_identifier_a_stranger_could_reuse(client, auth):
    """No user id, no email, no submission ids — nothing to correlate on."""
    headers, _ = auth()
    _ship(client, headers)
    handle = _live(client, headers)

    body = client.get(f"/api/v1/portfolio/{handle}").json()
    serialised = json.dumps(body)
    assert "email" not in serialised
    assert "user_id" not in serialised
