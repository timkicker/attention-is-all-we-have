"""Every file path and test id that docs/SECURITY.md and docs/ARCHITECTURE.md cite must exist.

A citation is a code span. `test_api.py::test_retry_orders_once` names a test function under tests/.
A span with a slash or a file ending names a file, relative to validio/, src/backend/ or
src/backend/validio/. Routes (`/mcp`), commands and ignored data files are not citations.
Every image that a page in docs/ shows must exist next to it."""

import ast
import re
from pathlib import Path

import pytest

VALIDIO = Path(__file__).resolve().parents[3]
BACKEND = VALIDIO / "src" / "backend"
TESTS = BACKEND / "tests"
ROOTS = (VALIDIO, BACKEND, BACKEND / "validio")
DOCS = ("docs/SECURITY.md", "docs/ARCHITECTURE.md")
FILE_END = re.compile(r"\.(py|cedar|sh|ts|svelte|md|svg|png|json|toml)$")
SPAN = re.compile(r"`([^`\n]+)`")
IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)[^)]*\)|<img[^>]*\bsrc=\"([^\"]+)\"")


def defined_tests(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_"):
            names.add(n.name)
    return names


def broken_refs(text: str) -> list[str]:
    bad = []
    for span in SPAN.findall(text):
        span = span.strip()
        if " " in span or span.startswith(("/", "http", "data/", "make ", "-")):
            continue
        if "::" in span:
            file, _, name = span.partition("::")
            hits = [p for p in TESTS.rglob(Path(file).name) if p.as_posix().endswith(file)]
            if not hits or not any(name in defined_tests(p) for p in hits):
                bad.append(span)
        elif ("/" in span or FILE_END.search(span)) and not any((root / span).exists() for root in ROOTS):
            bad.append(span)
    return bad


def count_refs(text: str) -> tuple[int, int]:
    spans = [s for s in SPAN.findall(text) if " " not in s]
    return sum("::" in s for s in spans), sum("::" not in s and ("/" in s or bool(FILE_END.search(s))) for s in spans)


@pytest.mark.parametrize("doc", DOCS)
def test_cited_paths_and_test_ids_exist(doc):
    path = VALIDIO / doc
    assert path.exists(), f"{doc} is missing"
    assert broken_refs(path.read_text()) == []


def test_security_doc_cites_tests_and_files():
    tests, files = count_refs((VALIDIO / "docs/SECURITY.md").read_text())
    assert tests >= 20 and files >= 10


def test_checker_catches_a_wrong_test_id_and_path():
    text = ("`test_api.py::test_retry_orders_once` `test_api.py::test_no_such_test` "
            "`orders/service.py` `orders/no_such_file.py` `/mcp` `make test`")
    assert broken_refs(text) == ["test_api.py::test_no_such_test", "orders/no_such_file.py"]


def missing_images(text: str, base: Path) -> list[str]:
    refs = [a or b for a, b in IMAGE.findall(text)]
    return [r for r in refs if not r.startswith(("http:", "https:")) and not (base / r).is_file()]


@pytest.mark.parametrize("doc", sorted(p.name for p in (VALIDIO / "docs").glob("*.md")))
def test_every_image_in_docs_exists(doc):
    path = VALIDIO / "docs" / doc
    assert missing_images(path.read_text(), path.parent) == []


def test_image_check_catches_a_missing_image():
    docs = VALIDIO / "docs"
    text = '![a](img/architecture.svg) ![b](img/no-such.png) <img src="img/gone.svg"> ![c](https://x.invalid/a.png)'
    assert missing_images(text, docs) == ["img/no-such.png", "img/gone.svg"]
