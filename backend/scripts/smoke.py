"""End-to-end smoke test against a *running* stack.

Unlike the pytest suite (which drives the app in-process), this walks the whole
product the way a person does — through the Next.js BFF, with real session
cookies — and asserts that the numbers on screen are derived from real work.

    python scripts/smoke.py                        # through the frontend, port 3000
    python scripts/smoke.py --base http://localhost:8010/api/v1 --direct

Exits non-zero on the first failure.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar

PASS = "  ok   "
FAIL = " FAIL  "


class Smoke:
    def __init__(self, base: str, direct: bool):
        self.base = base.rstrip("/")
        self.direct = direct
        self.token: str | None = None
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(CookieJar())
        )
        self.failures = 0

    # -- plumbing --------------------------------------------------------

    def request(self, method: str, path: str, body: dict | None = None):
        url = f"{self.base}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.direct and self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with self.opener.open(req, timeout=60) as response:
                payload = response.read().decode()
                return response.status, json.loads(payload) if payload else None
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode()
            try:
                return exc.code, json.loads(payload)
            except json.JSONDecodeError:
                return exc.code, {"detail": payload[:200]}
        except urllib.error.URLError as exc:
            raise SystemExit(f"Cannot reach {url}: {exc.reason}")

    def check(self, label: str, condition: bool, detail: str = ""):
        marker = PASS if condition else FAIL
        print(f"[{marker}] {label}" + (f"  — {detail}" if detail else ""))
        if not condition:
            self.failures += 1
        return condition

    # -- the walkthrough --------------------------------------------------

    def run(self) -> int:
        email = f"smoke+{int(time.time())}@example.com"
        password = "hunter2hunter2"

        print("\n1. Sign up")
        if self.direct:
            status, body = self.request(
                "POST", "/auth/signup", {"email": email, "password": password}
            )
            self.token = (body or {}).get("access_token")
        else:
            status, body = self.request(
                "POST", "/auth/signup", {"email": email, "password": password}
            )
        self.check("account created", status == 201, f"status {status}")

        status, me = self.request("GET", "/auth/me")
        self.check("session works", status == 200)
        self.check(
            "new account starts at zero",
            me["profile"]["xp"] == 0 and me["profile"]["level"] == 1,
            f"xp={me['profile']['xp']} level={me['profile']['level']}",
        )

        print("\n2. Roadmap")
        status, roadmap = self.request(
            "POST",
            "/roadmaps",
            {
                "track_slug": "backend-developer",
                "daily_hours": 3,
                "known_concept_slugs": ["git-version-control"],
            },
        )
        self.check("roadmap generated", status == 201, f"status {status}")
        self.check(
            "scheduled into weeks",
            len(roadmap["weeks"]) > 1,
            f"{roadmap['total_concepts']} concepts over {len(roadmap['weeks'])} weeks",
        )
        scheduled = {
            item["concept"]["slug"] for w in roadmap["weeks"] for item in w["items"]
        }
        self.check("known concept was skipped", "git-version-control" not in scheduled)

        status, again = self.request("GET", "/roadmaps/current")
        self.check("roadmap persisted", status == 200 and again["id"] == roadmap["id"])

        print("\n3. Locking")
        status, locked = self.request("GET", "/concepts/rest-api-design")
        self.check(
            "downstream concept is locked",
            locked["is_locked"],
            "needs " + ", ".join(c["slug"] for c in locked["missing_prerequisites"]),
        )
        status, _ = self.request("POST", "/progress/rest-api-design/complete", {"answers": []})
        self.check("cannot complete a locked concept", status == 409, f"status {status}")

        print("\n4. Study and complete")
        first = self.complete("internet-and-http")
        self.check("xp awarded", first["xp_earned"] > 0, f"+{first['xp_earned']} xp")
        self.check("streak started", first["streak_days"] == 1)
        self.check(
            "badge awarded",
            any(b["slug"] == "first-steps" for b in first["new_badges"]),
        )

        second = self.complete("programming-language-python")
        self.check(
            "completing prerequisites unlocks the next concept",
            any(c["slug"] == "rest-api-design" for c in second["unlocked_concepts"]),
        )

        status, unlocked = self.request("GET", "/concepts/rest-api-design")
        self.check("previously locked concept is now open", not unlocked["is_locked"])

        print("\n5. Build a project")
        status, project = self.request("GET", "/projects/http-message-parser")
        self.check("project served with its brief", status == 200 and bool(project["tests"]))
        self.check(
            "the worked solution is withheld until you pass",
            project["solution_md"] is None,
        )

        files = [{"path": f["path"], "content": f["content"]} for f in project["files"]]
        status, held = self.request(
            "POST",
            "/projects/http-message-parser/submit",
            {
                "files": [{"path": files[0]["path"], "content": "pass"}],
                "results": [{"test_id": t["id"], "passed": True} for t in project["tests"]],
            },
        )
        self.check(
            "a green run that ignores the brief is held back",
            status == 201 and not held["passed"] and bool(held["rejected_reason"]),
        )

        status, shipped = self.request(
            "POST",
            "/projects/http-message-parser/submit",
            {
                "files": files,
                "results": [{"test_id": t["id"], "passed": True} for t in project["tests"]],
            },
        )
        self.check(
            "project points awarded",
            shipped["passed"] and shipped["xp_earned"] == project["xp_reward"],
            f"+{shipped['xp_earned']} points",
        )
        self.check("solution revealed on a pass", bool(shipped["solution_md"]))

        status, again = self.request(
            "POST",
            "/projects/http-message-parser/submit",
            {
                "files": files,
                "results": [{"test_id": t["id"], "passed": True} for t in project["tests"]],
            },
        )
        self.check("resubmitting does not pay twice", again["xp_earned"] == 0)

        print("\n6. Points ledger explains the total")
        status, ledger = self.request("GET", "/progress/points")
        self.check("ledger populated", status == 200 and len(ledger) >= 3)
        status, me = self.request("GET", "/auth/me")
        total = sum(event["points"] for event in ledger)
        self.check(
            "ledger sums to the profile total",
            total == me["profile"]["xp"],
            f"{total} vs {me['profile']['xp']}",
        )

        print("\n7. Companies")
        status, companies = self.request("GET", "/companies")
        self.check("companies listed", status == 200 and len(companies) > 0, f"{len(companies)}")
        status, role = self.request("GET", "/companies/google/roles/software-engineer")
        self.check("role readiness computed", status == 200 and role["total_weight"] > 0,
                   f"{role['readiness_percent']}% ready")
        self.check(
            "every question cites a source",
            all(q["source_url"].startswith("http") for q in role["questions"]),
        )
        mapped = [a for a in role["focus_areas"] if a["concept_slug"]]
        self.check("focus areas link into the graph", len(mapped) > 0, f"{len(mapped)} mapped")
        status, extended = self.request(
            "POST",
            "/companies/nvidia/roles/deep-learning-engineer/add-to-roadmap",
            {"concept_slugs": []},
        )
        scheduled = {i["concept"]["slug"] for w in extended["weeks"] for i in w["items"]}
        self.check(
            "a role's gaps can be added to the route",
            status == 200 and "deep-learning-foundations" in scheduled,
        )

        print("\n8. Dashboard reflects the work")
        status, dash = self.request("GET", "/dashboard")
        stats = dash["stats"]
        # Two studied here, plus the one declared as prior knowledge at step 3 —
        # readiness counts declared knowledge, so this stat must agree with it.
        self.check(
            "concepts counted",
            stats["concepts_completed"] == 3,
            f"{stats['concepts_completed']} (2 studied + 1 prior knowledge)",
        )
        self.check("hours counted", stats["hours_invested"] > 0, f"{stats['hours_invested']}h")
        # Compared against a freshly read profile, not the snapshot taken at
        # signup: concepts and the project in step 5 have both paid out since.
        _, current = self.request("GET", "/auth/me")
        self.check(
            "xp matches the profile",
            stats["xp"] == current["profile"]["xp"],
            f'{stats["xp"]} vs {current["profile"]["xp"]}',
        )
        junior = next(
            (r for r in dash["roles"] if r["slug"] == "junior-backend-developer"), None
        )
        self.check(
            "role readiness computed",
            junior is not None and junior["percent"] > 0,
            f"junior backend {junior['percent'] if junior else 0}%",
        )
        self.check("gaps listed", len(dash["missing_skills"]) > 0)
        self.check(
            "velocity recorded",
            any(p["minutes"] > 0 for p in dash["velocity"]),
        )

        print("\n9. AI tutor")
        status, tutor = self.request("GET", "/chat/status")
        self.check("tutor reachable", status == 200, f"mode: {tutor['mode']}")
        answer, sources = self.ask("Why do caches serve stale data?")
        self.check("tutor answered", len(answer) > 40, f"{len(answer)} chars")
        self.check(
            "answer grounded in the right concept",
            "caching-strategies" in sources,
            f"sources: {', '.join(sources) or 'none'}",
        )

        print("\n10. Community")
        status, post = self.request(
            "POST",
            "/community/posts",
            {"title": "Smoke test discussion", "content": "Does this persist?"},
        )
        self.check("post created", status == 201)
        status, vote = self.request("POST", f"/community/posts/{post['id']}/vote")
        self.check("vote recorded", vote["upvotes"] == 1 and vote["viewer_has_voted"])
        status, _ = self.request(
            "POST", f"/community/posts/{post['id']}/comments", {"content": "It does."}
        )
        self.check("comment added", status == 201)
        status, detail = self.request("GET", f"/community/posts/{post['id']}")
        self.check(
            "everything persisted",
            detail["upvotes"] == 1 and detail["comment_count"] == 1,
        )
        self.request("DELETE", f"/community/posts/{post['id']}")

        print()
        if self.failures:
            print(f"{self.failures} check(s) failed.")
        else:
            print("All checks passed.")
        return 1 if self.failures else 0

    # -- helpers ----------------------------------------------------------

    def complete(self, slug: str) -> dict:
        """Complete a concept, using the graded review to answer correctly."""
        _, detail = self.request("GET", f"/concepts/{slug}")
        guess = [
            {"question_id": q["id"], "option_id": q["options"][0]["id"]}
            for q in detail["quiz"]
        ]
        _, result = self.request(
            "POST",
            f"/progress/{slug}/complete",
            {"answers": guess, "time_spent_minutes": 60},
        )
        if not result["passed"]:
            correct = [
                {"question_id": r["question_id"], "option_id": r["correct_option_id"]}
                for r in result["review"]
            ]
            _, result = self.request(
                "POST",
                f"/progress/{slug}/complete",
                {"answers": correct, "time_spent_minutes": 60},
            )
        self.check(f"completed {slug}", result["passed"])
        return result

    def ask(self, question: str) -> tuple[str, list[str]]:
        """Read the tutor's SSE stream to completion."""
        url = f"{self.base}/chat"
        req = urllib.request.Request(
            url, data=json.dumps({"message": question}).encode(), method="POST"
        )
        req.add_header("Content-Type", "application/json")
        if self.direct and self.token:
            req.add_header("Authorization", f"Bearer {self.token}")

        text, sources = [], []
        with self.opener.open(req, timeout=300) as response:
            for raw in response:
                line = raw.decode().strip()
                if not line.startswith("data: "):
                    continue
                event = json.loads(line[6:])
                if event["type"] == "sources":
                    sources = [s["slug"] for s in event["sources"]]
                elif event["type"] == "token":
                    text.append(event["text"])
        return "".join(text), sources


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        default="http://localhost:3000/api",
        help="API base URL (default: through the Next.js BFF)",
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        help="talk straight to FastAPI with bearer tokens instead of cookies",
    )
    args = parser.parse_args()

    print(f"SkillAtlas smoke test against {args.base}")
    return Smoke(args.base, args.direct).run()


if __name__ == "__main__":
    sys.exit(main())
