"""Knowledge-graph traversal.

This is the relational replacement for Neo4j. The graph is small (tens to low
hundreds of nodes), so it is loaded into an adjacency map and traversed in
Python — which is both faster than round-tripping recursive CTEs and portable
across SQLite and Postgres.

Build a ``ConceptGraph`` once per request and pass it around; every method on
it is pure.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content import Concept, ConceptPrerequisite, TrackConcept


class CycleError(Exception):
    """Raised when the prerequisite graph contains a cycle.

    The seeder rejects cycles at load time, so reaching this means the database
    was modified by something other than the seeder.
    """


@dataclass
class ConceptGraph:
    """An immutable snapshot of the concept graph."""

    # concept_id -> ids it directly requires
    prerequisites: dict[int, set[int]] = field(default_factory=dict)
    # concept_id -> ids that directly require it
    dependents: dict[int, set[int]] = field(default_factory=dict)
    # concept_id -> estimated hours, used for ordering and scheduling
    hours: dict[int, int] = field(default_factory=dict)

    @classmethod
    def load(cls, db: Session) -> "ConceptGraph":
        graph = cls()
        for concept_id, est_hours in db.execute(
            select(Concept.id, Concept.est_hours)
        ).all():
            graph.prerequisites.setdefault(concept_id, set())
            graph.dependents.setdefault(concept_id, set())
            graph.hours[concept_id] = est_hours

        for concept_id, prereq_id in db.execute(
            select(ConceptPrerequisite.concept_id, ConceptPrerequisite.prerequisite_id)
        ).all():
            # Guard against edges pointing at concepts that no longer exist.
            if concept_id in graph.prerequisites and prereq_id in graph.prerequisites:
                graph.prerequisites[concept_id].add(prereq_id)
                graph.dependents[prereq_id].add(concept_id)

        return graph

    # -- traversal ---------------------------------------------------------

    def direct_prerequisites(self, concept_id: int) -> set[int]:
        return set(self.prerequisites.get(concept_id, set()))

    def direct_dependents(self, concept_id: int) -> set[int]:
        return set(self.dependents.get(concept_id, set()))

    def closure(self, concept_ids: set[int]) -> set[int]:
        """Every concept transitively required by ``concept_ids``, plus itself.

        This is what turns "the AI Engineer track" into a genuine plan: the
        track lists `mlops-deployment`, and the closure pulls in
        `containers-docker` even though that concept is curated under the
        backend track.
        """
        seen: set[int] = set()
        stack = [cid for cid in concept_ids if cid in self.prerequisites]
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(self.prerequisites.get(current, ()))
        return seen

    def topological_order(self, concept_ids: set[int]) -> list[int]:
        """Kahn's algorithm over the induced subgraph.

        Ties are broken by (fewest prerequisites, fewest hours, id) so the
        output is deterministic and starts with the quickest wins — two
        learners with the same goal get the same plan.
        """
        subset = {cid for cid in concept_ids if cid in self.prerequisites}
        indegree = {
            cid: len(self.prerequisites[cid] & subset) for cid in subset
        }

        ready = sorted(
            (cid for cid, deg in indegree.items() if deg == 0),
            key=self._sort_key,
        )
        ordered: list[int] = []

        while ready:
            current = ready.pop(0)
            ordered.append(current)
            for dependent in sorted(self.dependents.get(current, ())):
                if dependent not in subset:
                    continue
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    # Insert in sorted position rather than re-sorting the list.
                    ready.append(dependent)
            ready.sort(key=self._sort_key)

        if len(ordered) != len(subset):
            stuck = sorted(subset - set(ordered))
            raise CycleError(
                f"Prerequisite cycle prevents ordering concept ids {stuck}"
            )
        return ordered

    def _sort_key(self, concept_id: int) -> tuple[int, int, int]:
        return (
            len(self.prerequisites.get(concept_id, ())),
            self.hours.get(concept_id, 0),
            concept_id,
        )

    # -- learner-relative queries ------------------------------------------

    def missing_prerequisites(self, concept_id: int, completed: set[int]) -> set[int]:
        """Direct prerequisites the learner has not finished."""
        return self.direct_prerequisites(concept_id) - completed

    def is_unlocked(self, concept_id: int, completed: set[int]) -> bool:
        return not self.missing_prerequisites(concept_id, completed)

    def unlocked(self, candidates: set[int], completed: set[int]) -> set[int]:
        """Candidates the learner could start right now."""
        return {
            cid
            for cid in candidates
            if cid not in completed and self.is_unlocked(cid, completed)
        }


def track_concept_ids(db: Session, track_id: int) -> list[int]:
    """Concept ids explicitly curated into a track, in authored order."""
    return list(
        db.scalars(
            select(TrackConcept.concept_id)
            .where(TrackConcept.track_id == track_id)
            .order_by(TrackConcept.sort_order)
        ).all()
    )
