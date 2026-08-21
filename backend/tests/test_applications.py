"""The job tracker: stages, the timeline behind them, prep, and privacy."""

from tests.conftest import complete_concept

BASE = "/api/v1/applications"


def _create(client, headers, **payload):
    body = {"company_name": "A Startup", "role_title": "Backend Engineer"}
    body.update(payload)
    response = client.post(BASE, json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# --------------------------------------------------------------------------
# the board and free-text applications
# --------------------------------------------------------------------------


def test_stages_are_listed_in_pipeline_order(client, auth):
    headers, _ = auth()
    stages = client.get(f"{BASE}/stages", headers=headers).json()
    assert [s["value"] for s in stages] == [
        "saved",
        "applied",
        "screen",
        "onsite",
        "offer",
        "rejected",
        "withdrawn",
    ]
    assert [s["value"] for s in stages if s["is_terminal"]] == [
        "offer",
        "rejected",
        "withdrawn",
    ]


def test_a_free_text_application_needs_no_company(client, auth):
    """Most applications are to companies that are not in the seeded 30."""
    headers, _ = auth()
    created = _create(
        client,
        headers,
        company_name="Some Local Agency",
        role_title="Django Developer",
        location="Hyderabad",
        salary_note="₹9-12 LPA",
        source_url="https://example.com/careers/django-dev",
        notes="Found via a friend.",
    )

    assert created["company"] is None
    assert created["company_role"] is None
    # Nothing researched exists for an unlinked employer, and we do not invent it.
    assert created["prep"] is None
    assert created["stage"] == "saved"
    assert created["salary_note"] == "₹9-12 LPA"
    assert created["source_url"] == "https://example.com/careers/django-dev"

    detail = client.get(f"{BASE}/{created['id']}", headers=headers).json()
    assert detail["company_name"] == "Some Local Agency"
    assert detail["notes"] == "Found via a friend."


def test_an_application_needs_a_company_and_a_role(client, auth):
    headers, _ = auth()
    assert (
        client.post(BASE, json={"role_title": "Backend"}, headers=headers).status_code
        == 422
    )
    assert (
        client.post(BASE, json={"company_name": "Acme"}, headers=headers).status_code
        == 422
    )


def test_the_board_groups_every_stage(client, auth):
    headers, _ = auth()
    saved = _create(client, headers, company_name="Alpha")
    _create(client, headers, company_name="Beta", stage="applied")
    rejected = _create(client, headers, company_name="Gamma", stage="rejected")

    board = client.get(f"{BASE}/board", headers=headers).json()
    assert board["total"] == 3
    # The two terminal stages do not count as live applications.
    assert board["active"] == 2

    columns = {c["stage"]: c for c in board["columns"]}
    assert [a["id"] for a in columns["saved"]["applications"]] == [saved["id"]]
    assert [a["id"] for a in columns["rejected"]["applications"]] == [rejected["id"]]
    assert columns["onsite"]["applications"] == []
    assert columns["screen"]["label"] == "Screen"


def test_the_list_can_be_filtered_by_stage(client, auth):
    headers, _ = auth()
    _create(client, headers, company_name="Alpha")
    applied = _create(client, headers, company_name="Beta", stage="applied")

    only = client.get(f"{BASE}?stage=applied", headers=headers).json()
    assert [a["id"] for a in only] == [applied["id"]]
    assert client.get(f"{BASE}?stage=nonsense", headers=headers).status_code == 422


# --------------------------------------------------------------------------
# stages and the timeline
# --------------------------------------------------------------------------


def test_moving_through_the_stages_records_a_timeline(client, auth):
    headers, _ = auth()
    application = _create(client, headers)
    assert [e["to_stage"] for e in application["events"]] == ["saved"]
    assert application["events"][0]["from_stage"] is None
    assert application["applied_on"] is None

    for stage in ("applied", "screen", "onsite", "offer"):
        moved = client.post(
            f"{BASE}/{application['id']}/stage",
            json={"stage": stage, "note": f"moved to {stage}"},
            headers=headers,
        )
        assert moved.status_code == 200, moved.text
        application = moved.json()

    assert application["stage"] == "offer"
    # Every move is kept, in order, with what it moved from — this is the whole
    # point of the tracker over a status column in a spreadsheet.
    assert [(e["from_stage"], e["to_stage"]) for e in application["events"]] == [
        (None, "saved"),
        ("saved", "applied"),
        ("applied", "screen"),
        ("screen", "onsite"),
        ("onsite", "offer"),
    ]
    assert all(e["occurred_at"] for e in application["events"])
    assert application["events"][1]["note"] == "moved to applied"
    # Reaching "applied" backfills the date the learner did not type.
    assert application["applied_on"] is not None


def test_a_stage_can_be_backdated(client, auth):
    headers, _ = auth()
    application = _create(client, headers)
    moved = client.post(
        f"{BASE}/{application['id']}/stage",
        json={"stage": "applied", "occurred_at": "2026-01-09T10:00:00"},
        headers=headers,
    ).json()

    logged = next(e for e in moved["events"] if e["to_stage"] == "applied")
    assert logged["occurred_at"].startswith("2026-01-09")
    # The date the learner applied comes from the move, not from today.
    assert moved["applied_on"] == "2026-01-09"
    # The timeline reads chronologically, so a backdated move sorts before the
    # row written when the application was created.
    assert [e["to_stage"] for e in moved["events"]] == ["applied", "saved"]


def test_stages_may_be_skipped_or_walked_back(client, auth):
    """Real pipelines skip rounds, and a mistyped stage should be correctable."""
    headers, _ = auth()
    application = _create(client, headers)

    onsite = client.post(
        f"{BASE}/{application['id']}/stage", json={"stage": "onsite"}, headers=headers
    )
    assert onsite.status_code == 200
    back = client.post(
        f"{BASE}/{application['id']}/stage", json={"stage": "screen"}, headers=headers
    )
    assert back.status_code == 200
    assert back.json()["stage"] == "screen"
    assert len(back.json()["events"]) == 3


def test_moving_to_the_current_stage_is_rejected(client, auth):
    headers, _ = auth()
    application = _create(client, headers)
    response = client.post(
        f"{BASE}/{application['id']}/stage", json={"stage": "saved"}, headers=headers
    )
    assert response.status_code == 409


def test_an_unknown_stage_is_rejected(client, auth):
    headers, _ = auth()
    application = _create(client, headers)
    response = client.post(
        f"{BASE}/{application['id']}/stage", json={"stage": "ghosted"}, headers=headers
    )
    assert response.status_code == 422


def test_a_mislogged_event_can_be_removed_but_never_the_last(client, auth):
    headers, _ = auth()
    application = _create(client, headers)
    application = client.post(
        f"{BASE}/{application['id']}/stage", json={"stage": "applied"}, headers=headers
    ).json()

    stray = application["events"][-1]["id"]
    assert (
        client.delete(
            f"{BASE}/{application['id']}/events/{stray}", headers=headers
        ).status_code
        == 204
    )

    remaining = client.get(f"{BASE}/{application['id']}", headers=headers).json()
    assert len(remaining["events"]) == 1
    # Deleting history does not silently move the application backwards.
    assert remaining["stage"] == "applied"

    last = remaining["events"][0]["id"]
    assert (
        client.delete(
            f"{BASE}/{application['id']}/events/{last}", headers=headers
        ).status_code
        == 409
    )


# --------------------------------------------------------------------------
# linking to a seeded company role
# --------------------------------------------------------------------------


def test_linking_a_seeded_role_surfaces_its_prep_material(client, auth):
    headers, _ = auth()
    application = _create(
        client,
        headers,
        company_name=None,
        role_title=None,
        company_slug="google",
        company_role_slug="software-engineer",
    )

    assert application["company"]["slug"] == "google"
    assert application["company_role"]["slug"] == "software-engineer"
    # The labels are denormalised from the seed so the card survives a re-seed.
    assert application["company_name"] == "Google"
    assert application["role_title"].startswith("Software Engineer")

    prep = application["prep"]
    # The documented loop, verbatim from the company profile.
    assert prep["hiring_process_md"]
    assert prep["fetched_on"]
    assert prep["focus_areas"], "the role's focus areas should come through"
    assert any(a["concept_slug"] for a in prep["focus_areas"])
    assert prep["question_count"] > 0

    # Nothing completed yet, so readiness is zero and everything is a gap.
    assert prep["focus_readiness_percent"] == 0
    assert prep["role_readiness_percent"] == 0
    assert prep["role_slug"] == "backend-developer"
    assert prep["missing"], "an untouched learner is missing things for this role"
    assert all(gap["adds_percent"] > 0 for gap in prep["missing"])


def test_prep_tracks_what_the_learner_has_actually_completed(client, learner):
    headers, _, _ = learner
    application = _create(
        client,
        headers,
        company_name=None,
        role_title=None,
        company_slug="google",
        company_role_slug="software-engineer",
    )
    before = application["prep"]

    # The concept behind this role's "How the web actually works" focus area.
    complete_concept(client, headers, "frontend-internet")

    after = client.get(f"{BASE}/{application['id']}", headers=headers).json()["prep"]
    assert after["focus_readiness_percent"] > before["focus_readiness_percent"]
    covered = {a["label"] for a in after["focus_areas"] if a["is_completed"]}
    assert "How the web actually works" in covered
    # And it is no longer listed as something still missing.
    assert "frontend-internet" not in {gap["slug"] for gap in after["missing"]}


def test_linking_only_a_company_still_shows_its_loop(client, auth):
    headers, _ = auth()
    application = _create(
        client,
        headers,
        company_name=None,
        role_title="Contract role not on their careers page",
        company_slug="infosys",
    )
    assert application["company"]["slug"] == "infosys"
    assert application["company_role"] is None
    assert application["prep"]["hiring_process_md"]
    assert application["prep"]["focus_areas"] == []


def test_unknown_company_or_role_is_rejected(client, auth):
    headers, _ = auth()
    missing_company = client.post(
        BASE,
        json={"company_slug": "not-a-company", "role_title": "Dev"},
        headers=headers,
    )
    assert missing_company.status_code == 404

    missing_role = client.post(
        BASE,
        json={"company_slug": "google", "company_role_slug": "not-a-role"},
        headers=headers,
    )
    assert missing_role.status_code == 404

    # A role slug is meaningless without the company it belongs to.
    orphan = client.post(
        BASE,
        json={"company_role_slug": "software-engineer", "company_name": "Google"},
        headers=headers,
    )
    assert orphan.status_code == 422


# --------------------------------------------------------------------------
# editing
# --------------------------------------------------------------------------


def test_details_can_be_edited_and_a_company_unlinked(client, auth):
    headers, _ = auth()
    # Linked to a company, but the role title is the learner's own — naming a
    # company does not tell us which job they applied for.
    application = _create(
        client,
        headers,
        company_name=None,
        role_title="Payments Engineer",
        company_slug="stripe",
    )

    updated = client.patch(
        f"{BASE}/{application['id']}",
        json={"notes": "Referred by Priya", "salary_note": "not disclosed"},
        headers=headers,
    ).json()
    assert updated["notes"] == "Referred by Priya"
    assert updated["company"]["slug"] == "stripe"
    # Editing details never moves the application or rewrites its history.
    assert updated["stage"] == application["stage"]
    assert len(updated["events"]) == len(application["events"])

    unlinked = client.patch(
        f"{BASE}/{application['id']}",
        json={"unlink_company": True},
        headers=headers,
    ).json()
    assert unlinked["company"] is None
    assert unlinked["prep"] is None
    # The name typed at creation stays, so the card is still identifiable.
    assert unlinked["company_name"] == "Stripe"


def test_a_blank_company_name_is_rejected(client, auth):
    headers, _ = auth()
    application = _create(client, headers)
    response = client.patch(
        f"{BASE}/{application['id']}", json={"company_name": "   "}, headers=headers
    )
    assert response.status_code == 422


def test_a_pasted_job_description_is_kept_verbatim(client, auth):
    """The learner pastes the JD. Nothing is fetched — see the router docstring."""
    headers, _ = auth()
    jd = "Responsibilities:\n- Own the payments service\n- 3+ years Python\n"
    application = _create(client, headers, job_description=jd)

    assert application["has_job_description"] is True
    detail = client.get(f"{BASE}/{application['id']}", headers=headers).json()
    assert detail["job_description"] == jd


def test_no_endpoint_offers_to_fetch_a_listing(client):
    """A structural guard on the no-scraping rule.

    If somebody later adds an "import this URL" route, this fails and they have
    to argue with the rule rather than route around it.
    """
    paths = client.get("/openapi.json").json()["paths"]
    tracker = [p for p in paths if p.startswith("/api/v1/applications")]
    assert tracker, "the tracker should be mounted"
    banned = ("import", "fetch", "scrape", "crawl", "parse-url", "linkedin", "indeed")
    for path in tracker:
        assert not any(word in path.lower() for word in banned), path


# --------------------------------------------------------------------------
# privacy: 404, never 403
# --------------------------------------------------------------------------


def test_applications_require_an_account(client):
    assert client.get(BASE).status_code == 401
    assert client.post(BASE, json={"company_name": "A", "role_title": "B"}).status_code == 401


def test_another_user_cannot_read_or_change_your_application(client, auth):
    mine, _ = auth()
    theirs, _ = auth()
    application = _create(client, mine, company_name="Confidential Co")
    other = f"{BASE}/{application['id']}"

    # 404 rather than 403 everywhere, so ids cannot be probed for existence.
    assert client.get(other, headers=theirs).status_code == 404
    assert client.patch(other, json={"notes": "hi"}, headers=theirs).status_code == 404
    assert (
        client.post(f"{other}/stage", json={"stage": "offer"}, headers=theirs).status_code
        == 404
    )
    assert client.delete(other, headers=theirs).status_code == 404
    assert (
        client.delete(
            f"{other}/events/{application['events'][0]['id']}", headers=theirs
        ).status_code
        == 404
    )

    # And it is untouched, and invisible on their board.
    assert client.get(other, headers=mine).json()["stage"] == "saved"
    assert client.get(BASE, headers=theirs).json() == []
    assert client.get(f"{BASE}/board", headers=theirs).json()["total"] == 0


def test_deleting_your_own_application_removes_its_timeline(client, auth):
    headers, _ = auth()
    application = _create(client, headers)
    assert client.delete(f"{BASE}/{application['id']}", headers=headers).status_code == 204
    assert client.get(f"{BASE}/{application['id']}", headers=headers).status_code == 404
