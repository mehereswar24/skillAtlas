"""Make every imported track shippable by removing the part we do not own.

roadmap.sh's licence permits personal use and forbids redistribution. The
importer pulled ~645,000 words of their prose into `content_md`, and that prose
is the only thing in a track file that is theirs. Everything else either states
a fact or was synthesised here:

  * `slug`, `name`     - a topic's name. "Docker" is a fact, not an expression.
  * `est_hours`        - our estimate, from material volume. Never published by
                         roadmap.sh; `scripts/import_roadmapsh.py` computes it.
  * `prerequisites`    - ours. Their canvas carries no dependency edges at all,
                         so the importer derives these from reading order.
  * `difficulty`       - ours, derived from position in the track.
  * `resources`        - URLs. A link is a fact; following it sends the reader
                         to the publisher, which is the opposite of copying.

So this script empties `content_md` and `summary`, replaces them with an honest
outline stub of our own words, and leaves the skeleton intact. The result is a
track a learner can navigate and study from — a syllabus plus primary sources —
that contains none of roadmap.sh's text.

`authored-*.yaml` files are never touched: they are ours already, and they are
what an outline track becomes when a later authoring wave reaches it.

    python scripts/strip_imported_prose.py --dry-run     # report, change nothing
    python scripts/strip_imported_prose.py               # rewrite in place

Re-running is safe: an already-stripped concept is detected and left alone.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

BACKEND = Path(__file__).resolve().parent.parent
TRACKS_DIR = BACKEND / "app" / "seed" / "tracks"

# Written into every stripped concept so the state is self-describing in the
# file, in a diff, and in the database.
OUTLINE_MARKER = "<!-- skillatlas:outline -->"

# Anything at or below this word count was already a stub from the importer.
STUB_WORDS = 40


def outline_body(name: str, resources: list[dict]) -> str:
    """The replacement for a concept body, in our own words.

    Deliberately says what it is rather than pretending to be a lesson. A
    reader who opens an outline concept should immediately understand that the
    depth is not here yet and where to go instead.
    """
    lines = [
        OUTLINE_MARKER,
        "",
        f"## {name}",
        "",
        "This step is an **outline**: the syllabus entry and its primary "
        "sources, without a written lesson yet. It tells you what to learn and "
        "where the authoritative material is; it does not teach it to you.",
        "",
        "Work through the linked sources below in order. They are the "
        "publishers' own documentation rather than a summary of it, so they "
        "stay correct as the tools change.",
    ]
    if not resources:
        lines += [
            "",
            "> No sources are attached to this step yet. Search the official "
            "documentation for the topic above, and treat the vendor's own "
            "reference as the starting point.",
        ]
    lines += [
        "",
        "*Full lessons are written one track at a time. Tracks that have been "
        "written carry complete material, worked examples and a quiz; this one "
        "is queued.*",
    ]
    return "\n".join(lines)


def outline_summary(name: str) -> str:
    return f"Outline step covering {name}, with links to primary sources."


def strip_file(path: Path, dry_run: bool) -> tuple[int, int, int]:
    """Returns (concepts, stripped_now, words_removed)."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    concepts = data.get("concepts") or []

    stripped = 0
    words_removed = 0
    changed = False

    for concept in concepts:
        # A reference entry (slug only) is defined in another file; skip it.
        if set(concept.keys()) <= {"slug", "is_core"}:
            continue

        body = concept.get("content_md") or ""
        if OUTLINE_MARKER in body:
            continue  # already stripped on a previous run

        word_count = len(body.split())
        name = concept.get("name") or concept.get("slug", "this topic")
        resources = concept.get("resources") or []

        if word_count > STUB_WORDS:
            words_removed += word_count
        stripped += 1
        changed = True

        if not dry_run:
            concept["content_md"] = outline_body(name, resources)
            concept["summary"] = outline_summary(name)

    if changed and not dry_run:
        path.write_text(
            yaml.dump(
                data,
                sort_keys=False,
                allow_unicode=True,
                width=100000,
                default_flow_style=False,
            ),
            encoding="utf-8",
        )

    return len(concepts), stripped, words_removed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would change without writing anything",
    )
    parser.add_argument("--tracks-dir", type=Path, default=TRACKS_DIR)
    args = parser.parse_args()

    files = sorted(args.tracks_dir.glob("*.yaml"))
    imported = [p for p in files if not p.name.startswith("authored-")]
    authored = len(files) - len(imported)

    if not imported:
        print(f"No imported track files in {args.tracks_dir}.")
        return 0

    total = stripped = words = 0
    for path in imported:
        concepts, n, w = strip_file(path, args.dry_run)
        total += concepts
        stripped += n
        words += w
        if n:
            print(f"  {path.name:<38} {n:>4} concepts stripped")

    verb = "would remove" if args.dry_run else "removed"
    print()
    print(f"{'DRY RUN - ' if args.dry_run else ''}{len(imported)} imported tracks, "
          f"{total} concepts, {stripped} stripped")
    print(f"{verb} {words:,} words of third-party prose")
    print(f"{authored} authored tracks left untouched")
    if not args.dry_run and stripped:
        print("\nRe-seed to apply:  python -m app.seed.loader")
    return 0


if __name__ == "__main__":
    sys.exit(main())
