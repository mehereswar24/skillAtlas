"""The AI tutor, and the public helper that is the same thing with its hands tied.

Two doors onto one model:

* ``POST /chat`` — the signed-in tutor. Grounded in the retrieved concept
  content, the learner's own plan and progress, and the page they are on. It
  can edit their roadmap.
* ``POST /chat/public`` — the same retrieval and the same page context for a
  visitor who has not signed in, with no account data, no tools, no stored
  history, a shorter leash on length, and a rate limit. It exists so the helper
  on the landing page is not a dead button.

Both stream over SSE and both degrade to retrieval without generation when
Ollama is not running.
"""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.deps import CurrentUser, DbSession, OptionalUser, get_profile
from app.models.content import Concept
from app.models.progress import STATUS_COMPLETED, ChatMessage as ChatMessageRow, UserProgress
from app.schemas.chat import (
    AnonChatRequest,
    ChatHistoryItem,
    ChatRequest,
    OpeningOut,
    OpeningRequest,
    PageContextIn,
    TutorStatus,
)
from app.services.llm import get_provider
from app.services.llm.base import ChatMessage, LLMUnavailable
from app.services.llm.rules import RetrievalOnlyProvider
from app.services.rag import Retrieved, retrieve
from app.services.roadmap import get_active_roadmap, insert_module_at_week
from app.services import tutor
from app.services.tutor import PageLocation, build_messages, resolve_context

log = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Tool definition for the LLM. Only ever offered to a signed-in learner: the
# tools mutate *their* roadmap, so there is nothing for an anonymous caller to
# aim one at.
ROADMAP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_to_roadmap",
            "description": (
                "Add an existing concept/module to the learner's active roadmap "
                "at a specific week. Use this when the learner asks to add a "
                "module, topic, or concept to their roadmap. The concept_slug "
                "should be a kebab-case identifier like 'containers-docker' or "
                "a partial name like 'docker'. The week_no should be chosen "
                "based on where it fits best given the learner's current "
                "progress and the module's prerequisites."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "concept_slug": {
                        "type": "string",
                        "description": (
                            "The slug or partial name of the concept to add. "
                            "Examples: 'containers-docker', 'rest-api-design', "
                            "'python-basics'."
                        ),
                    },
                    "week_no": {
                        "type": "integer",
                        "description": (
                            "The week number to place this module in. Pick a "
                            "week that makes sense given the learner's progress "
                            "and the module's difficulty/prerequisites."
                        ),
                    },
                },
                "required": ["concept_slug", "week_no"],
            },
        },
    }
]

MAX_HISTORY_TURNS = 8


# --------------------------------------------------------------------------
# status and opening offer — both safe for anonymous callers
# --------------------------------------------------------------------------


@router.get("/status", response_model=TutorStatus)
async def tutor_status(user: OptionalUser):
    """Whether generation is available, so the UI can set expectations."""
    provider = get_provider()
    available = await provider.is_available()
    return TutorStatus(
        available=available,
        model=provider.chat_model if available else None,
        mode="generative" if available else "retrieval-only",
        authenticated=user is not None,
    )


@router.post("/opening", response_model=OpeningOut)
def opening(payload: OpeningRequest, user: OptionalUser, db: DbSession):
    """What the helper should say before anyone has typed anything.

    Resolved from the page's structured location against our own tables, so the
    offer names the actual concept, company or role in front of the visitor.
    Cheap and read-only — no model involved.
    """
    location = (payload.context or PageContextIn()).to_location()
    resolved = resolve_context(db, location)
    return OpeningOut(
        greeting=resolved.greeting,
        suggestions=resolved.suggestions,
        authenticated=user is not None,
    )


# --------------------------------------------------------------------------
# history — user-scoped, and reachable only with a token
# --------------------------------------------------------------------------


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


def _available_concepts_hint(db: DbSession) -> str:
    """Build a compact list of available concept slugs for the system prompt."""
    slugs = db.scalars(select(Concept.slug).order_by(Concept.slug)).all()
    if not slugs:
        return "(No concepts loaded yet.)"
    return ", ".join(slugs)


# --------------------------------------------------------------------------
# the anonymous helper
# --------------------------------------------------------------------------


