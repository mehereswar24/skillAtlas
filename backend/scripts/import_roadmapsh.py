"""Import roadmap.sh roadmaps into SkillAtlas seed YAML.

Source of truth is roadmap.sh itself:

* **Structure** from ``https://roadmap.sh/<slug>.json`` — a React Flow canvas
  whose nodes carry x/y positions, not a dependency graph.
* **Content** from the ``nilbuild/developer-roadmap`` repo, one markdown file
  per node at ``roadmaps/<slug>/content/<topic>@<nodeId>.md``.
* **The catalogue** from ``https://roadmap.sh/pages.json``.

Mapping onto the SkillAtlas schema
----------------------------------
=========================  ====================================================
roadmap.sh                 SkillAtlas
=========================  ====================================================
roadmap                    ``Track`` (in a ``Domain`` from CATEGORIES below)
``topic`` node             ``Concept``
``subtopic`` node          a ``###`` section inside its parent concept
``@article@`` links        ``Resource`` rows
=========================  ====================================================

Two fields roadmap.sh does not publish, and how they are filled in:

``est_hours``
    No time data exists in the source. Estimated from how much material a topic
    carries (:func:`estimate_hours`) so the weekly scheduler has something to
    pack. These are guesses and the generated YAML says so.

``prerequisites``
    The canvas has no dependency edges; order is conveyed spatially, by reading
    top-to-bottom. Each concept therefore takes the previous one as its
    prerequisite, so a topological sort reproduces roadmap.sh's reading order.

Usage::

    python scripts/import_roadmapsh.py --repo <extracted-tarball-dir>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parent.parent
TRACKS_DIR = BACKEND / "app" / "seed" / "tracks"
DOMAINS_FILE = BACKEND / "app" / "seed" / "domains.yaml"

PAGES_URL = "https://roadmap.sh/pages.json"
ROADMAP_JSON = "https://roadmap.sh/{slug}.json"

CURRENT_YEAR = "2026"

MAX_SLUG = 110      # Concept.slug is String(120)
MAX_TITLE = 250     # Resource.title is String(255)
MAX_NAME = 190      # Concept.name is String(200)

# --------------------------------------------------------------------------
# Domains
#
# roadmap.sh's own taxonomy is only role/skill/beginner, too coarse for a
# browsable Explore page. These are subject areas; anything not listed falls
# back to `software-engineering`. This table is the only editorial judgement in
# the importer — edit freely.
# --------------------------------------------------------------------------
CATEGORIES: dict[str, dict[str, Any]] = {
    "frontend": {
        "name": "Frontend",
        "category": "Technology",
        "icon": "Monitor",
        "color": "text-blue-500",
        "description": "Build the interfaces people actually touch.",
        "slugs": ["frontend", "frontend-beginner", "react", "vue", "angular",
                  "javascript", "typescript", "html", "css", "nextjs"],
    },
    "backend": {
        "name": "Backend",
        "category": "Technology",
        "icon": "Server",
        "color": "text-green-500",
        "description": "The APIs, services and data layers behind an application.",
        "slugs": ["backend", "backend-beginner", "nodejs", "python", "java",
                  "golang", "rust", "php", "ruby", "ruby-on-rails", "spring-boot",
                  "aspnet-core", "django", "laravel", "graphql", "api-design",
                  "c", "cpp", "scala", "kotlin", "r"],
    },
    "fullstack": {
        "name": "Full Stack",
        "category": "Technology",
        "icon": "Layers",
        "color": "text-indigo-500",
        "description": "Own a feature end to end, database to button.",
        "slugs": ["full-stack"],
    },
    "mobile": {
        "name": "Mobile",
        "category": "Technology",
        "icon": "Smartphone",
        "color": "text-pink-500",
        "description": "Ship to phones — native and cross-platform.",
        "slugs": ["android", "ios", "react-native", "flutter", "swift-ui"],
    },
    "ai": {
        "name": "AI & Machine Learning",
        "category": "Technology",
        "icon": "Brain",
        "color": "text-purple-500",
        "description": "Models, agents and the engineering around them.",
        "slugs": ["ai-engineer", "ai-agents", "ai-data-scientist", "ai-red-teaming",
                  "ai-product-builder", "machine-learning", "mlops",
                  "prompt-engineering", "vibe-coding", "claude-code", "openclaw"],
    },
    "data": {
        "name": "Data",
        "category": "Technology",
        "icon": "BarChart3",
        "color": "text-amber-500",
        "description": "Turning raw data into decisions.",
        "slugs": ["data-analyst", "data-engineer", "bi-analyst", "power-bi",
                  "python-data-analysis", "sql", "postgresql-dba", "mongodb",
                  "redis", "elasticsearch"],
    },
    "devops": {
        "name": "DevOps & Cloud",
        "category": "Technology",
        "icon": "Cloud",
        "color": "text-cyan-500",
        "description": "Ship, run and keep software alive in production.",
        "slugs": ["devops", "devops-beginner", "aws", "docker", "kubernetes",
                  "terraform", "linux", "shell-bash", "cloudflare", "devsecops",
                  "network-engineer"],
    },
    "security": {
        "name": "Cybersecurity",
        "category": "Technology",
        "icon": "ShieldCheck",
        "color": "text-red-500",
        "description": "Attack, defend and harden real systems.",
        "slugs": ["cyber-security"],
    },
    "design": {
        "name": "Design",
        "category": "Design",
        "icon": "Palette",
        "color": "text-fuchsia-500",
        "description": "Interfaces and systems people understand at a glance.",
        "slugs": ["ux-design", "product-design", "design-system"],
    },
    "architecture": {
        "name": "Architecture",
        "category": "Technology",
        "icon": "Building2",
        "color": "text-slate-500",
        "description": "Designing systems that survive scale and change.",
        "slugs": ["software-architect", "software-design-architecture",
                  "system-design", "code-review", "api-design"],
    },
    "computer-science": {
        "name": "Computer Science",
        "category": "Education",
        "icon": "GraduationCap",
        "color": "text-teal-500",
        "description": "The fundamentals under every specialism.",
        "slugs": ["computer-science", "datastructures-and-algorithms", "leetcode",
                  "git-github", "git-github-beginner"],
    },
    "blockchain": {
        "name": "Blockchain",
        "category": "Technology",
        "icon": "Link2",
        "color": "text-orange-500",
        "description": "Distributed ledgers, contracts and the tooling around them.",
        "slugs": ["blockchain"],
    },
    "game-dev": {
        "name": "Game Development",
        "category": "Creative",
        "icon": "Gamepad2",
        "color": "text-lime-500",
        "description": "Build games and the servers behind them.",
        "slugs": ["game-developer", "server-side-game-developer"],
    },
    "quality": {
        "name": "Quality Engineering",
        "category": "Technology",
        "icon": "CheckCircle2",
        "color": "text-emerald-500",
        "description": "Testing and the practice of shipping things that work.",
        "slugs": ["qa"],
    },
    "careers": {
        "name": "Tech Careers",
        "category": "Business",
        "icon": "Briefcase",
        "color": "text-yellow-600",
        "description": "The non-code roles that ship software.",
        "slugs": ["product-manager", "engineering-manager", "technical-writer",
                  "devrel", "forward-deployed-engineer", "wordpress"],
    },
    "software-engineering": {
        "name": "Software Engineering",
        "category": "Technology",
        "icon": "Code2",
        "color": "text-violet-500",
        "description": "General engineering practice and everything else.",
        "slugs": [],  # fallback bucket
    },
}
FALLBACK_DOMAIN = "software-engineering"

# roadmap.sh resource-link kinds -> SkillAtlas Resource.kind
KIND_MAP = {
    "article": "article",
    "official": "doc",
    "documentation": "doc",
    "article@": "article",
    "course": "course",
    "video": "video",
    "opensource": "project",
    "book": "book",
    "podcast": "article",
    "website": "doc",
}
SKIP_KINDS = {"feed"}

RESOURCE_RE = re.compile(r"^\s*-\s*\[@(?P<kind>[a-z]+)@(?P<title>.*?)\]\((?P<url>\S+?)\)\s*$")
VISIT_RE = re.compile(r"^\s*Visit the following resources to learn more:?\s*$", re.I)
LEARN_RE = re.compile(r"^\s*Learn more from the following resources:?\s*$", re.I)


def slugify(text: str, limit: int = MAX_SLUG) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:limit].strip("-") or "topic"


def fetch_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "skillatlas-importer"})
    with urllib.request.urlopen(req, timeout=60) as fh:
        return json.loads(fh.read().decode("utf-8"))


# --------------------------------------------------------------------------
# content files
# --------------------------------------------------------------------------
def load_content_index(repo: Path, slug: str) -> dict[str, Path]:
    """Map ``nodeId -> markdown path`` for one roadmap."""
    content_dir = repo / "roadmaps" / slug / "content"
    index: dict[str, Path] = {}
    if not content_dir.is_dir():
        return index
    for path in content_dir.rglob("*.md"):
        if "@" in path.stem:
            index[path.stem.rsplit("@", 1)[1]] = path
    return index


def parse_content(path: Path | None) -> tuple[str, list[dict[str, Any]]]:
    """Split a roadmap.sh content file into prose and typed resource links."""
    if path is None or not path.is_file():
        return "", []
    raw = path.read_text(encoding="utf-8", errors="replace")

    body: list[str] = []
    resources: list[dict[str, Any]] = []
    for line in raw.splitlines():
        match = RESOURCE_RE.match(line)
        if match:
            kind = match.group("kind").lower()
            if kind in SKIP_KINDS:
                continue
            url = match.group("url").strip()
            title = match.group("title").strip()
            if not url.startswith("http") or not title:
                continue
            # A handful of roadmap.sh links are still plain http. Browsers
            # increasingly block or warn on those, and every host involved
            # serves https, so upgrade rather than ship a mixed-content link.
            if url.startswith("http://"):
                url = "https://" + url[len("http://"):]
            resources.append({
                "kind": KIND_MAP.get(kind, "doc"),
                "title": title[:MAX_TITLE],
                "url": url[:600],
            })
            continue
        if VISIT_RE.match(line) or LEARN_RE.match(line):
            continue
        body.append(line)

    # Drop the leading "# Title" — the concept/section heading already says it.
    while body and (not body[0].strip() or body[0].lstrip().startswith("# ")):
        body.pop(0)

    text = "\n".join(body).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return backtick_bare_tags(text), resources


CODE_SPAN = re.compile(r"```.*?```|`[^`]*`", re.S)
BARE_TAG = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)(\s*/?)>")


def backtick_bare_tags(text: str) -> str:
    """Wrap prose mentions of HTML tags in backticks.

    roadmap.sh prose says things like "extends the HTML <img> element". The app
    renders markdown with HTML disabled, so a bare tag shows up as literal text
    (or vanishes); as a code span it reads the way it was meant to. Existing
    code spans and fences are left alone.
    """
    out: list[str] = []
    last = 0
    for span in CODE_SPAN.finditer(text):
        out.append(BARE_TAG.sub(r"`<\1\2\3>`", text[last:span.start()]))
        out.append(span.group(0))
        last = span.end()
    out.append(BARE_TAG.sub(r"`<\1\2\3>`", text[last:]))
    return "".join(out)


# --------------------------------------------------------------------------
# canvas -> concepts
# --------------------------------------------------------------------------
def node_label(node: dict[str, Any]) -> str:
    label = (node.get("data") or {}).get("label") or ""
    return re.sub(r"\s+", " ", str(label)).strip()


def headings(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The nodes that become concepts.

    Most roadmaps use ``topic`` nodes as their headings, but a good few
    (engineering-manager, cyber-security) carry almost everything as
    ``subtopic`` under ``label`` headings instead — engineering-manager has one
    topic and 132 subtopics. Treating labels as headings too is what keeps
    those roadmaps from collapsing into a single giant concept. ``section``
    nodes look similar but are empty visual containers, so they are ignored.
    """
    return [n for n in nodes
            if n.get("type") in ("topic", "label") and node_label(n)]


