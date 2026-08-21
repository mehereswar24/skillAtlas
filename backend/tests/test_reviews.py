"""Member-submitted company reviews.

The rules worth testing here are the ones that separate a review section from a
comment box: one review per person per company, an author who can edit only
their own, anonymity that actually withholds a name, an aggregate that reflects
what was written, and a section a signed-out visitor can read but not write to.
"""

# Each aggregate test gets a company of its own. The `db` fixture rolls each
# test back, but a shared company would still couple these tests to the order
# they happen to run in, and an aggregate assertion is only worth writing if it
# is exact.
AGGREGATE_COMPANY = "salesforce"
UNREVIEWED_COMPANY = "meta"
DELETION_COMPANY = "netflix"
PROFILE_COMPANY = "oracle"

VALID_BODY = (
    "Four rounds over three weeks. The coding round was the hardest part and "
    "the system design round was more of a conversation than a whiteboard."
)


def _write(client, headers, slug="stripe", **overrides):
    payload = {
        "rating": 4,
        "title": "Long loop, fair questions",
        "body_md": VALID_BODY,
        "interview_outcome": "offer",
        "interview_year": 2025,
    } | overrides
    return client.post(
        f"/api/v1/companies/{slug}/reviews", json=payload, headers=headers
    )


# --------------------------------------------------------------------------
# creating
# --------------------------------------------------------------------------


def test_a_signed_in_learner_can_write_a_review(client, auth):
    headers, _ = auth()
    response = _write(client, headers)
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["rating"] == 4
    assert body["company_slug"] == "stripe"
    assert body["interview_outcome"] == "offer"
    assert body["viewer_is_author"] is True
    # The discriminator that stops a client rendering this as sourced fact.
    assert body["kind"] == "member-review"
    # Nothing a user submits may claim to be seeded sample content.
    assert body["is_sample"] is False


def test_a_review_can_name_the_role_it_is_about(client, auth):
    headers, _ = auth()
    response = _write(client, headers, slug="stripe", role_slug="security-engineer")
    assert response.status_code == 201, response.text
    assert response.json()["role"]["slug"] == "security-engineer"
    assert response.json()["role"]["title"]


def test_a_role_from_another_company_is_rejected(client, auth):
    """`deep-learning-engineer` is real, but it is NVIDIA's, not Stripe's."""
    headers, _ = auth()
    response = _write(client, headers, slug="stripe", role_slug="deep-learning-engineer")
    assert response.status_code == 404

    # And it is accepted at the company that does have it.
    other, _ = auth()
    assert (
        _write(
            client, other, slug="nvidia", role_slug="deep-learning-engineer"
        ).status_code
        == 201
    )


def test_one_review_per_user_per_company(client, auth):
    headers, _ = auth()
    assert _write(client, headers).status_code == 201

    second = _write(client, headers, title="Actually, a second opinion")
    assert second.status_code == 409
    assert "already reviewed" in second.json()["detail"]

    # ...but the same person reviewing a *different* company is fine.
    assert _write(client, headers, slug="uber").status_code == 201


def test_two_learners_can_each_review_the_same_company(client, auth):
    first, _ = auth()
    second, _ = auth()
    assert _write(client, first).status_code == 201
    assert _write(client, second, rating=2).status_code == 201

    listing = client.get("/api/v1/companies/stripe/reviews").json()
    assert listing["summary"]["review_count"] >= 2


def test_a_rating_outside_one_to_five_is_rejected(client, auth):
    headers, _ = auth()
    assert _write(client, headers, rating=0).status_code == 422
    assert _write(client, headers, rating=6).status_code == 422


def test_an_unknown_outcome_is_rejected(client, auth):
    headers, _ = auth()
    assert _write(client, headers, interview_outcome="ghosted").status_code == 422


def test_reviewing_a_company_that_does_not_exist_is_404(client, auth):
    headers, _ = auth()
    assert _write(client, headers, slug="not-a-company").status_code == 404


# --------------------------------------------------------------------------
# reading, signed out
# --------------------------------------------------------------------------


def test_signed_out_visitors_can_read_reviews(client, auth):
    headers, _ = auth()
    _write(client, headers)

    response = client.get("/api/v1/companies/stripe/reviews")
    assert response.status_code == 200

    body = response.json()
    assert body["summary"]["review_count"] >= 1
    # No account, so no write affordance and nothing of their own to edit.
    assert body["viewer_can_write"] is False
    assert body["viewer_review_id"] is None


def test_signed_out_visitors_cannot_write(client):
    assert _write(client, headers={}).status_code == 401


def test_the_seeded_samples_are_labelled_as_samples(client):
    """Demo content must never pass as a real member's testimony."""
    body = client.get("/api/v1/companies/google/reviews").json()
    assert body["reviews"], "the seed ships sample reviews so the section is not empty"
    for review in body["reviews"]:
        assert review["is_sample"] is True


