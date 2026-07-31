"""Check that every project can actually be passed.

A brief whose tests cannot go green is worse than no brief at all — the learner
loses an evening deciding the fault is theirs. This runs each project's tests
against a reference solution and fails loudly if any of them do not pass.

Reference solutions live in `app/seed/projects/_reference/<project-slug>/`,
mirroring the project's file paths. The loader only globs `*.yaml`, so they are
never seeded; they exist for this script and for review.

    python scripts/verify_projects.py            # every project
    python scripts/verify_projects.py lru-cache-with-ttl

Python projects run under CPython here rather than Pyodide. Pyodide *is*
CPython compiled to WebAssembly, so anything using only the standard library
behaves identically — and the briefs are constrained to the standard library
precisely so this holds.
"""

from __future__ import annotations

import sqlite3
import sys
import traceback
from pathlib import Path

import yaml

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECTS_DIR = BACKEND_DIR / "app" / "seed" / "projects"
REFERENCE_DIR = PROJECTS_DIR / "_reference"

GREEN, RED, YELLOW, DIM, RESET = (
    "\033[32m",
    "\033[31m",
    "\033[33m",
    "\033[2m",
    "\033[0m",
)


class VerifyError(Exception):
    """A project could not be verified."""


def load_projects() -> list[dict]:
    projects = []
    for path in sorted(PROJECTS_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for raw in data.get("projects", []):
            raw["_file"] = path.name
            projects.append(raw)
    return projects


def reference_files(project: dict) -> dict[str, str]:
    """The learner-editable files, with the reference solution substituted in."""
    files = {
        spec["path"]: spec.get("content", "") for spec in project.get("files", [])
    }
    root = REFERENCE_DIR / project["slug"]
    if not root.is_dir():
        raise VerifyError(
            f"no reference solution — expected {root.relative_to(BACKEND_DIR)}/"
        )
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    return files


# --------------------------------------------------------------------------
# runtimes
# --------------------------------------------------------------------------


def run_python(project: dict, files: dict[str, str]) -> list[tuple[str, str | None]]:
    """Exec the files as modules, then each test against that namespace.

    Mirrors the browser worker: every file becomes an importable module, the
    entry module's names are also exposed as globals, and a test passes when it
    raises nothing.
    """
    import types

    modules: dict[str, types.ModuleType] = {}
    entry_name = next(
        (
            spec["path"]
            for spec in project["files"]
            if spec.get("entry")
        ),
        None,
    )

    # Register every .py file as a module so `from fixtures import ROWS` works.
    for path, source in files.items():
        if not path.endswith(".py"):
            continue
        name = path[:-3].replace("/", ".")
        module = types.ModuleType(name)
        module.__dict__["__name__"] = name
        modules[name] = module
        sys.modules[name] = module

    try:
        for path, source in files.items():
            if not path.endswith(".py"):
                continue
            name = path[:-3].replace("/", ".")
            exec(compile(source, path, "exec"), modules[name].__dict__)

        entry_module = modules[entry_name[:-3].replace("/", ".")]
        results = []
        for test in project["tests"]:
            namespace = dict(entry_module.__dict__)
            try:
                exec(compile(test["code"], test["name"], "exec"), namespace)
                results.append((test["name"], None))
            except Exception:
                results.append((test["name"], traceback.format_exc(limit=3)))
        return results
    finally:
        for name in modules:
            sys.modules.pop(name, None)


def run_sql(project: dict, files: dict[str, str]) -> list[tuple[str, str | None]]:
    """Run the schema, then each test with `{{query}}` substituted."""
    import json

    schema = next(
        (
            content
            for path, content in files.items()
            if path.endswith(".sql") and "CREATE TABLE" in content.upper()
        ),
        "",
    )
    entry = next(spec["path"] for spec in project["files"] if spec.get("entry"))
    query = files[entry].strip().rstrip(";")

    results = []
    for test in project["tests"]:
        connection = sqlite3.connect(":memory:")
        try:
            connection.executescript(schema)
            sql = test["code"].replace("{{query}}", query)
            rows = [list(row) for row in connection.execute(sql).fetchall()]
            expected = json.loads(test["expected"])
            if rows == expected:
                results.append((test["name"], None))
            else:
                results.append(
                    (test["name"], f"got {rows!r}\n     expected {expected!r}")
                )
        except Exception:
            results.append((test["name"], traceback.format_exc(limit=2)))
        finally:
            connection.close()
    return results


RUNNERS = {"python": run_python, "sql": run_sql}


# --------------------------------------------------------------------------
# entrypoint
# --------------------------------------------------------------------------


def verify(project: dict) -> list[str]:
    """Return a list of failure messages; empty means the project is sound."""
    runner = RUNNERS.get(project["runtime"])
    if runner is None:
        # `web` projects need a DOM. They are checked in the browser, not here.
        return []

    failures = []
    for name, error in runner(project, reference_files(project)):
        if error is not None:
            failures.append(f"{name}\n     {error.strip().splitlines()[-1]}")

    # The other half of "the project is sound": the starter must not already
    # pass, or the learner is handed points for opening the page.
    starter = {
        spec["path"]: spec.get("content", "") for spec in project.get("files", [])
    }
    if all(error is None for _, error in runner(project, starter)):
        failures.append(
            "the starter files already pass every test — there is nothing to build"
        )
    return failures


def main(argv: list[str]) -> int:
    wanted = set(argv[1:])
    projects = [p for p in load_projects() if not wanted or p["slug"] in wanted]
    if not projects:
        print("No matching projects.", file=sys.stderr)
        return 1

    total_failures = 0
    skipped = 0

    for project in projects:
        label = f"{project['slug']} ({project['runtime']})"
        try:
            failures = verify(project)
        except VerifyError as exc:
            print(f"{YELLOW}SKIP{RESET} {label}\n     {exc}")
            skipped += 1
            continue

        if project["runtime"] == "web":
            print(f"{DIM}n/a {RESET} {label} — verified in the browser")
            continue
        if failures:
            total_failures += len(failures)
            print(f"{RED}FAIL{RESET} {label}")
            for failure in failures:
                print(f"     {failure}")
        else:
            count = len(project["tests"])
            print(f"{GREEN}ok{RESET}   {label} — {count} tests")

    print()
    if skipped:
        print(f"{YELLOW}{skipped} project(s) have no reference solution.{RESET}")
    if total_failures:
        print(f"{RED}{total_failures} test(s) failed against the reference.{RESET}")
        return 1
    print(f"{GREEN}Every reference solution passes its project's tests.{RESET}")
    return 0 if not skipped else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