def group_subtopics(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, list[dict]]:
    """Attach each subtopic to a heading.

    Explicit ``topic -> subtopic`` edges win where roadmap.sh drew them (about
    40% of the time). The rest are matched spatially: roadmap.sh lays a
    heading's subtopics beside or just below it, so the nearest heading
    vertically — with horizontal distance breaking ties — is the right parent.
    """
    by_id = {n["id"]: n for n in nodes}
    topics = headings(nodes)
    subs = [n for n in nodes if n.get("type") == "subtopic"]
    if not topics:
        return {}

    kids: dict[str, list[dict]] = defaultdict(list)
    claimed: set[str] = set()

    for edge in edges:
        src, dst = edge.get("source"), edge.get("target")
        s_node, d_node = by_id.get(src), by_id.get(dst)
        if not s_node or not d_node:
            continue
        if s_node.get("type") in ("topic", "label") and d_node.get("type") == "subtopic":
            if dst not in claimed:
                kids[src].append(d_node)
                claimed.add(dst)

    def pos(node: dict[str, Any]) -> tuple[float, float]:
        p = node.get("position") or {}
        return float(p.get("x", 0.0)), float(p.get("y", 0.0))

    for sub in subs:
        if sub["id"] in claimed:
            continue
        sx, sy = pos(sub)
        best = min(topics, key=lambda t: (abs(pos(t)[1] - sy), abs(pos(t)[0] - sx)))
        kids[best["id"]].append(sub)

    for topic_id, items in kids.items():
        items.sort(key=lambda n: (pos(n)[1], pos(n)[0]))
    return kids