def client_ip(request: Request) -> str:
    """Best available identity for an anonymous caller.

    The browser reaches us through the Next.js BFF, which forwards the real
    address; in normal operation nothing else can reach this API. If something
    can, this header is attacker-controlled — which is exactly why
    `tutor.anonymous_retry_after` also charges a global window that no amount
    of header rotation escapes.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64] or "unknown"
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()[:64] or "unknown"
    return request.client.host if request.client else "unknown"


@router.post("/public")
async def public_chat(payload: AnonChatRequest, request: Request, db: DbSession):
    """Answer a visitor who is not signed in.

    Everything user-scoped is absent by construction rather than by permission
    check: there is no user to look one up for, nothing is written to
    `chat_messages`, no roadmap tools are offered, and the prompt carries no
    LEARNER CONTEXT section at all.
    """
    wait = tutor.anonymous_retry_after(client_ip(request))
    if wait:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "That is as many questions as I can answer for one visitor "
                "right now. Wait a moment, or sign in for the full tutor."
            ),
            headers={"Retry-After": str(int(wait))},
        )

    question = payload.message.strip()
    location = (payload.context or PageContextIn()).to_location()
    resolved = resolve_context(db, location)
    passages = await retrieve(db, _retrieval_query(question, resolved), k=4)

    messages = build_messages(
        question=question,
        passages=passages,
        page_context=resolved.text,
        public=True,
        history=[
            {"role": turn.role, "content": turn.content} for turn in payload.history
        ],
    )

    provider = get_provider()
    degraded = not await provider.is_available()

    return _sse_response(
        _stream_answer(
            provider,
            messages,
            passages,
            degraded=degraded,
            public=True,
            options={"num_predict": tutor.ANON_NUM_PREDICT},
        )
    )


# --------------------------------------------------------------------------
# the signed-in tutor
# --------------------------------------------------------------------------


@router.post("")
async def chat(payload: ChatRequest, user: CurrentUser, db: DbSession):
    """Stream an answer as Server-Sent Events.

    Frames:
      {"type": "sources", "sources": [...], "degraded": bool}
      {"type": "token",  "text": "..."}
      {"type": "action", "action": "roadmap_updated", "detail": {...}}
      {"type": "done"}
      {"type": "error",  "message": "..."}
    """
    question = payload.message.strip()

    # `concept_slug` predates the structured context and some pages still send
    # only that; fold it in rather than making them choose.
    context = payload.context or PageContextIn()
    location: PageLocation = context.to_location()
    if payload.concept_slug and not location.concept_slug:
        location.concept_slug = tutor.clean_slug(payload.concept_slug)
        if location.page == "other" and location.concept_slug:
            location.page = "concept"
    resolved = resolve_context(db, location)
    passages = await retrieve(db, _retrieval_query(question, resolved), k=4)

    messages = build_messages(
        question=question,
        passages=passages,
        page_context=resolved.text,
        public=False,
        learner_context=_learner_context(db, user),
        available_concepts=_available_concepts_hint(db),
        history=_recent_history(db, user.id),
    )

    provider = get_provider()
    degraded = not await provider.is_available()

    db.add(
        ChatMessageRow(user_id=user.id, role="user", content=question, sources=None)
    )
    db.commit()

    roadmap = get_active_roadmap(db, user.id)

    return _sse_response(
        _stream_answer(
            provider,
            messages,
            passages,
            degraded=degraded,
            public=False,
            user_id=user.id,
            db=db,
            roadmap=roadmap,
        )
    )


# --------------------------------------------------------------------------
# the shared stream
# --------------------------------------------------------------------------


def _retrieval_query(question: str, resolved) -> str:
    """Bias retrieval towards whatever the page is about.

    "Explain this" is a query with no content. On a concept page it should
    retrieve that concept, not whichever chunk happens to share a stopword with
    the pronoun, so the page's subject is folded into the query. The visitor
    still sees only their own words; this affects retrieval, not the prompt.
    """
    subject = getattr(resolved, "subject", None)
    return f"{subject}. {question}" if subject else question


def _sse_response(stream: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            # Tells nginx and friends not to buffer the stream.
            "X-Accel-Buffering": "no",
        },
    )


def _open_stream(provider, messages: list[ChatMessage], options: dict | None):
    """Call ``stream_chat`` with options only if the provider takes them.

    Test doubles and the retrieval-only provider predate the parameter; a
    TypeError here is a signature mismatch, not a failure to answer.
    """
    if options:
        try:
            return provider.stream_chat(messages, options)
        except TypeError:
            pass
    return provider.stream_chat(messages)


async def _stream_answer(
    provider,
    messages: list[ChatMessage],
    passages: list[Retrieved],
    *,
    degraded: bool,
    public: bool,
    options: dict | None = None,
    user_id: int | None = None,
    db=None,
    roadmap=None,
) -> AsyncIterator[str]:
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
            text = RetrievalOnlyProvider.answer(messages, public=public)
            collected.append(text)
            yield _sse({"type": "token", "text": text})
        else:
            tool_call_made = False

            # ── Tool-calling loop ──────────────────────────────────────
            # Signed-in only: the tools edit a roadmap, and an anonymous
            # caller has none to edit.
            if roadmap is not None and hasattr(provider, "chat_with_tools"):
                tool_messages = list(messages)
                try:
                    assistant_msg = await provider.chat_with_tools(
                        tool_messages, ROADMAP_TOOLS
                    )
                    tool_calls = assistant_msg.get("tool_calls")

                    if tool_calls:
                        tool_call_made = True
                        tool_messages.append(assistant_msg)

                        for tc in tool_calls:
                            fn = tc.get("function", {})
                            fn_name = fn.get("name", "")
                            fn_args = fn.get("arguments", {})
                            if isinstance(fn_args, str):
                                try:
                                    fn_args = json.loads(fn_args)
                                except json.JSONDecodeError:
                                    fn_args = {}

                            if fn_name == "add_to_roadmap":
                                result = _execute_add_to_roadmap(db, roadmap, fn_args)
                                if result.get("ok"):
                                    yield _sse({
                                        "type": "action",
                                        "action": "roadmap_updated",
                                        "detail": result,
                                    })
                                tool_messages.append({
                                    "role": "tool",
                                    "content": json.dumps(result),
                                })
                            else:
                                tool_messages.append({
                                    "role": "tool",
                                    "content": json.dumps({
                                        "ok": False,
                                        "error": f"Unknown tool: {fn_name}",
                                    }),
                                })

                        async for fragment in _open_stream(
                            provider, tool_messages, options
                        ):
                            collected.append(fragment)
                            yield _sse({"type": "token", "text": fragment})
                except LLMUnavailable:
                    # Tool call failed; fall through to a plain stream.
                    tool_call_made = False

            if not tool_call_made:
                async for fragment in _open_stream(provider, messages, options):
                    collected.append(fragment)
                    yield _sse({"type": "token", "text": fragment})

    except LLMUnavailable as exc:
        # Ollama went away mid-answer: fall back rather than failing.
        text = RetrievalOnlyProvider.answer(messages, public=public)
        collected.append(text)
        yield _sse({"type": "token", "text": text})
        yield _sse({"type": "error", "message": str(exc)})

    answer = "".join(collected).strip()
    # Anonymous turns are never written down. There is no account to attach
    # them to, and inventing one would be the leak this endpoint exists to
    # avoid.
    if answer and user_id is not None:
        _persist_answer(user_id, answer, passages)
    yield _sse({"type": "done"})


def _execute_add_to_roadmap(db: DbSession, roadmap, fn_args: dict) -> dict:
    """Execute the add_to_roadmap tool call."""
    concept_slug = fn_args.get("concept_slug", "")
    week_no = fn_args.get("week_no", 1)

    if not concept_slug:
        return {"ok": False, "error": "No concept_slug provided."}

    try:
        week_no = int(week_no)
    except (ValueError, TypeError):
        week_no = 1

    result = insert_module_at_week(db, roadmap, concept_slug, week_no)
    if result.get("ok"):
        db.commit()
    return result


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
            f"{item.concept.name} (week {item.week_no})"
            for item in roadmap.items
            if item.status != STATUS_COMPLETED
        ][:8]
        if upcoming:
            lines.append("Upcoming on their roadmap: " + ", ".join(upcoming))
        total_weeks = max((item.week_no for item in roadmap.items), default=0)
        lines.append(f"Total weeks in roadmap: {total_weeks}")
    else:
        lines.append("They have not built a roadmap yet.")

    return "\n".join(lines)
