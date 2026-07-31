"""Retrieval over the concept content.

Embeddings are stored as float32 blobs in `concept_embeddings` and ranked with
cosine similarity in NumPy. With a few hundred chunks that is well under a
millisecond — a vector database would be pure overhead here, and this works
identically on SQLite and Postgres.

Keyword search is always available as a fallback so retrieval still works when
Ollama has never been run and no embeddings exist.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.content import Concept, ConceptEmbedding
from app.services.llm import get_provider
from app.services.llm.base import LLMUnavailable

# Chunks are ~1200 characters with overlap: small enough to be precise, large
# enough that a retrieved passage still makes sense on its own.
CHUNK_CHARS = 1200
CHUNK_OVERLAP = 200


@dataclass
class Retrieved:
    concept_id: int
    concept_slug: str
    concept_name: str
    chunk_text: str
    score: float


# --------------------------------------------------------------------------
# indexing
# --------------------------------------------------------------------------


def chunk_text(text: str) -> list[str]:
    """Split on paragraph boundaries, packing up to CHUNK_CHARS per chunk."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 2 > CHUNK_CHARS:
            chunks.append(current)
            # Carry the tail forward so a passage split across a boundary is
            # still retrievable from either side.
            current = current[-CHUNK_OVERLAP:] + "\n\n" + paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph

    if current:
        chunks.append(current)
    return chunks


def concept_chunks(concept: Concept) -> list[str]:
    header = f"{concept.name}\n{concept.summary}"
    body = concept.content_md or ""
    return chunk_text(f"{header}\n\n{body}") if body else [header]


def rebuild_embeddings(db: Session) -> int:
    """Re-embed every concept. Requires Ollama; returns the chunk count."""
    import anyio

    provider = get_provider()
    concepts = db.scalars(select(Concept)).unique().all()
    payloads: list[tuple[int, int, str]] = []
    for concept in concepts:
        for index, chunk in enumerate(concept_chunks(concept)):
            payloads.append((concept.id, index, chunk))

    if not payloads:
        return 0

    async def _embed_all() -> list[list[float]]:
        if not await provider.is_available():
            raise LLMUnavailable(
                "Ollama is not reachable. Start it with `ollama serve`, or skip "
                "--embed and the tutor will fall back to keyword retrieval."
            )
        vectors: list[list[float]] = []
        # Batched so a large corpus does not build one enormous request.
        for start in range(0, len(payloads), 32):
            batch = [text for _, _, text in payloads[start : start + 32]]
            vectors.extend(await provider.embed(batch))
        return vectors

    vectors = anyio.run(_embed_all)

    db.execute(delete(ConceptEmbedding))
    for (concept_id, index, text), vector in zip(payloads, vectors, strict=True):
        array = np.asarray(vector, dtype=np.float32)
        db.add(
            ConceptEmbedding(
                concept_id=concept_id,
                chunk_index=index,
                chunk_text=text,
                vector=array.tobytes(),
                dim=array.size,
                model=settings.ollama_embed_model,
            )
        )
    db.commit()
    return len(payloads)


# --------------------------------------------------------------------------
# retrieval
# --------------------------------------------------------------------------


def _normalise(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    # Avoid dividing by zero for an all-zero vector.
    return matrix / np.where(norms == 0, 1, norms)


async def retrieve(db: Session, query: str, k: int = 4) -> list[Retrieved]:
    """Best-matching chunks: vector search when indexed, keyword search otherwise."""
    rows = db.scalars(select(ConceptEmbedding)).all()
    if rows:
        try:
            vectors = await get_provider().embed([query])
            return _vector_search(db, rows, vectors[0], k)
        except (LLMUnavailable, NotImplementedError):
            # Embeddings exist but Ollama is down; keyword search still works.
            pass
    return _keyword_search(db, query, k)


def _vector_search(
    db: Session, rows: list[ConceptEmbedding], query_vector: list[float], k: int
) -> list[Retrieved]:
    query = np.asarray(query_vector, dtype=np.float32)
    usable = [row for row in rows if row.dim == query.size]
    if not usable:
        return []

    matrix = np.vstack(
        [np.frombuffer(row.vector, dtype=np.float32) for row in usable]
    )
    scores = _normalise(matrix) @ (query / (np.linalg.norm(query) or 1))

    concepts = _concepts_by_id(db, {row.concept_id for row in usable})
    ranked = np.argsort(-scores)[:k]

    results: list[Retrieved] = []
    for index in ranked:
        row = usable[int(index)]
        concept = concepts.get(row.concept_id)
        if concept is None:
            continue
        results.append(
            Retrieved(
                concept_id=concept.id,
                concept_slug=concept.slug,
                concept_name=concept.name,
                chunk_text=row.chunk_text,
                score=float(scores[index]),
            )
        )
    return results


# Words that appear in almost every learning question and carry no signal.
# Without this, "what should I learn about caching?" matches every concept
# containing "learn" and the actual topic gets buried.
_STOPWORDS = frozenset(
    """about after all also and any are but can could did does doing for from
    get give going had has have how into its just know learn learning like make
    many more most much need not now one only should some such take than that
    the their them then there these they this those understand use using very
    want was way what when where which while who why will with would you your"""
    .split()
)


def _keyword_search(db: Session, query: str, k: int) -> list[Retrieved]:
    """Score concepts by rarity-weighted term overlap.

    Crude compared to embeddings, but it keeps the tutor useful on a fresh
    install where nobody has run `--embed`. Terms that appear in many concepts
    are worth less, which is enough to stop common words dominating.
    """
    terms = {
        t
        for t in re.findall(r"[a-z0-9]+", query.lower())
        if len(t) > 2 and t not in _STOPWORDS
    }
    if not terms:
        return []

    concepts = db.scalars(select(Concept)).unique().all()
    haystacks = {
        concept.id: f"{concept.name} {concept.summary} {concept.content_md}".lower()
        for concept in concepts
    }
    # Inverse document frequency: a term in one concept is far more telling
    # than one that appears in twenty.
    document_freq = {
        term: sum(1 for text in haystacks.values() if term in text) for term in terms
    }

    scored: list[tuple[float, Concept]] = []
    for concept in concepts:
        haystack = haystacks[concept.id]
        name = concept.name.lower()
        score = 0.0
        for term in terms:
            if term not in haystack:
                continue
            frequency = document_freq[term] or 1
            weight = 1 / frequency
            # A hit in the title is what the concept is *about*, not a mention.
            score += weight * (3 if term in name else 1)
        if score > 0:
            scored.append((score, concept))

    scored.sort(key=lambda pair: (-pair[0], pair[1].name))
    return [
        Retrieved(
            concept_id=concept.id,
            concept_slug=concept.slug,
            concept_name=concept.name,
            chunk_text=concept_chunks(concept)[0],
            score=score,
        )
        for score, concept in scored[:k]
    ]


def _concepts_by_id(db: Session, ids: set[int]) -> dict[int, Concept]:
    return {
        concept.id: concept
        for concept in db.scalars(select(Concept).where(Concept.id.in_(ids)))
        .unique()
        .all()
    }
