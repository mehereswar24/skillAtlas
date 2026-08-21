"""Re-point ``concept:`` references at the roadmap.sh concept set.

``roles.yaml``, ``seed/projects/*.yaml`` and ``seed/companies/*.yaml`` were
written against the hand-authored concept slugs (``internet-and-http``,
``relational-databases-sql``, ...). Importing roadmap.sh replaced every concept,
so those references dangle and the seed loader refuses to run.

This rewrites them in place. References are always the literal token
``concept: <slug>``, so it is a targeted text substitution — YAML comments,
ordering and inline-flow style all survive.

Matching is by token overlap against the *name* of each new concept, biased
towards the roadmaps a reference is most likely to have meant (a role roadmap
like ``backend`` beats an incidental mention inside ``laravel``). Anything that
does not clear ``--threshold`` is reported and left alone rather than being
silently mapped to something wrong.

Usage::

    python scripts/remap_concept_refs.py --dry-run     # report only
    python scripts/remap_concept_refs.py               # apply
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

BACKEND = Path(__file__).resolve().parent.parent
SEED = BACKEND / "app" / "seed"
TRACKS = SEED / "tracks"

TARGETS = [SEED / "roles.yaml", *sorted((SEED / "projects").glob("*.yaml")),
           *sorted((SEED / "companies").glob("*.yaml"))]

STOPWORDS = {"and", "the", "of", "a", "an", "to", "for", "in", "on", "with",
             "basics", "fundamentals", "foundations", "essentials", "intro",
             "introduction", "core", "learn"}

# Roadmaps a generic reference most plausibly points at, best first. Used only
# to break ties between equally good name matches.
PREFERRED = ["computer-science", "backend", "frontend", "devops", "full-stack",
             "system-design", "datastructures-and-algorithms", "sql", "python",
             "javascript", "docker", "kubernetes", "linux", "git-github",
             "machine-learning", "ai-engineer", "data-analyst", "cyber-security",
             "ux-design", "qa", "android", "api-design"]

# Where token matching is genuinely ambiguous, say what was meant.
OVERRIDES = {
    "internet-and-http": "frontend-internet",
    "git-version-control": "backend-version-control-systems",
    "programming-language-python": "python-learn-the-basics",
    "relational-databases-sql": "backend-relational-databases",
    "data-structures-algorithms": "computer-science-data-structures",
    "system-design-basics": "computer-science-system-design",
    "rest-api-design": "api-design-building-json-restful-apis",
    "containers-docker": "devops-containers",
    "ci-cd": "devops-ci-cd-basics",
    "linux-and-shell": "devops-operating-system",
    "cloud-fundamentals": "devops-cloud-providers",
}

CONCEPT_REF = re.compile(r"(?P<pre>\bconcept:\s*)(?P<slug>[A-Za-z0-9][A-Za-z0-9._-]*)")


def tokens(text: str) -> set[str]:
    parts = re.split(r"[^a-z0-9]+", text.lower())
    return {p for p in parts if p and p not in STOPWORDS}


def load_new_concepts() -> dict[str, dict]:
    """slug -> {name, roadmap} for every concept the importer produced."""
    out: dict[str, dict] = {}
    for path in sorted(TRACKS.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        roadmap = (data.get("track") or {}).get("slug", path.stem)
        for concept in data.get("concepts", []):
            slug = concept.get("slug")
            if slug and slug not in out:
                out[slug] = {"name": concept.get("name", ""), "roadmap": roadmap}
    return out


def score(old: str, slug: str, meta: dict) -> float:
    want = tokens(old)
    if not want:
        return 0.0
    have = tokens(meta["name"])
    if not have:
        return 0.0
    overlap = len(want & have)
    if not overlap:
        return 0.0
    # Jaccard, so "Internet" beats "Internet Protocol Suite Deep Dive".
    base = overlap / len(want | have)
    if tokens(meta["name"]) == want:
        base += 0.35
    try:
        base += (len(PREFERRED) - PREFERRED.index(meta["roadmap"])) / (len(PREFERRED) * 12)
    except ValueError:
        pass
    return base


def build_mapping(old_slugs: set[str], new: dict[str, dict],
                  threshold: float) -> tuple[dict[str, str], dict[str, str], list[str]]:
    mapping: dict[str, str] = {}
    how: dict[str, str] = {}
    unmatched: list[str] = []

    for old in sorted(old_slugs):
        if old in new:                       # already a valid new slug
            continue
        override = OVERRIDES.get(old)
        if override and override in new:
            mapping[old] = override
            how[old] = "override"
            continue
        best, best_score = None, 0.0
        for slug, meta in new.items():
            s = score(old, slug, meta)
            if s > best_score:
                best, best_score = slug, s
        if best and best_score >= threshold:
            mapping[old] = best
            how[old] = f"{best_score:.2f}"
        else:
            unmatched.append(old)
    return mapping, how, unmatched


def collect_refs(paths: list[Path]) -> set[str]:
    found: set[str] = set()
    for path in paths:
        for match in CONCEPT_REF.finditer(path.read_text(encoding="utf-8")):
            found.add(match.group("slug"))
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--threshold", type=float, default=0.34)
    parser.add_argument("--drop-unmatched", action="store_true",
                        help="delete skill/focus rows whose concept cannot be mapped")
    args = parser.parse_args(argv)

    new = load_new_concepts()
    if not new:
        print("error: no generated tracks found — run import_roadmapsh.py first",
              file=sys.stderr)
        return 2
    print(f"{len(new)} concepts available from roadmap.sh import")

    paths = [p for p in TARGETS if p.is_file()]
    refs = collect_refs(paths)
    print(f"{len(refs)} distinct concept references across {len(paths)} files")

    mapping, how, unmatched = build_mapping(refs, new, args.threshold)

    print(f"\nMapped {len(mapping)}:")
    for old, newslug in sorted(mapping.items()):
        print(f"  {old:38} -> {newslug:48} [{how[old]}]")
    if unmatched:
        print(f"\nUnmatched {len(unmatched)} (left as-is):")
        for old in unmatched:
            print(f"  {old}")

    if args.dry_run:
        print("\n(dry run — nothing written)")
        return 0

    dead = set(unmatched)
    changed = 0
    for path in paths:
        text = path.read_text(encoding="utf-8")

        if args.drop_unmatched and dead:
            kept = []
            for line in text.splitlines():
                match = CONCEPT_REF.search(line)
                stripped = line.lstrip()
                if (match and match.group("slug") in dead
                        and stripped.startswith("- ") and stripped.rstrip().endswith("}")):
                    continue          # a whole inline-flow skill/focus row
                kept.append(line)
            text = "\n".join(kept) + ("\n" if text.endswith("\n") else "")

        def sub(match: re.Match[str]) -> str:
            slug = match.group("slug")
            return match.group("pre") + mapping.get(slug, slug)

        updated = CONCEPT_REF.sub(sub, text)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed += 1

    print(f"\nRewrote {changed} files.")
    if unmatched and not args.drop_unmatched:
        print("Unmatched references remain and will fail the seed loader; "
              "re-run with --drop-unmatched or add entries to OVERRIDES.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
