"""Scoring the career assessment and mapping a result to a track.

The category → track mapping lives alongside the questions in
`app/seed/assessment.yaml` so content stays in one place. It is read once and
cached rather than duplicated into the database, because it is configuration
rather than user data.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assessment import AssessmentOption
from app.models.content import Track

ASSESSMENT_YAML = Path(__file__).resolve().parent.parent / "seed" / "assessment.yaml"


@dataclass(frozen=True)
class Category:
    name: str
    track_slug: str | None
    fallback_track_slug: str | None
    fallback_note: str | None
    blurb: str


@lru_cache
def load_categories() -> dict[str, Category]:
    with ASSESSMENT_YAML.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return {
        raw["name"]: Category(
            name=raw["name"],
            track_slug=raw.get("track"),
            fallback_track_slug=raw.get("fallback_track"),
            fallback_note=(raw.get("fallback_note") or "").strip() or None,
            blurb=(raw.get("blurb") or "").strip(),
        )
        for raw in data.get("categories", [])
    }


@dataclass
class AssessmentOutcome:
    scores: dict[str, float]
    top_category: str
    blurb: str
    track: Track | None
    note: str | None


def score_answers(db: Session, option_ids: list[int]) -> AssessmentOutcome:
    """Tally the selected options by category and resolve the winner."""
    categories = load_categories()
    scores: dict[str, float] = {name: 0.0 for name in categories}

    options = db.scalars(
        select(AssessmentOption).where(AssessmentOption.id.in_(option_ids))
    ).all()
    for option in options:
        scores[option.category] = scores.get(option.category, 0.0) + option.weight

    # Ties break alphabetically so the same answers always give the same result.
    top = max(scores.items(), key=lambda pair: (pair[1], pair[0]))[0]
    category = categories.get(top)

    if category is None:
        return AssessmentOutcome(scores, top, "", None, None)

    track = _resolve(db, category.track_slug)
    note = None
    if track is None:
        # No curated track for this result yet — say so instead of quietly
        # recommending something unrelated.
        track = _resolve(db, category.fallback_track_slug)
        note = category.fallback_note
    elif category.fallback_note:
        note = category.fallback_note

    return AssessmentOutcome(scores, top, category.blurb, track, note)


def _resolve(db: Session, slug: str | None) -> Track | None:
    if not slug:
        return None
    return db.scalar(select(Track).where(Track.slug == slug))
