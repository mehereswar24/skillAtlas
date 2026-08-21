"""Knowledge-graph traversal and roadmap scheduling."""

import pytest
from sqlalchemy import select

from app.models.content import Concept, Track
from app.services.graph import ConceptGraph, CycleError, track_concept_ids
from app.services.roadmap import chunk_into_weeks, plan_concepts


def ids_for(db, *slugs: str) -> set[int]:
    return set(db.scalars(select(Concept.id).where(Concept.slug.in_(slugs))).all())


def slugs_for(db, ids) -> list[str]:
    by_id = {c.id: c.slug for c in db.scalars(select(Concept)).unique().all()}
    return [by_id[i] for i in ids]


def test_closure_pulls_in_transitive_prerequisites(db):
    graph = ConceptGraph.load(db)
    closure = slugs_for(db, graph.closure(ids_for(db, "backend-caching")))

    # Directly required
    assert "backend-relational-databases" in closure
    # Required by a requirement — two levels up
    assert "backend-introduction" in closure


def test_closure_stays_inside_its_roadmap(db):
    """Concepts are per-roadmap since the roadmap.sh import.

    The hand-authored graph deliberately shared nodes between tracks, so the AI
    track's closure reached Docker over in the backend track. roadmap.sh
    publishes each roadmap as a self-contained canvas, and the importer
    namespaces every concept by roadmap, so a closure no longer leaves its own
    track. This pins that down: if concept sharing is ever reintroduced, this
    test should be the thing that fails.
    """
    graph = ConceptGraph.load(db)
    closure = slugs_for(db, graph.closure(ids_for(db, "backend-caching")))
    assert all(slug.startswith("backend-") for slug in closure), sorted(closure)


def test_topological_order_puts_prerequisites_first(db):
    graph = ConceptGraph.load(db)
    subset = graph.closure(ids_for(db, "backend-caching", "devops-containers"))
    ordered = graph.topological_order(subset)
    position = {cid: i for i, cid in enumerate(ordered)}

    assert len(ordered) == len(subset)
    for concept_id in subset:
        for prereq in graph.direct_prerequisites(concept_id) & subset:
            assert position[prereq] < position[concept_id]


def test_topological_order_is_deterministic(db):
    graph = ConceptGraph.load(db)
    subset = graph.closure(ids_for(db, "backend-caching"))
    assert graph.topological_order(subset) == graph.topological_order(subset)


def test_cycle_is_detected(db):
    """A cycle must raise rather than silently dropping concepts."""
    graph = ConceptGraph.load(db)
    a, b = 9001, 9002
    graph.prerequisites = {a: {b}, b: {a}}
    graph.dependents = {a: {b}, b: {a}}
    graph.hours = {a: 1, b: 1}

    with pytest.raises(CycleError):
        graph.topological_order({a, b})


def test_prerequisites_are_advisory_not_a_gate(db):
    """Nothing is locked, but the recommended order is still recorded.

    `HARD_PREREQUISITES` is off, so `is_unlocked` is always true. That is
    deliberate rather than incidental: the 85 imported tracks have no real
    dependency data — each concept simply chains to the previous one in reading
    order — and gating on that would lock a learner out of "Caching" until they
    had finished seven unrelated concepts. The edges still have to be there
    either way; they drive the plan's ordering and the "usually covered after"
    hint, and in the authored tracks they are genuine dependencies.
    """
    graph = ConceptGraph.load(db)
    (caching,) = ids_for(db, "backend-caching")
    (databases,) = ids_for(db, "backend-relational-databases")

    assert graph.is_unlocked(caching, completed=set())

    chain = graph.closure({caching}) - {caching}
    assert databases in chain
    assert graph.missing_prerequisites(caching, completed=set()) == {databases}
    assert graph.missing_prerequisites(caching, completed={databases}) == set()


# --- scheduling ----------------------------------------------------------


def test_chunking_respects_the_weekly_budget():
    hours = {1: 10, 2: 10, 3: 10, 4: 10}
    weeks = chunk_into_weeks([1, 2, 3, 4], hours, weekly_hours=21)

    assert [w.concept_ids for w in weeks] == [[1, 2], [3, 4]]
    assert all(w.total_hours <= 21 for w in weeks)


def test_a_concept_larger_than_a_week_gets_its_own_week():
    """Splitting a concept across weeks would produce half a deliverable."""
    hours = {1: 5, 2: 80, 3: 5}
    weeks = chunk_into_weeks([1, 2, 3], hours, weekly_hours=7)

    assert [w.concept_ids for w in weeks] == [[1], [2], [3]]
    assert weeks[1].total_hours == 80


def test_chunking_preserves_order_so_prerequisites_come_first():
    hours = {i: 10 for i in range(1, 7)}
    weeks = chunk_into_weeks([1, 2, 3, 4, 5, 6], hours, weekly_hours=25)
    flattened = [cid for week in weeks for cid in week.concept_ids]
    assert flattened == [1, 2, 3, 4, 5, 6]


def test_chunking_handles_an_empty_plan():
    assert chunk_into_weeks([], {}, weekly_hours=14) == []


def test_plan_skips_known_concepts_and_their_orphaned_prerequisites(db):
    graph = ConceptGraph.load(db)
    track = db.scalar(select(Track).where(Track.slug == "backend"))
    curated = track_concept_ids(db, track.id)

    full = plan_concepts(graph, curated, known=set())
    known = ids_for(db, "backend-introduction", "backend-version-control-systems")
    reduced = plan_concepts(graph, curated, known=known)

    assert len(reduced) == len(full) - len(known)
    assert not known & set(reduced)
