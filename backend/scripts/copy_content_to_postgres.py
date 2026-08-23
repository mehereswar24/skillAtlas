"""Bulk-copy seeded content from the local SQLite database into Postgres.

Why this exists
---------------
`python -m app.seed.loader` is the right tool against a local database and the
wrong one against a remote managed Postgres. It works row by row — a SELECT to
check for an existing row, then an INSERT — which is fine at SQLite's
sub-millisecond latency and hopeless at a network's. Measured against Neon in
`us-east-1` from India the round trip is ~360ms, so the roughly 50,000
statements a full seed issues would take about five hours, inside a single
uncommitted transaction that shows no progress and leaves nothing behind if it
is interrupted.

Moving the database closer is not the fix: it belongs near the serverless
functions that read it on every request, not near whoever happens to be
seeding it. So the fix is to stop making 50,000 round trips. This sends each
table in batches of 1,000 rows, which turns the whole corpus into a few dozen
round trips and finishes in about a minute over the same link.

What it copies
--------------
Content only, in foreign-key order. User and runtime tables are deliberately
excluded — accounts, progress, roadmaps, applications, interviews, résumés,
chat history — because they are the developer's local test data and have no
business in production.

Two further exclusions worth naming:

* ``concept_embeddings`` — 7,427 vectors, ~23MB. Unused in production: the
  hosted provider cannot embed a query, so retrieval is BM25 and these would
  never be read. Regenerate with ``app.seed.loader --embed`` if an
  embedding-capable provider is ever configured.
* ``company_reviews`` — every row references a local test user by id, so
  copying them would violate the foreign key. They are development data.

Usage
-----
    $env:DATABASE_URL = "postgresql://...-pooler...neon.tech/db?sslmode=require"
    .\\venv\\Scripts\\python.exe scripts\\copy_content_to_postgres.py

Run migrations first; this fills existing tables, it does not create them.
Re-running is safe only against empty tables — pass --truncate to clear the
content tables first.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

BACKEND = Path(__file__).resolve().parent.parent
DEFAULT_SQLITE = BACKEND / "skillatlas.db"

#: Content tables in foreign-key order. Parents before children; the copy is a
#: plain insert, so a child arriving first would be rejected.
TABLES = [
    "domains",
    "tracks",
    "concepts",
    "track_concepts",
    "concept_prerequisites",
    "resources",
    "quiz_questions",
    "quiz_options",
    "interview_questions",
    "roles",
    "role_skills",
    "companies",
    "company_roles",
    "company_focus_areas",
    "company_questions",
    "company_resources",
    "projects",
    "project_tests",
    "project_files",
]

BATCH = 1000


def pg_columns(cur, table: str) -> dict[str, str]:
    """Column name -> Postgres data type, in ordinal order."""
    cur.execute(
        "select column_name, data_type from information_schema.columns "
        "where table_schema='public' and table_name=%s order by ordinal_position",
        (table,),
    )
    return {name: dtype for name, dtype in cur.fetchall()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", type=Path, default=DEFAULT_SQLITE)
    parser.add_argument(
        "--truncate", action="store_true",
        help="clear the content tables first (children before parents)",
    )
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith("postgres"):
        print("DATABASE_URL must be a postgresql:// URL.", file=sys.stderr)
        return 2
    if not args.sqlite.exists():
        print(f"No SQLite database at {args.sqlite}", file=sys.stderr)
        return 2

    src = sqlite3.connect(args.sqlite)
    src.row_factory = sqlite3.Row
    dst = psycopg2.connect(url, connect_timeout=20)
    dst.autocommit = False
    cur = dst.cursor()

    started = time.time()
    try:
        if args.truncate:
            # Reverse order so a child is emptied before its parent. RESTART
            # IDENTITY resets the sequences too, which matters because the ids
            # below are copied explicitly.
            joined = ", ".join(f'"{t}"' for t in reversed(TABLES))
            cur.execute(f"TRUNCATE {joined} RESTART IDENTITY CASCADE")
            print(f"truncated {len(TABLES)} tables")

        total = 0
        for table in TABLES:
            types = pg_columns(cur, table)
            if not types:
                print(f"  {table:24} SKIPPED (not in Postgres)")
                continue
            have = {r[1] for r in src.execute(f'PRAGMA table_info("{table}")')}
            cols = [c for c in types if c in have]
            missing = [c for c in types if c not in have]
            # SQLite stores booleans as 0/1 integers; Postgres will not accept
            # those in a boolean column, so convert by declared type rather
            # than by guessing from the value.
            bools = {c for c in cols if types[c] == "boolean"}

            quoted = ", ".join(f'"{c}"' for c in cols)
            rows = src.execute(f'SELECT {quoted} FROM "{table}"').fetchall()
            if not rows:
                print(f"  {table:24} 0")
                continue

            payload = [
                tuple(
                    bool(row[c]) if c in bools and row[c] is not None else row[c]
                    for c in cols
                )
                for row in rows
            ]
            execute_values(
                cur,
                f'INSERT INTO "{table}" ({quoted}) VALUES %s',
                payload,
                page_size=BATCH,
            )
            total += len(payload)
            note = f"  (no source column: {', '.join(missing)})" if missing else ""
            print(f"  {table:24} {len(payload)}{note}")

        # Copied ids came from SQLite, so Postgres' sequences still sit at 1 and
        # the next insert from the application would collide. Fast-forward each
        # to the highest id present.
        print("resetting sequences...")
        cur.execute(
            """
            select table_name, column_name, pg_get_serial_sequence(table_name, column_name)
            from information_schema.columns
            where table_schema='public' and column_default like 'nextval%'
            """
        )
        for table, column, seq in cur.fetchall():
            if table in TABLES and seq:
                cur.execute(
                    f"select setval(%s, coalesce((select max(\"{column}\") from \"{table}\"), 1))",
                    (seq,),
                )

        dst.commit()
        print(f"\ncommitted {total} rows in {time.time() - started:.0f}s")

        print("\nverifying row counts against the source:")
        ok = True
        for table in TABLES:
            cur.execute(f'select count(*) from "{table}"')
            got = cur.fetchone()[0]
            want = src.execute(f'select count(*) from "{table}"').fetchone()[0]
            flag = "" if got == want else "   <-- MISMATCH"
            if got != want:
                ok = False
            print(f"  {table:24} sqlite={want:<7} postgres={got:<7}{flag}")
        return 0 if ok else 1
    except Exception:
        dst.rollback()
        print("\nrolled back — nothing was written.", file=sys.stderr)
        raise
    finally:
        cur.close()
        dst.close()
        src.close()


if __name__ == "__main__":
    raise SystemExit(main())
