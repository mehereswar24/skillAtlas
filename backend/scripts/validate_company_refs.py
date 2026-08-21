"""Check — and optionally repair — `concept:` references in company YAML.

Company profiles are authored (increasingly by agents) against a concept set of
~2,700 slugs, and a wrong one is only discovered when the seed loader refuses to
run. This finds them all in one pass instead of one per re-seed.

A company focus area is allowed to have no concept at all — "The 16 Leadership
Principles" never had one — so the repair is to *unlink* a dangling reference
and keep the author's label and notes, not to delete the row or guess wildly.
Where a close match plainly exists (`machine-learning-popular-ml-algorithms` →
`machine-learning-popular-algorithms`), it is remapped instead, and every
remap is printed so it can be checked.

Usage::

    python scripts/validate_company_refs.py            # report only
    python scripts/validate_company_refs.py --fix      # repair in place
"""

from __future__ import annotations

import argparse
import difflib
import glob
import os
import re
import sys

import yaml

TRACKS = "app/seed/tracks/*.yaml"
COMPANIES = "app/seed/companies/*.yaml"

# `concept: <slug>` inside an inline-flow map, with or without a trailing comma.
REF_WITH_COMMA = re.compile(r"concept:\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*,\s*")
REF_BARE = re.compile(r",?\s*concept:\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?=[},])")

# Below this, a "close match" is not close enough to apply silently.
SIMILARITY = 0.86


def valid_slugs() -> set[str]:
    slugs: set[str] = set()
    for path in glob.glob(TRACKS):
        data = yaml.safe_load(open(path, encoding="utf-8")) or {}
        for concept in data.get("concepts", []):
            if concept.get("slug"):
                slugs.add(concept["slug"])
    return slugs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix", action="store_true", help="repair in place")
    args = parser.parse_args(argv)

    slugs = valid_slugs()
    if not slugs:
        print("error: no concepts found — run the importer first", file=sys.stderr)
        return 2
    print(f"{len(slugs)} valid concept slugs")

    remapped: list[tuple[str, str, str]] = []
    unlinked: list[tuple[str, str]] = []

    for path in sorted(glob.glob(COMPANIES)):
        text = original = open(path, encoding="utf-8").read()
        name = os.path.basename(path)

        def resolve(match: re.Match[str]) -> str:
            slug = match.group(1)
            if slug in slugs:
                return match.group(0)
            close = difflib.get_close_matches(slug, slugs, n=1, cutoff=SIMILARITY)
            if close:
                remapped.append((name, slug, close[0]))
                return match.group(0).replace(slug, close[0])
            unlinked.append((name, slug))
            return ""

        text = REF_WITH_COMMA.sub(resolve, text)
        text = REF_BARE.sub(resolve, text)

        if text != original:
            if args.fix:
                open(path, "w", encoding="utf-8").write(text)

    if remapped:
        print(f"\nRemapped {len(remapped)} near-miss reference(s):")
        for name, old, new in remapped:
            print(f"  {name:22} {old}  ->  {new}")
    if unlinked:
        print(f"\nUnlinked {len(unlinked)} reference(s) with no close match:")
        for name, old in unlinked:
            print(f"  {name:22} {old}")
    if not remapped and not unlinked:
        print("\nEvery concept reference resolves.")
        return 0

    print("\n(dry run — pass --fix to apply)" if not args.fix else "\nApplied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
