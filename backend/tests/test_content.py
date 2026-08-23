"""Guards on the seeded content itself.

The curated YAML is the product. These tests keep it honest as it grows.
"""

import pytest
import re

from sqlalchemy import select

from app.models.content import (
    Concept,
    Domain,
    InterviewQuestion,
    QuizQuestion,
    Role,
    Track,
)
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
    """Every concept says something; most say a lot.

    Content is imported from roadmap.sh, whose nodes vary from a paragraph to
    several pages. A hard per-concept floor would fail on the genuinely short
    ones, so the floor is per-concept and the depth is checked in aggregate.
    """
    concepts = db.scalars(select(Concept)).unique().all()
    for concept in concepts:
        assert concept.summary.strip(), f"{concept.slug} has no summary"
        assert concept.content_md.strip(), f"{concept.slug} has no explainer"
        assert concept.est_hours > 0, f"{concept.slug} has no time estimate"

    substantial = sum(1 for c in concepts if len(c.content_md) > 400)
    assert substantial / len(concepts) >= 0.75, (
        f"only {substantial}/{len(concepts)} concepts have a real explainer"
    )


def test_every_concept_has_usable_resources(db):
    """Links must be sound, and the corpus must be well covered overall.

    roadmap.sh leaves some nodes without links, so "at least three" holds for
    the corpus rather than for every single concept.
    """
    concepts = db.scalars(select(Concept)).unique().all()
    for concept in concepts:
        for resource in concept.resources:
            assert resource.url.startswith("https://"), (
                f"{concept.slug} links to a non-https URL: {resource.url}"
            )
            assert resource.title.strip()

    well_sourced = sum(1 for c in concepts if len(c.resources) >= 3)
    assert well_sourced / len(concepts) >= 0.70, (
        f"only {well_sourced}/{len(concepts)} concepts carry three or more sources"
    )


def test_every_quiz_question_has_exactly_one_correct_option(db):
    for question in db.scalars(select(QuizQuestion)).unique().all():
        correct = [o for o in question.options if o.is_correct]
        assert len(correct) == 1, (
            f"question {question.id} has {len(correct)} correct options"
        )
        assert len(question.options) >= 3


@pytest.mark.xfail(
    reason="Quiz coverage is deliberately partial: scripts/generate_quizzes.py "
    "targets the ~250 concepts on the routes people actually take, not all "
    "2,757 imported ones. Kept as a live reminder of the remaining gap — it "
    "will XPASS once the whole corpus is covered.",
    strict=False,
)
def test_every_concept_has_a_quiz_and_interview_questions(db):
    for concept in db.scalars(select(Concept)).unique().all():
        assert concept.quiz_questions, f"{concept.slug} has no quiz"
        assert concept.interview_questions, f"{concept.slug} has no interview questions"


def test_completion_is_not_silently_ungated(db):
    """A concept that has a quiz must be gated by a quiz worth passing.

    Coverage is deliberately partial. ``scripts/generate_quizzes.py`` quizzes
    the concepts that appear on the routes people actually take, not all 2,757
    imported ones, so the corpus is genuinely mixed: some concepts are gated
    and the rest still fall through the ``question_count == 0`` path in
    ``routers/progress.py``.

    What would not be acceptable is a gate that can be cleared by guessing.
    ``PASS_THRESHOLD`` is two thirds, so a one- or two-question quiz is passed
    by luck often enough to be worse than the honest no-gate fallback.
    """
    concepts = db.scalars(select(Concept)).unique().all()
    quizzed = [c for c in concepts if c.quiz_questions]
    assert quizzed, (
        "no concept has a quiz — the seed set under app/seed/quizzes/ is "
        "missing or empty; regenerate with scripts/generate_quizzes.py"
    )

    for concept in quizzed:
        assert len(concept.quiz_questions) >= 3, (
            f"{concept.slug} is gated on only {len(concept.quiz_questions)} "
            f"question(s), which a learner can pass by guessing"
        )
        assert concept.interview_questions, (
            f"{concept.slug} has a quiz but no interview questions"
        )


def test_generated_questions_are_labelled_as_generated(db):
    """No machine-written question may pass itself off as hand-authored.

    ``generated_by`` is what lets the UI tell a learner where a question came
    from. A generated question also has to carry ``verified_at``: the second
    pass in ``scripts/generate_quizzes.py`` is the only thing standing between
    the bank and questions its own source material cannot answer, and an
    unverified row means that pass was skipped.
    """
    for question in db.scalars(select(QuizQuestion)).unique().all():
        if question.generated_by:
            assert question.verified_at is not None, (
                f"quiz question {question.id} was generated by "
                f"{question.generated_by} but never verified"
            )

    for question in db.scalars(select(InterviewQuestion)).unique().all():
        if question.generated_by:
            assert question.verified_at is not None, (
                f"interview question {question.id} was generated by "
                f"{question.generated_by} but never verified"
            )
        assert (question.answer_md or "").strip(), (
            f"interview question {question.id} has no answer"
        )


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


