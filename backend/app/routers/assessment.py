"""Career assessment.

Questions come from the database, results are scored server-side, and a signed-
in learner's result is persisted so it can drive their recommendation. Anonymous
visitors get the same result with `saved: false` — the client holds it and
replays it after signup.
"""

import json

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.deps import DbSession, OptionalUser
from app.models.assessment import AssessmentQuestion, AssessmentResult
from app.models.content import Concept, TrackConcept
from app.routers.content import track_summary
from app.schemas.community import (
    AssessmentOptionOut,
    AssessmentQuestionOut,
    AssessmentResultOut,
    AssessmentSubmit,
)
from app.services.assessment import score_answers

router = APIRouter(prefix="/assessment", tags=["assessment"])


@router.get("/questions", response_model=list[AssessmentQuestionOut])
def questions(db: DbSession):
    rows = db.scalars(
        select(AssessmentQuestion).order_by(AssessmentQuestion.sort_order)
    ).unique().all()
    return [
        AssessmentQuestionOut(
            id=q.id,
            prompt=q.prompt,
            options=[AssessmentOptionOut(id=o.id, text=o.text) for o in q.options],
        )
        for q in rows
    ]


@router.post("/submit", response_model=AssessmentResultOut)
def submit(payload: AssessmentSubmit, db: DbSession, user: OptionalUser):
    outcome = score_answers(db, payload.option_ids)
    if not outcome.scores:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Those answers did not match any question"
        )

    saved = False
    if user is not None:
        db.add(
            AssessmentResult(
                user_id=user.id,
                scores_json=json.dumps(outcome.scores),
                top_category=outcome.top_category,
                recommended_track_id=outcome.track.id if outcome.track else None,
            )
        )
        db.commit()
        saved = True

    track_out = None
    if outcome.track:
        count, hours = db.execute(
            select(
                func.count(TrackConcept.concept_id),
                func.coalesce(func.sum(Concept.est_hours), 0),
            )
            .join(Concept, Concept.id == TrackConcept.concept_id)
            .where(TrackConcept.track_id == outcome.track.id)
        ).one()
        track_out = track_summary(outcome.track, count, hours)

    return AssessmentResultOut(
        top_category=outcome.top_category,
        blurb=outcome.blurb,
        scores=outcome.scores,
        recommended_track=track_out,
        note=outcome.note,
        saved=saved,
    )
