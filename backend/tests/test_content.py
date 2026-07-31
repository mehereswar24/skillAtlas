"""Guards on the seeded content itself.

The curated YAML is the product. These tests keep it honest as it grows.
"""

import re

from sqlalchemy import select

from app.models.content import Concept, Domain, QuizQuestion, Role, Track
from app.seed.loader import seed_all
from app.services.rag import _keyword_search, chunk_text


def test_seeding_is_idempotent(db):
    before = seed_all(db, verbose=False)
    counts_before = _counts(db)

    after = seed_all(db, verbose=False)

    assert before == after
    assert _counts(db) == counts_before


def _counts(db):
    return {
        model.__name__: db.scalar(select(model).count_from_self())
        if False
        else len(db.scalars(select(model)).unique().all())
        for model in (Domain, Track, Concept, Role)
    }


def test_every_concept_has_teaching_material(db):
    for concept in db.scalars(select(Concept)).unique().all():
        assert concept.summary.strip(), f"{concept.slug} has no summary"
        assert len(concept.content_md) > 400, f"{concept.slug} has a stub explainer"
        assert concept.est_hours > 0, f"{concept.slug} has no time estimate"


def test_every_concept_has_usable_resources(db):
    for concept in db.scalars(select(Concept)).unique().all():
        assert len(concept.resources) >= 3, f"{concept.slug} has too few resources"
        for resource in concept.resources:
            assert resource.url.startswith("https://"), (
                f"{concept.slug} links to a non-https URL: {resource.url}"
            )
            assert resource.title.strip()


def test_every_quiz_question_has_exactly_one_correct_option(db):
    for question in db.scalars(select(QuizQuestion)).unique().all():
        correct = [o for o in question.options if o.is_correct]
        assert len(correct) == 1, (
            f"question {question.id} has {len(correct)} correct options"
        )
        assert len(question.options) >= 3


def test_every_concept_has_a_quiz_and_interview_questions(db):
    for concept in db.scalars(select(Concept)).unique().all():
        assert concept.quiz_questions, f"{concept.slug} has no quiz"
        assert concept.interview_questions, f"{concept.slug} has no interview questions"


def test_role_weights_reference_real_concepts(db):
    slugs = {c.slug for c in db.scalars(select(Concept)).unique().all()}
    for role in db.scalars(select(Role)).unique().all():
        assert role.skills, f"role {role.slug} has no skills"
        for skill in role.skills:
            assert skill.concept.slug in slugs
            assert skill.weight > 0


def test_a_domain_claims_content_only_if_it_has_a_track(db):
    tracked = {track.domain_id for track in db.scalars(select(Track)).unique().all()}
    for domain in db.scalars(select(Domain)).unique().all():
        assert domain.has_content == (domain.id in tracked), (
            f"{domain.slug} has_content={domain.has_content} but tracked={domain.id in tracked}"
        )


def test_tracks_share_concepts_rather_than_duplicating_them(db):
    """Sharing is what makes this a graph instead of parallel lists."""
    python = db.scalar(
        select(Concept).where(Concept.slug == "programming-language-python")
    )
    sharing = {
        track.slug
        for track in db.scalars(select(Track)).unique().all()
        for tc in track.track_concepts
        if tc.concept_id == python.id
    }
    # Python is curated under the backend track and referenced by several
    # others; at minimum those two must both point at the same node.
    assert {"backend-developer", "ai-engineer"} <= sharing
    assert len(sharing) >= 3


# --- retrieval quality ----------------------------------------------------


def test_chunking_keeps_chunks_bounded_and_lossless():
    text = "\n\n".join(f"Paragraph {i}. " + "word " * 60 for i in range(12))
    chunks = chunk_text(text)

    assert len(chunks) > 1
    assert all(len(c) < 2200 for c in chunks)
    # Nothing is dropped: every paragraph survives somewhere.
    for i in range(12):
        assert any(f"Paragraph {i}." in chunk for chunk in chunks)


def test_keyword_fallback_finds_the_right_concept(db):
    """Retrieval must work before anyone has run the embedding step.

    These questions share vocabulary with their target concept, which is all a
    lexical fallback can be expected to handle — paraphrases without shared
    words are what the embedding path exists for.
    """
    cases = {
        "why does my cache serve stale data": "caching-strategies",
        "how do I prevent SQL injection": "auth-and-security",
        "explain attention in transformers": "nlp-transformers",
        "my model is overfitting": "classical-ml",
        "what is progressive overload": "training-principles",
        "what is bleed in print": "brand-and-production",
        "what is a liveness probe": "kubernetes-orchestration",
        "how do I improve my listening in a new language": "vocabulary-and-listening",
    }
    for question, expected in cases.items():
        results = _keyword_search(db, question, k=3)
        assert results, f"no result for {question!r}"
        assert results[0].concept_slug == expected, (
            f"{question!r} returned {results[0].concept_slug}, expected {expected}"
        )


def test_keyword_ranking_prefers_the_concept_that_covers_the_whole_question(db):
    """A rare incidental word must not outrank broad relevance.

    Small corpora break naive IDF: a term appearing in exactly one concept
    scores maximally, so an off-topic concept containing "prevent" once beat
    the security concept containing both "sql" and "injection".
    """
    results = _keyword_search(db, "how do I prevent SQL injection", k=5)
    top = [r.concept_slug for r in results]
    # The two security concepts must lead; anything matching only the
    # incidental word may appear further down but must not outrank them.
    assert set(top[:2]) == {"auth-and-security", "offensive-security-basics"}
    assert "customer-discovery" not in top[:3]


def test_stopwords_do_not_dominate_retrieval(db):
    """"What should I learn about X" must still rank X first."""
    plain = _keyword_search(db, "caching", k=1)
    padded = _keyword_search(db, "what should I learn about caching", k=1)
    assert plain[0].concept_slug == padded[0].concept_slug == "caching-strategies"


def test_content_markdown_has_no_raw_html(db):
    """Content is rendered as markdown with HTML disabled; keep it that way."""
    for concept in db.scalars(select(Concept)).unique().all():
        assert not re.search(r"<script|<iframe|<img", concept.content_md, re.I)