def estimate_hours(prose_len: int, n_subtopics: int, n_resources: int) -> int:
    """Estimate study hours. roadmap.sh publishes no time data — see module docstring."""
    hours = 3 + 1.5 * n_subtopics + prose_len / 2500 + 0.25 * n_resources
    return int(max(2, min(round(hours), 40)))


def build_concepts(
    roadmap_slug: str,
    domain_slug: str,
    data: dict[str, Any],
    content: dict[str, Path],
) -> list[dict[str, Any]]:
    nodes = [n for n in data.get("nodes", []) if isinstance(n, dict) and n.get("id")]
    edges = [e for e in data.get("edges", []) if isinstance(e, dict)]
    kids = group_subtopics(nodes, edges)

    topics = headings(nodes)
    topics.sort(key=lambda n: (float((n.get("position") or {}).get("y", 0)),
                               float((n.get("position") or {}).get("x", 0))))

    concepts: list[dict[str, Any]] = []
    used: set[str] = set()

    for topic in topics:
        label = node_label(topic)
        base = slugify(f"{roadmap_slug}-{label}")
        slug = base
        n = 2
        while slug in used:
            slug = f"{base[:MAX_SLUG - 3]}-{n}"
            n += 1
        used.add(slug)

        prose, resources = parse_content(content.get(topic["id"]))
        sections: list[str] = []
        subs = kids.get(topic["id"], [])
        for sub in subs:
            sub_label = node_label(sub)
            if not sub_label:
                continue
            sub_prose, sub_res = parse_content(content.get(sub["id"]))
            sections.append(f"### {sub_label}\n\n{sub_prose}".rstrip()
                            if sub_prose else f"### {sub_label}")
            resources.extend(sub_res)

        body = "\n\n".join(x for x in ([prose] + sections) if x).strip()
        if not body:
            body = f"See the roadmap.sh page for **{label}**: https://roadmap.sh/{roadmap_slug}"

        # De-duplicate resources by URL, preserving order.
        seen: set[str] = set()
        deduped = []
        for res in resources:
            if res["url"] in seen:
                continue
            seen.add(res["url"])
            deduped.append(res)

        summary = (prose.split("\n\n")[0] if prose else "").strip()
        summary = re.sub(r"\s+", " ", summary)
        if not summary:
            summary = f"{label} — part of the roadmap.sh {roadmap_slug} roadmap."

        concepts.append({
            "slug": slug,
            "name": label[:MAX_NAME],
            "domain": domain_slug,
            "est_hours": estimate_hours(len(body), len(subs), len(deduped)),
            "difficulty": "beginner",
            "summary": summary[:600],
            "content_md": body,
            "resources": deduped[:25],
        })

    # Spatial reading order becomes a prerequisite chain (see module docstring).
    for i, concept in enumerate(concepts):
        concept["prerequisites"] = [concepts[i - 1]["slug"]] if i else []
    return concepts


