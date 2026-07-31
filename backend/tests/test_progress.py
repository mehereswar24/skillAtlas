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


def test_a_locked_concept_cannot_be_completed(client, learner):
    headers, _, _ = learner
    response = client.post(
        "/api/v1/progress/rest-api-design/complete", json={"answers": []}, headers=headers
    )
    assert response.status_code == 409
    assert "prerequisites" in response.json()["detail"].lower()


def test_a_failed_quiz_records_nothing(client, learner):
    headers, _, _ = learner
    detail = client.get("/api/v1/concepts/internet-and-http", headers=headers).json()
    wrong = [
        {"question_id": q["id"], "option_id": q["options"][-1]["id"]}
        for q in detail["quiz"]
    ]

    result = client.post(
        "/api/v1/progress/internet-and-http/complete",
        json={"answers": wrong, "time_spent_minutes": 30},
        headers=headers,
    ).json()

    assert result["passed"] is False
    assert result["xp_earned"] == 0
    # Every question comes back with its correct answer and explanation.
    assert len(result["review"]) == len(detail["quiz"])
    assert all(r["explanation"] for r in result["review"])

    after = client.get("/api/v1/concepts/internet-and-http", headers=headers).json()
    assert after["status"] is None
    assert client.get("/api/v1/auth/me", headers=headers).json()["profile"]["xp"] == 0


def test_completing_a_concept_awards_xp_streak_and_a_badge(client, learner):
    headers, _, _ = learner
    result = complete_concept(client, headers, "internet-and-http")

    assert result["xp_earned"] > 0
    assert result["streak_days"] == 1
    assert "first-steps" in {b["slug"] for b in result["new_badges"]}

    profile = client.get("/api/v1/auth/me", headers=headers).json()["profile"]
    assert profile["xp"] == result["total_xp"]
    assert profile["level"] == result["level"]


def test_resubmitting_a_completed_concept_awards_no_further_xp(client, learner):
    headers, _, _ = learner
    first = complete_concept(client, headers, "internet-and-http")

    detail = client.get("/api/v1/concepts/internet-and-http", headers=headers).json()
    again = client.post(
        "/api/v1/progress/internet-and-http/complete",
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


def test_completion_unlocks_dependent_concepts(client, learner):
    headers, _, _ = learner

    assert client.get("/api/v1/concepts/rest-api-design", headers=headers).json()["is_locked"]

    complete_concept(client, headers, "internet-and-http")
    result = complete_concept(client, headers, "programming-language-python")

    assert "rest-api-design" in {c["slug"] for c in result["unlocked_concepts"]}
    assert not client.get(
        "/api/v1/concepts/rest-api-design", headers=headers
    ).json()["is_locked"]


def test_completion_is_mirrored_onto_the_roadmap(client, learner):
    headers, _, _ = learner
    complete_concept(client, headers, "internet-and-http")

    roadmap = client.get("/api/v1/roadmaps/current", headers=headers).json()
    statuses = {
        item["concept"]["slug"]: item["status"]
        for week in roadmap["weeks"]
        for item in week["items"]
    }
    assert statuses["internet-and-http"] == "completed"
    assert roadmap["completed_concepts"] == 1


def test_activity_is_logged_and_zero_filled(client, learner):
    headers, _, _ = learner
    complete_concept(client, headers, "internet-and-http", minutes=45)

    points = client.get("/api/v1/progress/activity?days=7", headers=headers).json()
    assert len(points) == 7
    assert points[-1]["minutes"] == 45
    assert points[-1]["concepts"] == 1
    assert all(p["minutes"] == 0 for p in points[:-1])
