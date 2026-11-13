"""docs/RULES.md must match policies.cedar: every rule id with its effect, action and exact inputs,
and every context field of the schema. A rule changed in Cedar and not in the doc fails here."""

import re
from pathlib import Path

from validio.policy.decide import POLICY_FILE, SCHEMA_FILE

DOC = Path(__file__).parents[3] / "docs" / "RULES.md"


def cedar_rules(text: str) -> dict[str, dict]:
    rules = {}
    pattern = r'@id\("([^"]+)"\)\s*(permit|forbid)\s*\(([^)]*)\)\s*when\s*\{(.*?)\};'
    for m in re.finditer(pattern, text, re.DOTALL):
        rid, effect, head, body = m.groups()
        action = re.search(r'Action::"(\w+)"', head)
        rules[rid] = {
            "effect": effect,
            "action": action.group(1) if action else "every action",
            "inputs": set(re.findall(r"context\.(\w+)", body)),
        }
    return rules


def doc_rows(text: str, first_col: str) -> dict[str, list[str]]:
    """Rows of the markdown table whose header starts with `first_col`, keyed by the first cell."""
    rows, inside = {}, False
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("|") else None
        if cells and cells[0] == first_col:
            inside = True
            continue
        if not cells:
            inside = False
            continue
        if inside and not set(cells[0]) <= set(":-"):
            rows[cells[0].strip("`")] = cells
    return rows


def ticks(cell: str) -> set[str]:
    return set(re.findall(r"`(\w+)`", cell))


def test_policy_file_has_rules():
    assert len(cedar_rules(POLICY_FILE.read_text())) == 4


def test_every_rule_documented_with_its_inputs():
    rules = cedar_rules(POLICY_FILE.read_text())
    rows = doc_rows(DOC.read_text(), "Rule")
    assert set(rows) == set(rules), "rule ids in docs/RULES.md differ from policies.cedar"
    for rid, r in rules.items():
        _, effect, action, decides, inputs, _why = rows[rid]
        assert effect == r["effect"], rid
        assert action.strip("`") == r["action"], rid
        assert decides, rid
        assert ticks(inputs) == r["inputs"], f"{rid}: inputs in the doc differ from the rule"


def test_every_context_field_explained():
    ctx = SCHEMA_FILE.read_text().split("type Ctx = {")[1].split("};")[0]
    fields = set(re.findall(r"^\s*(\w+)\s*:", ctx, re.MULTILINE))
    rows = doc_rows(DOC.read_text(), "Field")
    assert set(rows) == fields, "context fields in docs/RULES.md differ from schema.cedarschema"
    for f, cells in rows.items():
        assert all(cells[1:]), f


def test_parser_catches_a_missing_rule(tmp_path):
    """Control: drop one row and the comparison fails."""
    text = DOC.read_text()
    broken = "\n".join(ln for ln in text.splitlines() if not ln.startswith("| `never-break-diet`"))
    assert set(doc_rows(broken, "Rule")) != set(cedar_rules(POLICY_FILE.read_text()))
