"""Résumé: generated from real progress, or uploaded and analysed.

Two directions through the same concept graph.

*Out*: `POST /resume/generate` assembles a document from `user_progress`,
`project_submissions`, the points ledger and `readiness.py`. `GET|POST
/resume/render` returns that document as a self-contained HTML page with print
CSS, which the browser turns into a PDF — no headless browser, no LaTeX.

*In*: `POST /resume/uploads` takes a PDF, DOCX or plain-text file, and
`/analyse` reports what it says, what it is missing, which roles it supports,
which of the seeded companies hire for those roles and what they ask, and what
a naive parser can actually read out of the file.

Privacy is the load-bearing constraint on everything below the upload line. An
uploaded résumé is personal data belonging to exactly one person: every query
is filtered by `user_id`, a row belonging to someone else answers 404 rather
than 403 so the API never confirms that it exists, and the author can delete
one upload or all of them outright.

Uploads are untrusted. The size is capped before anything is decoded, the type
is decided from the file's magic bytes rather than its name, nothing is ever
written to a path, no subprocess is involved, and the extracted text only ever
reaches the model inside a delimited user turn that the system prompt names as
data.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json

from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import HTMLResponse
from sqlalchemy import delete, func, select

from app.deps import CurrentUser, DbSession
from app.models.resume import (
    ALLOWED_UPLOAD_KINDS,
    MAX_UPLOAD_BYTES,
    ResumeAnalysis,
    ResumeProfile,
    ResumeUpload,
)
from app.schemas.resume import (
    JobMatchIn,
    JobMatchOut,
    ResumeAnalyseIn,
    ResumeAnalysisOut,
    ResumeDocumentOut,
    ResumeGenerateIn,
    ResumeProfileIn,
    ResumeProfileOut,
    ResumeStatusOut,
    ResumeUploadInline,
    ResumeUploadOut,
)
from app.services import resume as service
from app.services.llm import get_provider
from app.services.readiness import completed_concept_ids

router = APIRouter(prefix="/resume", tags=["resume"])


# ==========================================================================
# status
# ==========================================================================


@router.get("/status", response_model=ResumeStatusOut)
async def resume_status():
    """What the page can promise before the learner uploads anything.

    Mirrors `/chat/status`: the honest answer when Ollama is down is
    "retrieval-only", not a spinner that eventually fails.
    """
    provider = get_provider()
    available = await provider.is_available()
    return ResumeStatusOut(
        available=available,
        model=provider.chat_model if available else None,
        mode="generative" if available else "computed-only",
        max_upload_mb=round(MAX_UPLOAD_BYTES / (1024 * 1024), 1),
        accepted_kinds=list(ALLOWED_UPLOAD_KINDS),
    )


# ==========================================================================
# the contact block
# ==========================================================================


def _serialize_profile(profile: ResumeProfile | None) -> ResumeProfileOut:
    if profile is None:
        return ResumeProfileOut(
            full_name=None,
            headline=None,
            email=None,
            phone=None,
            location=None,
            links=[],
            summary=None,
            updated_at=None,
        )
    return ResumeProfileOut(
        full_name=profile.full_name,
        headline=profile.headline,
        email=profile.email,
        phone=profile.phone,
        location=profile.location,
        links=[line for line in (profile.links or "").splitlines() if line.strip()],
        summary=profile.summary,
        updated_at=profile.updated_at,
    )


@router.get("/profile", response_model=ResumeProfileOut)
def get_resume_profile(user: CurrentUser, db: DbSession):
    return _serialize_profile(
        db.scalar(select(ResumeProfile).where(ResumeProfile.user_id == user.id))
    )


@router.put("/profile", response_model=ResumeProfileOut)
def update_resume_profile(payload: ResumeProfileIn, user: CurrentUser, db: DbSession):
    profile = db.scalar(select(ResumeProfile).where(ResumeProfile.user_id == user.id))
    if profile is None:
        profile = ResumeProfile(user_id=user.id)
        db.add(profile)

    profile.full_name = payload.full_name
    profile.headline = payload.headline
    profile.email = payload.email
    profile.phone = payload.phone
    profile.location = payload.location
    profile.links = "\n".join(payload.links) or None
    profile.summary = payload.summary

    db.commit()
    db.refresh(profile)
    return _serialize_profile(profile)


# ==========================================================================
# generation
# ==========================================================================


@router.post("/generate", response_model=ResumeDocumentOut)
async def generate_resume(payload: ResumeGenerateIn, user: CurrentUser, db: DbSession):
    """Build the résumé document from what the learner has actually done."""
    return await service.build_resume(
        db,
        user,
        target_role_slug=payload.target_role_slug,
        job_description=payload.job_description,
        polish=payload.polish,
    )


@router.post("/job-match", response_model=JobMatchOut)
def job_match(payload: JobMatchIn, user: CurrentUser, db: DbSession):
    """Diff a pasted job description against completed concepts.

    `addable_slugs` on the response is exactly the body
    `POST /roadmaps/current/items` wants, so every gap is one call from being
    scheduled on the learner's route.
    """
    evidence = service.gather_evidence(db, user)
    return service.match_job_description(
        db,
        payload.job_description,
        completed_concept_ids(db, user.id),
        roadmap_concept_ids=evidence.roadmap_concept_ids,
    )


@router.get("/render", response_class=HTMLResponse)
async def render_resume_get(
    user: CurrentUser,
    db: DbSession,
    role: str | None = Query(default=None, max_length=80),
    polish: bool = Query(default=True),
):
    """The printable résumé, as a page.

    A GET so it can be opened in a tab and printed straight from there. The
    job-description variant needs a body, so it lives on the POST below.
    """
    document = await service.build_resume(
        db, user, target_role_slug=role, polish=polish
    )
    return HTMLResponse(service.render_html(document))


@router.post("/render", response_class=HTMLResponse)
async def render_resume_post(payload: ResumeGenerateIn, user: CurrentUser, db: DbSession):
    """Same page, tailored to a pasted job description."""
    document = await service.build_resume(
        db,
        user,
        target_role_slug=payload.target_role_slug,
        job_description=payload.job_description,
        polish=payload.polish,
    )
    return HTMLResponse(service.render_html(document))


# ==========================================================================
# uploads
# ==========================================================================


def _serialize_upload(db: DbSession, upload: ResumeUpload) -> ResumeUploadOut:
    has_analysis = (
        db.scalar(
            select(func.count(ResumeAnalysis.id)).where(
                ResumeAnalysis.upload_id == upload.id
            )
        )
        or 0
    ) > 0
    return ResumeUploadOut(
        id=upload.id,
        filename=upload.filename,
        kind=upload.kind,
        size_bytes=upload.size_bytes,
        extraction_ok=upload.extraction_ok,
        extraction_note=upload.extraction_note,
        page_count=upload.page_count,
        text_chars=len(upload.extracted_text or ""),
        created_at=upload.created_at,
        has_analysis=has_analysis,
    )


def _own_upload(db: DbSession, user_id: int, upload_id: int) -> ResumeUpload:
    """The caller's own upload, or 404.

    404 rather than 403 on someone else's row: a résumé is personal data, and
    "that exists but is not yours" is itself a disclosure.
    """
    upload = db.scalar(
        select(ResumeUpload).where(
            ResumeUpload.id == upload_id, ResumeUpload.user_id == user_id
        )
    )
    if upload is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such résumé")
    return upload


# The filename is display-only, but it is still rendered in a browser and
# stored, so anything that is not a filename is thrown away rather than
# escaped later.
def _safe_filename(raw: str | None) -> str:
    name = (raw or "resume").replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if ch.isprintable() and ch not in '<>:"|?*')
    name = name.strip() or "resume"
    return name[:255]


def _store_upload(
    db: DbSession, user_id: int, data: bytes, filename: str, content_type: str
) -> ResumeUpload:
    try:
        extraction = service.extract_text(data, filename, content_type)
    except service.UploadRejected as exc:
        raise HTTPException(exc.status, str(exc)) from exc

    upload = ResumeUpload(
        user_id=user_id,
        filename=_safe_filename(filename),
        kind=extraction.kind,
        content_type=content_type[:120],
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        data=data,
        extracted_text=extraction.text,
        extraction_ok=extraction.ok,
        extraction_note=extraction.note,
        page_count=extraction.page_count,
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)
    return upload


@router.post(
    "/uploads", response_model=ResumeUploadOut, status_code=status.HTTP_201_CREATED
)
async def upload_resume(user: CurrentUser, db: DbSession, file: UploadFile = File(...)):
    """Upload a PDF, DOCX or plain-text résumé.

    The body is read in chunks and abandoned the moment it passes the cap, so
    an oversized file is refused without ever being held in full.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status.HTTP_413_CONTENT_TOO_LARGE,
                f"Résumés are capped at {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
            )
        chunks.append(chunk)

    return _serialize_upload(
        db,
        _store_upload(
            db,
            user.id,
            b"".join(chunks),
            file.filename or "resume",
            file.content_type or "",
        ),
    )


