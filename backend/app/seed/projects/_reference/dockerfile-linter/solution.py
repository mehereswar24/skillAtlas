INSTALL_MARKERS = ("pip install", "npm ci", "npm install", "apt-get install")


def lint(dockerfile: str) -> list[dict]:
    findings: list[dict] = []
    copy_all_line: int | None = None
    has_user = False

    for number, raw in enumerate(dockerfile.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        instruction, _, rest = line.partition(" ")
        instruction = instruction.upper()

        if instruction == "FROM":
            image = rest.split()[0] if rest.split() else ""
            _, colon, tag = image.rpartition(":")
            if not colon or tag == "latest":
                findings.append({"line": number, "rule": "no-latest-tag"})

        elif instruction in {"COPY", "ADD"}:
            if rest.split() == [".", "."] and copy_all_line is None:
                copy_all_line = number

        elif instruction == "RUN":
            if copy_all_line is not None and any(
                marker in rest for marker in INSTALL_MARKERS
            ):
                findings.append({"line": copy_all_line, "rule": "copy-before-install"})
                copy_all_line = None
            if "apt-get install" in rest and "/var/lib/apt/lists" not in rest:
                findings.append({"line": number, "rule": "apt-without-cleanup"})

        elif instruction == "USER":
            has_user = True

    if not has_user:
        findings.append({"line": 1, "rule": "root-user"})

    return sorted(findings, key=lambda finding: (finding["line"], finding["rule"]))