def test_reviews_come_back_newest_first(client, auth):
    first, _ = auth()
    second, _ = auth()
    _write(client, first, title="Written first")
    created = _write(client, second, title="Written second").json()

    reviews = client.get("/api/v1/companies/stripe/reviews").json()["reviews"]
    assert reviews[0]["id"] == created["id"]


def test_the_signed_in_viewer_learns_whether_they_can_write(client, auth):
    headers, _ = auth()

    before = client.get("/api/v1/companies/stripe/reviews", headers=headers).json()
    assert before["viewer_can_write"] is True
    assert before["viewer_review_id"] is None

    created = _write(client, headers).json()

    after = client.get("/api/v1/companies/stripe/reviews", headers=headers).json()
    assert after["viewer_can_write"] is False
    assert after["viewer_review_id"] == created["id"]


# --------------------------------------------------------------------------
# anonymity
# --------------------------------------------------------------------------


def test_an_anonymous_review_withholds_the_name(client, auth):
    headers, user = auth()
    client.patch(
        "/api/v1/auth/me", json={"display_name": "Jordan"}, headers=headers
    )
    created = _write(client, headers, is_anonymous=True).json()

    listing = client.get("/api/v1/companies/stripe/reviews").json()
    mine = next(r for r in listing["reviews"] if r["id"] == created["id"])

    assert mine["is_anonymous"] is True
    assert mine["author"]["display_name"] is None
    # The user id would deanonymise the author across their other reviews.
    assert mine["author"]["id"] is None
    # And the email is never in the payload, anonymous or not.
    assert user["email"] not in str(listing)


def test_a_signed_review_never_leaks_the_email(client, auth):
    headers, user = auth()
    _write(client, headers, is_anonymous=False)

    listing = client.get("/api/v1/companies/stripe/reviews").json()
    assert user["email"] not in str(listing)


def test_the_author_still_sees_their_own_anonymous_review_as_theirs(client, auth):
    headers, _ = auth()
    created = _write(client, headers, is_anonymous=True).json()

    listing = client.get("/api/v1/companies/stripe/reviews", headers=headers).json()
    mine = next(r for r in listing["reviews"] if r["id"] == created["id"])
    assert mine["viewer_is_author"] is True
    assert mine["author"]["display_name"] is None


def test_anonymity_can_be_switched_on_after_the_fact(client, auth):
    headers, _ = auth()
    client.patch("/api/v1/auth/me", json={"display_name": "Sam"}, headers=headers)
    created = _write(client, headers, is_anonymous=False).json()
    assert created["author"]["display_name"] == "Sam"

    updated = client.patch(
        f"/api/v1/reviews/{created['id']}",
        json={"is_anonymous": True},
        headers=headers,
    ).json()
    assert updated["author"]["display_name"] is None


# --------------------------------------------------------------------------
# editing and deleting — author only
# --------------------------------------------------------------------------


def test_the_author_can_edit_their_review(client, auth):
    headers, _ = auth()
    created = _write(client, headers).json()

    response = client.patch(
        f"/api/v1/reviews/{created['id']}",
        json={"rating": 2, "title": "Revised after the rejection"},
        headers=headers,
    )
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["rating"] == 2
    assert body["title"] == "Revised after the rejection"
    # A PATCH changes only what it names.
    assert body["body_md"] == VALID_BODY


def test_a_stranger_editing_your_review_gets_404_not_403(client, auth):
    """403 would confirm the id exists, turning the id space into an oracle."""
    author, _ = auth()
    stranger, _ = auth()
    created = _write(client, author).json()

    response = client.patch(
        f"/api/v1/reviews/{created['id']}", json={"rating": 1}, headers=stranger
    )
    assert response.status_code == 404
    # Indistinguishable from an id that was never issued.
    assert response.json() == client.patch(
        "/api/v1/reviews/98765432", json={"rating": 1}, headers=stranger
    ).json()


def test_a_stranger_deleting_your_review_gets_404_not_403(client, auth):
    author, _ = auth()
    stranger, _ = auth()
    created = _write(client, author).json()

    assert (
        client.delete(f"/api/v1/reviews/{created['id']}", headers=stranger).status_code
        == 404
    )
    # And it is still there.
    assert (
        client.get("/api/v1/companies/stripe/reviews").json()["summary"]["review_count"]
        >= 1
    )


def test_the_author_can_delete_their_review_and_write_a_new_one(client, auth):
    headers, _ = auth()
    created = _write(client, headers).json()

    assert (
        client.delete(f"/api/v1/reviews/{created['id']}", headers=headers).status_code
        == 204
    )
    # The one-per-company constraint frees up again.
    assert _write(client, headers, title="Second time around").status_code == 201


