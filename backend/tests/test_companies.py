"""Companies, role readiness, and the provenance rules the content must obey."""

from tests.conftest import complete_concept


def test_every_company_has_roles_and_a_verified_date(client):
    companies = client.get("/api/v1/companies").json()
    assert companies, "the seed should ship companies"

    for company in companies:
        assert company["role_count"] > 0, f"{company['slug']} has no roles"
        assert company["fetched_on"], (
            f"{company['slug']} has no fetched_on — the UI cannot say how stale it is"
        )


def test_every_question_cites_a_source(client):
    """The rule that separates this section from plausible-looking filler."""
    for company in client.get("/api/v1/companies").json():
        detail = client.get(f"/api/v1/companies/{company['slug']}").json()
        for role in detail["roles"]:
            payload = client.get(
                f"/api/v1/companies/{company['slug']}/roles/{role['slug']}"
            ).json()
            for question in payload["questions"]:
                assert question["source_url"].startswith("http"), (
                    f"{company['slug']}/{role['slug']}: "
                    f"{question['question'][:50]!r} has no usable source"
                )
                assert question["source_name"]


def test_focus_areas_point_at_concepts_that_exist(client):
    checked = 0
    for company in client.get("/api/v1/companies").json():
        detail = client.get(f"/api/v1/companies/{company['slug']}").json()
        for role in detail["roles"]:
            payload = client.get(
                f"/api/v1/companies/{company['slug']}/roles/{role['slug']}"
            ).json()
            for area in payload["focus_areas"]:
                if area["concept_slug"] is None:
                    continue
                assert (
                    client.get(f"/api/v1/concepts/{area['concept_slug']}").status_code
                    == 200
                ), f"{area['label']} points at a missing concept"
                checked += 1
    assert checked > 20, "most focus areas should link into the graph"


def test_readiness_is_zero_before_any_progress(client, auth):
    headers, _ = auth()
    role = client.get(
        "/api/v1/companies/google/roles/software-engineer", headers=headers
    ).json()
    assert role["readiness_percent"] == 0
    assert role["covered_weight"] == 0
    assert role["total_weight"] > 0


def test_readiness_rises_with_real_progress(client, learner):
    headers, _, _ = learner
    before = client.get(
        "/api/v1/companies/google/roles/software-engineer", headers=headers
    ).json()

    # The concept behind this role's "How the web actually works" focus area.
    complete_concept(client, headers, "frontend-internet")

    after = client.get(
        "/api/v1/companies/google/roles/software-engineer", headers=headers
    ).json()
    assert after["readiness_percent"] > before["readiness_percent"]

    covered = {a["label"] for a in after["focus_areas"] if a["is_completed"]}
    assert "How the web actually works" in covered


def test_unmapped_focus_areas_do_not_drag_readiness_down(client, auth):
    """A focus area with no concept written yet is excluded, not counted as failed."""
    headers, _ = auth()
    role = client.get(
        "/api/v1/companies/google/roles/software-engineer", headers=headers
    ).json()

    mapped = [a for a in role["focus_areas"] if a["concept_slug"]]
    unmapped = [a for a in role["focus_areas"] if not a["concept_slug"]]
    assert unmapped, "this role has an unmapped area, which is the point of the test"
    assert role["total_weight"] == sum(a["weight"] for a in mapped)


def test_adding_a_roles_focus_areas_extends_the_roadmap(client, learner):
    headers, _, roadmap = learner
    before = {i["concept"]["slug"] for w in roadmap["weeks"] for i in w["items"]}

    updated = client.post(
        "/api/v1/companies/nvidia/roles/deep-learning-engineer/add-to-roadmap",
        json={"concept_slugs": []},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text

    after = {i["concept"]["slug"] for w in updated.json()["weeks"] for i in w["items"]}
    assert "ai-data-scientist-deep-learning" in after
    # Prerequisites come along, which is the whole reason this goes through the graph.
    assert len(after) > len(before)


def test_adding_without_a_roadmap_is_rejected(client, auth):
    headers, _ = auth()
    response = client.post(
        "/api/v1/companies/google/roles/software-engineer/add-to-roadmap",
        json={"concept_slugs": []},
        headers=headers,
    )
    assert response.status_code == 404


def test_unknown_company_and_role_return_404(client):
    assert client.get("/api/v1/companies/not-a-company").status_code == 404
    assert (
        client.get("/api/v1/companies/google/roles/not-a-role").status_code == 404
    )


def test_industries_are_listed_for_filtering(client):
    industries = client.get("/api/v1/companies/industries").json()
    assert "Big Tech" in industries
    assert "IT Services (India)" in industries