@router.post(
    "/uploads/inline",
    response_model=ResumeUploadOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_resume_inline(payload: ResumeUploadInline, user: CurrentUser, db: DbSession):
    """Base64 variant, for callers that cannot send multipart.

    The browser is one of them: the Next.js BFF proxy reads bodies as text and
    would corrupt binary on the way through. Validation is identical — both
    paths meet in `_store_upload`.
    """
    # Base64 inflates by 4/3; refuse the string before decoding it rather than
    # materialising an oversized buffer to then reject.
    if len(payload.content_base64) > (MAX_UPLOAD_BYTES * 4) // 3 + 1024:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"Résumés are capped at {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )
    encoded = payload.content_base64
    # Tolerate a data: URL, which is what FileReader.readAsDataURL produces.
    if encoded.startswith("data:"):
        _, _, encoded = encoded.partition(",")
    try:
        data = base64.b64decode(encoded, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "The file could not be decoded."
        ) from exc

    return _serialize_upload(
        db, _store_upload(db, user.id, data, payload.filename, payload.content_type)
    )


@router.get("/uploads", response_model=list[ResumeUploadOut])
def list_uploads(user: CurrentUser, db: DbSession):
    uploads = db.scalars(
        select(ResumeUpload)
        .where(ResumeUpload.user_id == user.id)
        .order_by(ResumeUpload.created_at.desc(), ResumeUpload.id.desc())
    ).all()
    return [_serialize_upload(db, upload) for upload in uploads]


@router.get("/uploads/{upload_id}", response_model=ResumeUploadOut)
def get_upload(upload_id: int, user: CurrentUser, db: DbSession):
    return _serialize_upload(db, _own_upload(db, user.id, upload_id))


@router.get("/uploads/{upload_id}/text", response_class=Response)
def get_upload_text(upload_id: int, user: CurrentUser, db: DbSession):
    """Exactly what a parser sees. Served as text, never as HTML."""
    upload = _own_upload(db, user.id, upload_id)
    return Response(
        content=upload.extracted_text or "",
        media_type="text/plain; charset=utf-8",
        # It is user-supplied content coming back out; nothing may treat it as
        # markup or execute it.
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
        },
    )


