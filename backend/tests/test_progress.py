"""Completion, quiz grading, XP, streaks and badges."""

from datetime import date, timedelta

import pytest

from app.services.gamification import (
    current_streak,
    level_for_xp,
    level_progress,
    update_streak,
    xp_for_concept,
    xp_for_level,
)
from tests.conftest import complete_concept


# --- levelling maths ------------------------------------------------------


@pytest.mark.parametrize("level", range(1, 12))
def test_level_thresholds_round_trip(level):
    required = xp_for_level(level)
    assert level_for_xp(required) == level
    if required:
        assert level_for_xp(required - 1) == level - 1


def test_level_progress_splits_into_the_current_level():
    level, into, needed = level_progress(450)
    assert (level, into, needed) == (3, 450 - xp_for_level(3), xp_for_level(4) - xp_for_level(3))


def test_xp_scales_with_effort_and_quiz_score():
    assert xp_for_concept(40, 1.0) > xp_for_concept(40, 0.6)
    assert xp_for_concept(40, 1.0) > xp_for_concept(10, 1.0)
    # An out-of-range score cannot inflate the award.
    assert xp_for_concept(10, 5.0) == xp_for_concept(10, 1.0)


# --- streaks --------------------------------------------------------------


class _Profile:
    def __init__(self, last=None, streak=0, longest=0):
        self.last_active_on = last
        self.streak_days = streak
        self.longest_streak = longest


def test_consecutive_days_extend_the_streak():
    today = date(2026, 7, 31)
    profile = _Profile(last=today - timedelta(days=1), streak=4, longest=4)

    update_streak(profile, today)

    assert profile.streak_days == 5
    assert profile.longest_streak == 5


def test_a_second_completion_on_the_same_day_does_not_double_count():
    today = date(2026, 7, 31)
    profile = _Profile(last=today, streak=3, longest=7)

    update_streak(profile, today)

    assert profile.streak_days == 3
    assert profile.longest_streak == 7


def test_a_missed_day_restarts_the_streak_but_keeps_the_record():
    today = date(2026, 7, 31)
    profile = _Profile(last=today - timedelta(days=3), streak=9, longest=9)

    update_streak(profile, today)

    assert profile.streak_days == 1
    assert profile.longest_streak == 9


def test_displayed_streak_is_zero_once_a_day_has_been_missed():
    """Stored streak_days is only true on the day it was written."""
    today = date(2026, 7, 31)
    assert current_streak(_Profile(last=today, streak=6), today) == 6
    assert current_streak(_Profile(last=today - timedelta(days=1), streak=6), today) == 6
    assert current_streak(_Profile(last=today - timedelta(days=2), streak=6), today) == 0
    assert current_streak(_Profile(last=None), today) == 0


# --- completion flow ------------------------------------------------------


