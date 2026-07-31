"""The AI tutor.

Grounded in two things: the concept content retrieved for the question, and the
learner's own plan and progress. Streams over SSE, and degrades to retrieval
without generation when Ollama is not running.

This replaces the prototype's `if "roadmap" in message` canned-string router.
"""

from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.deps import CurrentUser, DbSession, get_profile
from app.models.content import Concept
from app.models.progress import STATUS_COMPLETED, ChatMessage as ChatMessageRow, UserProgress
from app.schemas.chat import ChatHistoryItem, ChatRequest, TutorStatus
from app.services.llm import get_provider
from app.services.llm.base import ChatMessage, LLMUnavailable
from app.services.llm.rules import RetrievalOnlyProvider
from app.services.rag import Retrieved, retrieve
from app.services.roadmap import get_active_roadmap

router = APIRouter(prefix="/chat", tags=["chat"])

SYSTEM_PREAMBLE = """You are the SkillAtlas tutor. You help one learner work \
through a specific roadmap.

Rules:
- Answer using the COURSE NOTES below. They are the authoritative material.
- If the notes do not cover the question, say so plainly and suggest which \
concept on their roadmap is closest. Never invent facts, URLs or statistics.
- Use the LEARNER CONTEXT to be specific: refer to what they have finished and \
what is next rather than giving generic advice.
- Be concise and direct. Short paragraphs, no filler, no flattery. Use markdown \
for structure when it helps.
"""

MAX_HISTORY_TURNS = 8


@router.get("/status", response_model=TutorStatus)
async def tutor_status():
    """Whether generation is available, so the UI can set expectations."""
    provider = get_provider()
    available = await provider.is_available()
    return TutorStatus(
        available=available,
        model=provider.chat_model if available else None,
        mode="generative" if available else "retrieval-only",
    )


@router.get("/history", response_model=list[ChatHistoryItem])
def history(user: CurrentUser, db: DbSession, limit: int = Query(50, ge=1, le=200)):
    rows = db.scalars(
        select(ChatMessageRow)
        .where(ChatMessageRow.user_id == user.id)
        # Ordered by id, not created_at: the timestamp has second granularity,
        # so a question and its answer can tie and interleave wrongly.
        .order_by(ChatMessageRow.id.desc())
        .limit(limit)
    ).all()
    return [
        ChatHistoryItem(
            id=row.id,
            role=row.role,
            content=row.content,
            sources=row.sources.split(",") if row.sources else [],
            created_at=row.created_at,
        )
        for row in reversed(rows)
    ]


@router.delete("/history", status_code=204)
def clear_history(user: CurrentUser, db: DbSession):
    for row in db.scalars(
        select(ChatMessageRow).where(ChatMessageRow.user_id == user.id)
    ).all():
        db.delete(row)
    db.commit()


@router.post("")
async def chat(payload: ChatRequest, user: CurrentUser, db: DbSession):
    """Stream an answer as Server-Sent Events.

    Frames:
      {"type": "sources", "sources": [...], "degraded": bool}
      {"type": "token",  "text": "..."}
      {"type": "done"}
      {"type": "error",  "message": "..."}
    """
    question = payload.message.strip()
    passages = await retrieve(db, question, k=4)
    learner_context = _learner_context(db, user)

    system = "\n\n".join(
        [
            SYSTEM_PREAMBLE,
            "LEARNER CONTEXT\n" + learner_context,
            "COURSE NOTES\n" + _format_passages(passages),
        ]
    )

    messages: list[ChatMessage] = [{"role": "system", "content": system}]
    messages.extend(_recent_history(db, user.id))
    messages.append({"role": "user", "content": question})

    provider = get_provider()
    degraded = not await provider.is_available()

    db.add(
        ChatMessageRow(user_id=user.id, role="user", content=question, sources=None)
    )
    db.commit()

    async def event_stream() -> AsyncIterator[str]:
        # Several chunks often come from the same concept; cite each once, in
        # relevance order.
        seen: set[str] = set()
        sources = [
            {"slug": p.concept_slug, "name": p.concept_name}
            for p in passages
            if not (p.concept_slug in seen or seen.add(p.concept_slug))
        ]
        yield _sse({"type": "sources", "sources": sources, "degraded": degraded})

        collected: list[str] = []
        try:
            if degraded:
                text = RetrievalOnlyProvider.answer(messages)
                collected.append(text)
                yield _sse({"type": "token", "text": text})
            else:
                async for fragment in provider.stream_chat(messages):
                    collected.append(fragment)
                    yield _sse({"type": "token", "text": fragment})
        except LLMUnavailable as exc:
            # Ollama went away mid-answer: fall back rather than failing.
            text = RetrievalOnlyProvider.answer(messages)
            collected.append(text)
            yield _sse({"type": "token", "text": text})
            yield _sse({"type": "error", "message": str(exc)})

        answer = "".join(collected).strip()
        if answer:
            _persist_answer(user.id, answer, passages)
        yield _sse({"type": "done"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            # Tells nginx and friends not to buffer the stream.
            "X-Accel-Buffering": "no",
        },
    )


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _persist_answer(user_id: int, answer: str, passages: list[Retrieved]) -> None:
    """Write the assistant turn on its own session.

    The request-scoped session is closed by the time the stream finishes, so
    this opens a short-lived one of its own.
    """
    from app.database import SessionLocal

    with SessionLocal() as session:
        session.add(
            ChatMessageRow(
                user_id=user_id,
                role="assistant",
                content=answer,
                sources=",".join(p.concept_slug for p in passages) or None,
            )
        )
        session.commit()


def _recent_history(db: DbSession, user_id: int) -> list[ChatMessage]:
    rows = db.scalars(
        select(ChatMessageRow)
        .where(ChatMessageRow.user_id == user_id)
        # Ordered by id, not created_at: the timestamp has second granularity,
        # so a question and its answer can tie and interleave wrongly.
        .order_by(ChatMessageRow.id.desc())
        .limit(MAX_HISTORY_TURNS * 2)
    ).all()
    return [
        {"role": row.role, "content": row.content}  # type: ignore[typeddict-item]
        for row in reversed(rows)
    ]


def _format_passages(passages: list[Retrieved]) -> str:
    if not passages:
        return "(No relevant notes were found for this question.)"
    return "\n\n".join(
        f"### {p.concept_name}\n{p.chunk_text}" for p in passages
    )


def _learner_context(db: DbSession, user) -> str:
    profile = get_profile(db, user)
    lines = [f"Name: {user.display_name or 'the learner'}"]

    if profile.current_track:
        lines.append(f"Goal: {profile.current_track.title}")
    lines.append(f"Daily commitment: {profile.daily_hours} hours")
    lines.append(f"Level {profile.level}, {profile.xp} XP")

    completed = db.scalars(
        select(Concept.name)
        .join(UserProgress, UserProgress.concept_id == Concept.id)
        .where(
            UserProgress.user_id == user.id,
            UserProgress.status == STATUS_COMPLETED,
        )
    ).all()
    lines.append(
        "Completed so far: " + (", ".join(completed) if completed else "nothing yet")
    )

    roadmap = get_active_roadmap(db, user.id)
    if roadmap:
        upcoming = [
            item.concept.name
            for item in roadmap.items
            if item.status != STATUS_COMPLETED
        ][:5]
        if upcoming:
            lines.append("Next on their roadmap: " + ", ".join(upcoming))
    else:
        lines.append("They have not built a roadmap yet.")

    return "\n".join(lines)