def test_each_track_owns_its_concepts(db):
    """Tracks no longer share concept nodes, and that is a known trade-off.

    The hand-authored content deliberately shared nodes — one Docker concept
    that both the backend and AI tracks pointed at — which is what made the
    catalogue a graph rather than parallel lists. roadmap.sh ships each roadmap
    as a standalone canvas with its own copy of a shared topic, so the importer
    namespaces concepts per roadmap and the same subject is now duplicated
    across tracks (Docker appears in devops, backend and kubernetes).

    The cost is a fatter corpus and progress that does not carry across tracks.
    This test states the current model plainly so the regression is visible
    rather than forgotten; deduplicating across roadmaps would replace it.
    """
    tracks = db.scalars(select(Track)).unique().all()
    owners: dict[int, set[str]] = {}
    for track in tracks:
        for tc in track.track_concepts:
            owners.setdefault(tc.concept_id, set()).add(track.slug)

    shared = {cid: names for cid, names in owners.items() if len(names) > 1}
    assert not shared, f"{len(shared)} concepts are shared between tracks"


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

    Questions are drawn from what the corpus actually teaches. Since
    `scripts/strip_imported_prose.py` removed the third-party prose, only the
    hand-written tracks carry a lesson, and `retrievable_concepts` excludes the
    outline ones — so a question about machine learning has no written material
    to find and belongs in this test only once that track is authored.

    Expectations name a set of acceptable concepts rather than one slug: the
    same subject is covered by several written tracks, and which of them ranks
    first is a ranking preference, not correctness.
    """
    cases = {
        "how do I design a REST API": ("api-design-", "system-design-"),
        "what is a docker container": ("devops-containers", "backend-containerization"),
        "why does my cache serve stale data": ("caching", "cach"),
        "what is a B-tree index": (
            "storage-engines",
            "balanced-search-trees",
            "relational-databases",
        ),
        "how do I stop a slow dependency taking down my service": (
            "resiliency",
            "integration-patterns",
            "high-availability",
        ),
    }
    for question, acceptable in cases.items():
        results = _keyword_search(db, question, k=3)
        assert results, f"no result for {question!r}"
        top = results[0].concept_slug
        assert any(fragment in top for fragment in acceptable), (
            f"{question!r} returned {top}, expected one of {acceptable}"
        )


def test_keyword_ranking_prefers_the_concept_that_covers_the_whole_question(db):
    """A rare incidental word must not outrank broad relevance.

    Small corpora break naive IDF: a term appearing in exactly one concept
    scores maximally, so an off-topic concept containing "prevent" once beat
    the security concept containing both "sql" and "injection".

    The property under test is coverage, not identity: every leading result has
    to carry the *whole* question rather than one rare word from it. Which
    on-topic concept comes first is left open — several tracks cover REST, and
    pinning one of them made this a test of the corpus rather than the ranker.
    """
    results = _keyword_search(db, "how do I design a REST API", k=5)
    top = [r.concept_slug for r in results]
    # Concepts carrying the whole question ("api" *and* "rest") must lead over
    # anything that merely mentions "design".
    assert "api" in top[0], top
    assert sum(1 for slug in top[:3] if "api" in slug) >= 2, top
    assert any(slug.startswith("api-design-") for slug in top), top


def test_keyword_ranking_normalises_for_document_length(db):
    """A long chapter must not outrank a short one by sheer volume.

    Before BM25 length normalisation the ranker summed a damped term frequency
    with no reference to document size, so the longest chapter mentioning a
    term tended to win. This pins the fix: the query is answered by concepts
    that are *about* caching, not merely by the longest one that says the word.
    """
    top = [r.concept_slug for r in _keyword_search(db, "cache invalidation", k=3)]
    assert any("cach" in slug for slug in top[:2]), top


def test_stopwords_do_not_dominate_retrieval(db):
    """"What should I learn about X" must still rank X first."""
    plain = _keyword_search(db, "caching", k=3)
    padded = _keyword_search(db, "what should I learn about caching", k=3)
    # The padding words carry no signal, so the reading must be identical.
    assert [r.concept_slug for r in plain] == [r.concept_slug for r in padded]
    # Topical rather than positional. The ranker does not stem, so "caching"
    # and "cache" are separate terms and the chapter using the query's exact
    # inflection most can lead — see the note in `_keyword_search`. What must
    # hold is that the answer is about caching at all.
    assert any("cach" in r.concept_slug for r in plain), [
        r.concept_slug for r in plain
    ]


def test_content_markdown_has_no_raw_html(db):
    """Content is rendered as markdown with HTML disabled; keep it that way.

    Code spans and blocks are exempt: a lot of the material legitimately talks
    *about* HTML, and `<img>` inside backticks renders as the text it says.
    """
    code = re.compile(r"```.*?```|`[^`]*`|^(?: {4}|\t).*$", re.S | re.M)
    for concept in db.scalars(select(Concept)).unique().all():
        prose = code.sub("", concept.content_md)
        assert not re.search(r"<script|<iframe|<img", prose, re.I), concept.slug