@router.delete("/uploads/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_upload(upload_id: int, user: CurrentUser, db: DbSession):
    """Delete one résumé and every analysis of it."""
    upload = _own_upload(db, user.id, upload_id)
    db.delete(upload)
    db.commit()


@router.delete("/uploads", status_code=status.HTTP_204_NO_CONTENT)
def delete_all_uploads(user: CurrentUser, db: DbSession):
    """Erase every résumé this account has uploaded, and their analyses."""
    db.execute(delete(ResumeAnalysis).where(ResumeAnalysis.user_id == user.id))
    db.execute(delete(ResumeUpload).where(ResumeUpload.user_id == user.id))
    db.commit()


# ==========================================================================
# analysis
# ==========================================================================


def _serialize_analysis(row: ResumeAnalysis) -> ResumeAnalysisOut:
    payload = json.loads(row.payload_json or "{}")
    return ResumeAnalysisOut(
        id=row.id,
        upload_id=row.upload_id,
        created_at=row.created_at,
        degraded=row.degraded,
        generated_by=row.generated_by,
        degraded_reason=payload.get("degraded_reason"),
        extraction=payload.get("extraction", {}),
        ats=payload.get("ats", {}),
        suggestions=payload.get("suggestions", []),
        rewrites=payload.get("rewrites", []),
        detected_skills=payload.get("detected_skills", []),
        career_options=payload.get("career_options", []),
        companies=payload.get("companies", []),
        learn_next=payload.get("learn_next", []),
        addable_slugs=payload.get("addable_slugs", []),
        job_match=payload.get("job_match"),
        target_role=payload.get("target_role"),
        generated_at=payload.get("generated_at", ""),
    )


@router.post("/uploads/{upload_id}/analyse", response_model=ResumeAnalysisOut)
async def analyse_upload(
    upload_id: int,
    payload: ResumeAnalyseIn,
    user: CurrentUser,
    db: DbSession,
):
    """Analyse an uploaded résumé and cache the report.

    Everything except the bullet rewrites is computed. When Ollama is not
    running the response still arrives, with `degraded: true` and a reason —
    the suggestions, role scores, company matches and ATS check are unaffected
    because none of them ever needed a model.
    """
    upload = _own_upload(db, user.id, upload_id)

    if not payload.refresh and not payload.job_description:
        cached = db.scalar(
            select(ResumeAnalysis)
            .where(
                ResumeAnalysis.upload_id == upload.id,
                ResumeAnalysis.user_id == user.id,
                ResumeAnalysis.target_role_slug == payload.target_role_slug,
            )
            .order_by(ResumeAnalysis.created_at.desc(), ResumeAnalysis.id.desc())
        )
        if cached is not None:
            return _serialize_analysis(cached)

    report = await service.analyse_upload(
        db,
        user,
        upload,
        target_role_slug=payload.target_role_slug,
        job_description=payload.job_description,
    )

    row = ResumeAnalysis(
        upload_id=upload.id,
        user_id=user.id,
        target_role_slug=payload.target_role_slug,
        payload_json=json.dumps(report),
        generated_by=report.get("generated_by"),
        degraded=bool(report.get("degraded")),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_analysis(row)


@router.get("/uploads/{upload_id}/analysis", response_model=ResumeAnalysisOut)
def get_analysis(upload_id: int, user: CurrentUser, db: DbSession):
    """The most recent cached analysis for one of my uploads."""
    upload = _own_upload(db, user.id, upload_id)
    row = db.scalar(
        select(ResumeAnalysis)
        .where(
            ResumeAnalysis.upload_id == upload.id,
            ResumeAnalysis.user_id == user.id,
        )
        .order_by(ResumeAnalysis.created_at.desc(), ResumeAnalysis.id.desc())
    )
    if row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "This résumé has not been analysed yet"
        )
    return _serialize_analysis(row)
