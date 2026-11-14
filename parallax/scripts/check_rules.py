"""Guards behind `make check-rules`: the PLAN rules a script can find.

Scans every file git tracks (or would track) under parallax/ plus the CI workflow. Exit 1 on a finding.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff", ".woff2", ".gz", ".lock"}
# Files that quote the rules themselves.
SKIP_FILES = {"PLAN.md", "scripts/check_rules.py"}

HOME_PATH = re.compile(r"(/home/[a-z_][\w.-]*/|/Users/[\w.-]+/|[A-Z]:\\\\Users\\\\)")
SECRETS = [
    re.compile(r"nvapi-[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
]
ENV_ASSIGN = re.compile(r"^(GEMINI_API_KEY|NVIDIA_API_KEYS|DB_PASSWORD|[A-Z_]*(API_KEY|TOKEN|SECRET))=(.+)$", re.M)
WIKI_WRITE = [
    re.compile(r"action\s*[=:]\s*['\"]?(edit|upload|move|delete|protect|rollback)\b"),
    re.compile(r"\b(csrftoken|oauth_consumer|mwoauth|pywikibot)\b", re.I),
]
# UI wording and look-alike rules apply to what the app shows.
UI_DIRS = ("web/", "api/")
UI_WORDS = re.compile(r"\b(biased|propaganda|liar|lies)\b", re.I)
LOOKALIKE = re.compile(r"cdxIconLogo|From Wikipedia, the free encyclopedia|puzzle.?globe|wikipedia-wordmark", re.I)
CODEX_COPY = re.compile(r"codex(-design-tokens)?(\.min)?\.(js|css)$")


def tracked() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "parallax", ".github/workflows/parallax.yml"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return [REPO / p for p in out if (REPO / p).is_file()]


def main() -> int:
    problems: list[str] = []
    for path in tracked():
        rel = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.relative_to(REPO).as_posix()
        if rel in SKIP_FILES or path.suffix in SKIP_SUFFIX:
            continue
        if rel == ".env" or rel.endswith("/.env"):
            problems.append(f"{rel}: .env must not be committed")
            continue
        if CODEX_COPY.search(path.name):
            problems.append(f"{rel}: Codex is loaded from jsDelivr, never copied into the repo")
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if m := HOME_PATH.search(text):
            problems.append(f"{rel}: home path {m.group(0)!r}")
        for rx in SECRETS:
            if rx.search(text):
                problems.append(f"{rel}: looks like a secret ({rx.pattern[:20]})")
        if path.name.startswith(".env"):
            for m in ENV_ASSIGN.finditer(text):
                problems.append(f"{rel}: {m.group(1)} has a value, keep it empty in the example")
        if rel.startswith(("pipeline/", "engine/", "api/", "web/src/")):
            for rx in WIKI_WRITE:
                if m := rx.search(text):
                    problems.append(f"{rel}: Wikimedia write call {m.group(0)!r}")
        if rel.startswith(UI_DIRS) and not rel.startswith(("api/tests/", "web/tests/")):
            if m := UI_WORDS.search(text):
                problems.append(f"{rel}: wording rule, {m.group(0)!r}")
            if m := LOOKALIKE.search(text):
                problems.append(f"{rel}: Wikipedia look-alike, {m.group(0)!r}")
    for p in problems:
        print(p)
    print(f"check-rules: {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