# --------------------------------------------------------------------------
# YAML emission (hand-rolled: block scalars stay readable, no PyYAML quirks)
# --------------------------------------------------------------------------
def _block(text: str, indent: str) -> str:
    lines = (text or "").rstrip().splitlines() or [""]
    out = ["|-"]
    out += [f"{indent}{line}".rstrip() for line in lines]
    return "\n".join(out)


def _qstr(text: str) -> str:
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_track_yaml(track: dict[str, Any], concepts: list[dict[str, Any]]) -> str:
    out: list[str] = []
    out.append("# Generated by scripts/import_roadmapsh.py from roadmap.sh.")
    out.append("# Do not hand-edit: re-running the importer overwrites this file.")
    out.append(f"# Source: https://roadmap.sh/{track['source_slug']}")
    out.append("# est_hours are estimates (roadmap.sh publishes no time data) and")
    out.append("# prerequisites are the roadmap's own top-to-bottom reading order.")
    out.append("")
    out.append("track:")
    out.append(f"  slug: {track['slug']}")
    out.append(f"  title: {_qstr(track['title'])}")
    out.append(f"  domain: {track['domain']}")
    out.append(f"  target_role: {_qstr(track['target_role'])}")
    out.append(f"  difficulty: {track['difficulty']}")
    out.append(f"  description: {_qstr(track['description'])}")
    out.append("")
    out.append("concepts:")
    for concept in concepts:
        out.append(f"  - slug: {concept['slug']}")
        out.append(f"    name: {_qstr(concept['name'])}")
        out.append(f"    domain: {concept['domain']}")
        out.append(f"    est_hours: {concept['est_hours']}")
        out.append(f"    difficulty: {concept['difficulty']}")
        if concept["prerequisites"]:
            out.append("    prerequisites:")
            out += [f"      - {p}" for p in concept["prerequisites"]]
        else:
            out.append("    prerequisites: []")
        out.append(f"    summary: {_block(concept['summary'], '      ')}")
        out.append(f"    content_md: {_block(concept['content_md'], '      ')}")
        if concept["resources"]:
            out.append("    resources:")
            for res in concept["resources"]:
                out.append(f"      - kind: {res['kind']}")
                out.append(f"        title: {_qstr(res['title'])}")
                out.append(f"        url: {_qstr(res['url'])}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def render_domains_yaml(domains: list[str]) -> str:
    out = [
        "# Generated by scripts/import_roadmapsh.py.",
        "# Domains are subject-area buckets for the roadmap.sh catalogue; the",
        "# grouping lives in CATEGORIES in that script.",
        "#",
        "# `has_content` is NOT set here: the loader turns it on only for domains",
        "# that actually have a track.",
        "",
        "domains:",
    ]
    for slug in domains:
        meta = CATEGORIES[slug]
        out.append(f"  - slug: {slug}")
        out.append(f"    name: {_qstr(meta['name'])}")
        out.append(f"    category: {meta['category']}")
        out.append(f"    icon: {meta['icon']}")
        out.append(f"    color: {meta['color']}")
        out.append(f"    description: {_qstr(meta['description'])}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


# --------------------------------------------------------------------------
def domain_for(slug: str) -> str:
    for domain, meta in CATEGORIES.items():
        if slug in meta["slugs"]:
            return domain
    return FALLBACK_DOMAIN


ROLE_WORDS = ("engineer", "developer", "designer", "analyst", "manager",
              "architect", "administrator", "writer", "scientist", "dba", "qa")


def target_role(title: str, tags: list[str]) -> str:
    """A human job title. roadmap.sh titles are often a bare noun ('Frontend')."""
    if "role-roadmap" in tags:
        if any(word in title.lower() for word in ROLE_WORDS):
            return title
        return f"{title} Developer"
    return f"{title} Practitioner"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path,
                        help="extracted nilbuild/developer-roadmap tarball")
    parser.add_argument("--limit", type=int, default=0, help="import only N roadmaps")
    parser.add_argument("--only", default="", help="comma-separated roadmap slugs")
    parser.add_argument("--out", type=Path, default=TRACKS_DIR)
    parser.add_argument("--cache", type=Path, default=None,
                        help="directory to cache the per-roadmap JSON in")
    args = parser.parse_args(argv)

    repo = args.repo
    if not (repo / "roadmaps").is_dir():
        print(f"error: {repo} does not look like the developer-roadmap repo", file=sys.stderr)
        return 2

    print("Fetching roadmap.sh catalogue ...")
    pages = fetch_json(PAGES_URL)
    roadmaps = [p for p in pages if p.get("group") == "Roadmaps"]

    wanted = {s.strip() for s in args.only.split(",") if s.strip()}
    if wanted:
        roadmaps = [r for r in roadmaps if r.get("id") in wanted]
    if args.limit:
        roadmaps = roadmaps[: args.limit]

    # A roadmap we have written ourselves is no longer imported at all.
    #
    # This is the licence exit path, one track at a time: `authored-<slug>.yaml`
    # is our own curation and our own prose, tracked in git and publishable.
    # Once it exists the imported version is skipped entirely, so the
    # roadmap.sh copy stops being part of the product rather than sitting
    # underneath it. When every track is authored, the importer is dead code.
    authored = {
        path.stem[len("authored-"):]
        for path in args.out.glob("authored-*.yaml")
    }
    if authored:
        print(f"Skipping {len(authored)} roadmap(s) already authored: "
              f"{', '.join(sorted(authored))}")

    args.out.mkdir(parents=True, exist_ok=True)
    if args.cache:
        args.cache.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    used_domains: set[str] = set()
    skipped: list[tuple[str, str]] = []
    total_concepts = 0
    total_resources = 0

    for entry in roadmaps:
        slug = entry.get("id")
        if not slug:
            continue
        if slug in authored:
            skipped.append((slug, "authored — ours, not imported"))
            continue
        cache_file = (args.cache / f"{slug}.json") if args.cache else None
        try:
            if cache_file and cache_file.is_file():
                data = json.loads(cache_file.read_text(encoding="utf-8"))
            else:
                data = fetch_json(ROADMAP_JSON.format(slug=slug))
                if cache_file:
                    cache_file.write_text(json.dumps(data), encoding="utf-8")
        except Exception as exc:  # network / 404 / non-editor roadmap
            skipped.append((slug, f"no structure JSON ({exc})"))
            continue

        if not isinstance(data, dict) or not data.get("nodes"):
            skipped.append((slug, "empty canvas"))
            continue

        domain = domain_for(slug)
        content = load_content_index(repo, slug)
        concepts = build_concepts(slug, domain, data, content)
        if not concepts:
            skipped.append((slug, "no topic nodes"))
            continue

        title = entry.get("title") or data.get("title") or slug
        tags = (entry.get("metadata") or {}).get("tags") or []
        # roadmap.sh templates the year into its blurbs as a literal token.
        description = (entry.get("description") or "").replace("@currentYear@", CURRENT_YEAR).strip()
        track = {
            "slug": slug,
            "source_slug": slug,
            "title": title if title.lower().startswith(("become", "learn")) else f"{title} Roadmap",
            "domain": domain,
            "target_role": target_role(title, tags),
            "difficulty": "beginner" if "beginner-roadmap" in tags else "intermediate",
            "description": description or f"The roadmap.sh {title} roadmap.",
        }

        (args.out / f"{slug}.yaml").write_text(
            render_track_yaml(track, concepts), encoding="utf-8")
        written.append(slug)
        used_domains.add(domain)
        total_concepts += len(concepts)
        total_resources += sum(len(c["resources"]) for c in concepts)
        print(f"  {slug:34} {len(concepts):3} concepts  "
              f"{sum(len(c['resources']) for c in concepts):4} resources  -> {domain}")

    ordered = [d for d in CATEGORIES if d in used_domains]
    DOMAINS_FILE.write_text(render_domains_yaml(ordered), encoding="utf-8")

    print(f"\nWrote {len(written)} tracks, {total_concepts} concepts, "
          f"{total_resources} resources across {len(ordered)} domains.")
    if skipped:
        print(f"Skipped {len(skipped)}:")
        for slug, why in skipped:
            print(f"  {slug:34} {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
