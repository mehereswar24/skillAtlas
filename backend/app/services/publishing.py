"""Content depth, and what a deployment is allowed to serve.

Two separate questions that are easy to conflate:

**Depth** — is this concept a written lesson or an outline? Determined by the
content itself (the marker `scripts/strip_imported_prose.py` leaves behind), so
it cannot drift out of step with what a learner actually sees. The UI shows it
because promising a lesson and delivering a link list is the kind of thing that
loses trust permanently.

**Publishability** — may this deployment serve it at all? After the strip, the
answer is yes for everything: no track carries third-party prose any more. The
gate stays because it is the mechanism that made shipping safe in the first
place, and because `PUBLISH_AUTHORED_ONLY=true` is still the right setting for
a deployment that wants only the fully-written tracks in front of users.
"""

from __future__ import annotations

from app.config import settings

# Written into stripped concepts by scripts/strip_imported_prose.py.
OUTLINE_MARKER = "<!-- skillatlas:outline -->"

DEPTH_WRITTEN = "written"
DEPTH_OUTLINE = "outline"


def concept_depth(content_md: str | None) -> str:
    """`written` if this is a real lesson, `outline` if it is a syllabus stub."""
    if content_md and OUTLINE_MARKER in content_md:
        return DEPTH_OUTLINE
    return DEPTH_WRITTEN


def track_is_authored(track_slug: str, seed_file: str | None = None) -> bool:
    """Whether a track came from an `authored-*.yaml` file.

    Falls back to the slug when the seed file is not to hand — the authored set
    is small and explicit, and guessing from content would misreport a track
    that is half-written.
    """
    if seed_file:
        return seed_file.startswith("authored-")
    return track_slug in AUTHORED_TRACK_SLUGS


# The tracks written in-house. Kept explicit rather than inferred: this list is
# what a licence question gets answered from, and it should be readable.
AUTHORED_TRACK_SLUGS = frozenset(
    {
        "backend",
        "api-design",
        "frontend",
        "computer-science",
        "devops",
        "system-design",
        "dsa-interview-prep",
    }
)


def visible_track_slugs(all_slugs: set[str]) -> set[str]:
    """Filter tracks down to what this deployment serves."""
    if settings.authored_only:
        return {slug for slug in all_slugs if slug in AUTHORED_TRACK_SLUGS}
    return set(all_slugs)