def test_prerequisites_advise_but_do_not_block_completion(client, learner):
    """Order is a recommendation, not a gate.

    The 85 imported tracks ship no dependency data, so the importer chains each
    concept to the one before it — a strict line. Enforcing that meant a learner
    could not open "Caching" without first finishing seven unrelated concepts,
    so `HARD_PREREQUISITES` is off and the chain only advises. Flip that flag
    and this test is the one that should fail.

    Note what is *not* being waived: the concept still has a quiz to pass, and
    `complete_concept` answers it. Completing with an unfinished prerequisite is
    allowed; completing without doing the work is not.
    """
    headers, _, _ = learner
    detail = client.get(
        "/api/v1/concepts/backend-learn-about-apis", headers=headers
    ).json()
    assert detail["missing_prerequisites"], "need an unmet prerequisite to prove this"

    # Answered inline rather than through `complete_concept`, which walks the
    # prerequisite chain first — that is exactly the thing this test needs left
    # unfinished. Submit once to obtain the review, then resubmit its answers.
    first = client.post(
        "/api/v1/progress/backend-learn-about-apis/complete",
        json={
            "answers": [
                {"question_id": q["id"], "option_id": q["options"][0]["id"]}
                for q in detail["quiz"]
            ],
            "time_spent_minutes": 10,
        },
        headers=headers,
    )
    assert first.status_code == 200, first.text
    response = client.post(
        "/api/v1/progress/backend-learn-about-apis/complete",
        json={
            "answers": [
                {"question_id": r["question_id"], "option_id": r["correct_option_id"]}
                for r in first.json()["review"]
            ],
            "time_spent_minutes": 10,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["passed"] is True

    detail = client.get(
        "/api/v1/concepts/backend-learn-about-apis", headers=headers
    ).json()
    assert detail["is_locked"] is False
    # The recommendation survives even though it no longer blocks.
    assert detail["prerequisites"]


def test_a_failed_quiz_records_nothing(client, learner):
    headers, _, _ = learner
    detail = client.get("/api/v1/concepts/backend-introduction", headers=headers).json()
    assert detail["quiz"], (
        "backend-introduction has no quiz, so nothing here could fail — "
        "seed app/seed/quizzes/ before trusting a pass"
    )
    # Answer every question with the option that is *not* the right one. The
    # correct option is never last for more than one question, so this always
    # lands below PASS_THRESHOLD.
    correct_ids = {
        r["question_id"]: r["correct_option_id"]
        for r in client.post(
            "/api/v1/progress/backend-introduction/complete",
            json={"answers": [], "time_spent_minutes": 0},
            headers=headers,
        ).json()["review"]
    }
    wrong = [
        {
            "question_id": q["id"],
            "option_id": next(
                o["id"] for o in q["options"] if o["id"] != correct_ids[q["id"]]
            ),
        }
        for q in detail["quiz"]
    ]

    result = client.post(
        "/api/v1/progress/backend-introduction/complete",
        json={"answers": wrong, "time_spent_minutes": 30},
        headers=headers,
    ).json()

    assert result["passed"] is False
    assert result["xp_earned"] == 0
    # Every question comes back with its correct answer and explanation.
    assert len(result["review"]) == len(detail["quiz"])
    assert all(r["explanation"] for r in result["review"])

    after = client.get("/api/v1/concepts/backend-introduction", headers=headers).json()
    assert after["status"] is None
    assert client.get("/api/v1/auth/me", headers=headers).json()["profile"]["xp"] == 0


def test_completing_a_concept_awards_xp_streak_and_a_badge(client, learner):
    headers, _, _ = learner
    result = complete_concept(client, headers, "backend-introduction")

    assert result["xp_earned"] > 0
    assert result["streak_days"] == 1
    assert "first-steps" in {b["slug"] for b in result["new_badges"]}

    profile = client.get("/api/v1/auth/me", headers=headers).json()["profile"]
    assert profile["xp"] == result["total_xp"]
    assert profile["level"] == result["level"]


def test_resubmitting_a_completed_concept_awards_no_further_xp(client, learner):
    headers, _, _ = learner
    first = complete_concept(client, headers, "backend-introduction")

    detail = client.get("/api/v1/concepts/backend-introduction", headers=headers).json()
    again = client.post(
        "/api/v1/progress/backend-introduction/complete",
        json={
            "answers": [
                {"question_id": r["question_id"], "option_id": r["correct_option_id"]}
                for r in first["review"]
            ]
        },
        headers=headers,
    ).json()

    assert again["passed"] is True
    assert again["xp_earned"] == 0
    assert again["total_xp"] == first["total_xp"]
    assert detail["status"] == "completed"


def test_completion_reports_what_it_opens_up(client, learner):
    """Finishing a concept still tells the learner what it leads on to.

    Nothing is gated any more, so this is a signpost rather than a key — but
    the dependents must still be reported, since that is what drives "what
    next" in the UI.
    """
    headers, _, _ = learner

    result = complete_concept(client, headers, "backend-relational-databases")

    assert "backend-caching" in {c["slug"] for c in result["unlocked_concepts"]}


def test_completion_is_mirrored_onto_the_roadmap(client, learner):
    headers, _, _ = learner
    complete_concept(client, headers, "backend-introduction")

    roadmap = client.get("/api/v1/roadmaps/current", headers=headers).json()
    statuses = {
        item["concept"]["slug"]: item["status"]
        for week in roadmap["weeks"]
        for item in week["items"]
    }
    assert statuses["backend-introduction"] == "completed"
    assert roadmap["completed_concepts"] == 1


def test_activity_is_logged_and_zero_filled(client, learner):
    headers, _, _ = learner
    complete_concept(client, headers, "backend-introduction", minutes=45)

    points = client.get("/api/v1/progress/activity?days=7", headers=headers).json()
    assert len(points) == 7
    assert points[-1]["minutes"] == 45
    assert points[-1]["concepts"] == 1
    assert all(p["minutes"] == 0 for p in points[:-1])