def test_editing_and_deleting_require_an_account(client, auth):
    headers, _ = auth()
    created = _write(client, headers).json()

    assert client.patch(f"/api/v1/reviews/{created['id']}", json={"rating": 1}).status_code == 401
    assert client.delete(f"/api/v1/reviews/{created['id']}").status_code == 401


# --------------------------------------------------------------------------
# the aggregate
# --------------------------------------------------------------------------


def test_the_aggregate_averages_what_was_actually_written(client, auth):
    ratings = [5, 4, 4, 1]
    for rating in ratings:
        headers, _ = auth()
        assert (
            _write(client, headers, slug=AGGREGATE_COMPANY, rating=rating).status_code
            == 201
        )

    summary = client.get(
        f"/api/v1/companies/{AGGREGATE_COMPANY}/reviews"
    ).json()["summary"]
    assert summary["review_count"] == len(ratings)
    assert summary["average_rating"] == round(sum(ratings) / len(ratings), 2)
    assert summary["distribution"] == {"1": 1, "2": 0, "3": 0, "4": 2, "5": 1}


def test_a_company_with_no_reviews_averages_none_not_zero(client):
    """0 is not a point on a 1-5 scale, and "unrated" is not "rated badly"."""
    summary = client.get(
        f"/api/v1/companies/{UNREVIEWED_COMPANY}/reviews"
    ).json()["summary"]
    assert summary["review_count"] == 0
    assert summary["average_rating"] is None
    assert summary["distribution"] == {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}


def test_deleting_a_review_removes_it_from_the_average(client, auth):
    first, _ = auth()
    second, _ = auth()
    created = _write(client, first, slug=DELETION_COMPANY, rating=5).json()
    _write(client, second, slug=DELETION_COMPANY, rating=1)

    def average():
        return client.get(f"/api/v1/companies/{DELETION_COMPANY}/reviews").json()[
            "summary"
        ]["average_rating"]

    assert average() == 3.0

    client.delete(f"/api/v1/reviews/{created['id']}", headers=first)
    assert average() == 1.0


def test_the_company_profile_carries_the_review_aggregate(client, auth):
    """So the profile page can show the rating without a second request."""
    headers, _ = auth()
    _write(client, headers, slug=PROFILE_COMPANY, rating=3)

    detail = client.get(f"/api/v1/companies/{PROFILE_COMPANY}").json()
    assert detail["reviews"]["review_count"] == 1
    assert detail["reviews"]["average_rating"] == 3.0
    # Still nested under its own key, not flattened in among the sourced fields.
    assert "average_rating" not in detail


# --------------------------------------------------------------------------
# helpful votes
# --------------------------------------------------------------------------


def test_helpful_votes_are_counted_and_toggle_off(client, auth):
    author, _ = auth()
    voter, _ = auth()
    created = _write(client, author).json()
    assert created["helpful_count"] == 0

    first = client.post(
        f"/api/v1/reviews/{created['id']}/vote?helpful=true", headers=voter
    ).json()
    assert first == {"helpful_count": 1, "not_helpful_count": 0, "viewer_vote": 1}

    # Same vote again clears it.
    second = client.post(
        f"/api/v1/reviews/{created['id']}/vote?helpful=true", headers=voter
    ).json()
    assert second == {"helpful_count": 0, "not_helpful_count": 0, "viewer_vote": None}


def test_switching_from_helpful_to_not_helpful_moves_the_vote(client, auth):
    author, _ = auth()
    voter, _ = auth()
    created = _write(client, author).json()

    client.post(f"/api/v1/reviews/{created['id']}/vote?helpful=true", headers=voter)
    switched = client.post(
        f"/api/v1/reviews/{created['id']}/vote?helpful=false", headers=voter
    ).json()
    assert switched == {"helpful_count": 0, "not_helpful_count": 1, "viewer_vote": -1}


def test_one_vote_per_user_however_many_times_they_click(client, auth):
    author, _ = auth()
    voters = [auth()[0] for _ in range(3)]
    created = _write(client, author).json()

    for headers in voters:
        for _ in range(3):
            client.post(
                f"/api/v1/reviews/{created['id']}/vote?helpful=true", headers=headers
            )

    # Three clicks each: on, off, on again.
    listing = client.get("/api/v1/companies/stripe/reviews").json()
    mine = next(r for r in listing["reviews"] if r["id"] == created["id"])
    assert mine["helpful_count"] == len(voters)


def test_you_cannot_vote_on_your_own_review(client, auth):
    headers, _ = auth()
    created = _write(client, headers).json()
    response = client.post(
        f"/api/v1/reviews/{created['id']}/vote", headers=headers
    )
    assert response.status_code == 409


def test_voting_requires_an_account(client, auth):
    author, _ = auth()
    created = _write(client, author).json()
    assert client.post(f"/api/v1/reviews/{created['id']}/vote").status_code == 401
