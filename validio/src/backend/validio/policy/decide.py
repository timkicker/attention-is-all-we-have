"""Hard Lines: Cedar decides order alone, ask a person or block. The AI model never reaches this.

The context holds only whole numbers and yes/no values that Validio computed from Valio's data
and the verified Spend Pass. A policy file that fails to parse or validate raises PolicyError,
and the app refuses to start.
"""

import json
import os
from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from functools import cache
from math import ceil
from pathlib import Path
from typing import Any

import cedarpy

from validio.audit.sentences import eur
from validio.policy.mandate import Mandate

HERE = Path(__file__).resolve().parent
POLICY_FILE = HERE / "policies.cedar"
SCHEMA_FILE = HERE / "schema.cedarschema"

# Grades from Fact Grades that count as a kept diet rule. Anything else (unchecked, unknown,
# missing) means a person has to look.
DIET_KEPT = frozenset({"consistent", "attested"})


class PolicyError(Exception):
    """The policy file is broken or Cedar reported an error. Never treated as a decision."""


class Outcome(StrEnum):
    ALLOW = "allow"
    ESCALATE = "escalate"
    DENY = "deny"


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(w.capitalize() for w in rest)


@dataclass(frozen=True)
class PolicyContext:
    total_cents: int
    auto_limit_cents: int
    hard_cap_cents: int
    diet_contradicted: bool
    diet_unchecked: bool
    quantity_attested: bool
    cutoff_ok: bool
    is_substitute: bool = False
    on_valio_list: bool = False
    is_split: bool = False
    split_extra_bp: int = 0
    split_max_extra_bp: int = 0
    category_allowed: bool = True
    sales_block: bool = False
    is_renewal: bool = False
    drift_flag: bool = False

    def __post_init__(self) -> None:
        for f in fields(self):
            v = getattr(self, f.name)
            if type(v) is not f.type:
                raise TypeError(f"{f.name} must be {f.type.__name__}, got {type(v).__name__}")

    def to_cedar(self) -> dict[str, int | bool]:
        return {_camel(f.name): getattr(self, f.name) for f in fields(self)}


def _grade(g: Any) -> str:
    return str(getattr(g, "value", g))


def build_context(
    mandate: Mandate,
    *,
    total_cents: int,
    diet_grades: dict[str, Any],
    quantity_grade: Any,
    cutoff_ok: bool,
    category: str,
    is_substitute: bool = False,
    on_valio_list: bool = False,
    split_base_cents: int | None = None,
    sales_block: bool = False,
    is_renewal: bool = False,
    drift_flag: bool = False,
) -> PolicyContext:
    """Fill the Cedar context from typed facts. Undisclosed limits count as zero, an undisclosed
    diet counts as unchecked, so a pass that shows too little can never order alone."""
    grades = {k: _grade(v) for k, v in diet_grades.items()}
    diet = mandate.diet
    if diet is None:
        contradicted, unchecked = False, True
    else:
        contradicted = any(grades.get(d) == "contradicted" for d in diet)
        unchecked = any(grades.get(d) not in DIET_KEPT for d in diet)
    split_extra_bp = 0
    if split_base_cents is not None:
        if split_base_cents <= 0:
            raise ValueError("split base must be positive")
        split_extra_bp = max(0, ceil((total_cents - split_base_cents) * 10000 / split_base_cents))
    return PolicyContext(
        total_cents=total_cents,
        auto_limit_cents=mandate.auto_limit_cents or 0,
        hard_cap_cents=mandate.hard_cap_cents or 0,
        diet_contradicted=contradicted,
        diet_unchecked=unchecked,
        quantity_attested=_grade(quantity_grade) == "attested",
        cutoff_ok=cutoff_ok,
        is_substitute=is_substitute,
        on_valio_list=on_valio_list,
        is_split=split_base_cents is not None,
        split_extra_bp=split_extra_bp,
        split_max_extra_bp=mandate.split_max_extra_bp,
        category_allowed=any(category.startswith(c) for c in mandate.categories),
        sales_block=sales_block,
        is_renewal=is_renewal,
        drift_flag=drift_flag,
    )


def context_for(
    mandate: Mandate,
    product: Any,
    availability: Any,
    *,
    total_cents: int,
    now: datetime,
    is_substitute: bool = False,
    on_valio_list: bool = False,
    split_base_cents: int | None = None,
    is_renewal: bool = False,
    drift_flag: bool = False,
) -> PolicyContext:
    """The Cedar context for one product line, from Fact Grades and Valio's availability answer.

    `total_cents` must be recomputed from Valio's price, never taken from the agent."""
    from validio.trust.claims import claim_check
    from validio.trust.levels import TrustLevel, quantity_fact

    q = quantity_fact(availability)
    deliverable = availability is not None and availability.deliverable
    closing = availability.closing_time if availability is not None else None
    return build_context(
        mandate,
        total_cents=total_cents,
        diet_grades={d: claim_check(product, d)[0] for d in mandate.diet or ()},
        # "not deliverable" is an attested fact too, but nothing is there to order
        quantity_grade=q.level if deliverable else TrustLevel.MISSING,
        cutoff_ok=closing is not None and now < closing,
        category=product.category,
        is_substitute=is_substitute,
        on_valio_list=on_valio_list,
        split_base_cents=split_base_cents,
        sales_block=bool(availability is not None and availability.sales_block),
        is_renewal=is_renewal,
        drift_flag=drift_flag,
    )


@dataclass(frozen=True)
class Decision:
    outcome: Outcome
    rule_ids: list[str]
    sentence: str
    context: dict[str, int | bool]


@dataclass(frozen=True)
class Policy:
    policy_set: Any
    schema: str
    ids: dict[str, str]  # policy0 -> @id

    @property
    def rule_ids(self) -> list[str]:
        return list(self.ids.values())


def load_policy(path: Path = POLICY_FILE, schema_path: Path = SCHEMA_FILE) -> Policy:
    try:
        text = Path(path).read_text()
        schema = Path(schema_path).read_text()
    except OSError as e:
        raise PolicyError(f"cannot read policy: {e}") from e
    try:
        policy_set = cedarpy.PolicySet.from_str(text)
        parsed = json.loads(cedarpy.policies_to_json_str(text))
    except ValueError as e:
        raise PolicyError(f"{path}: parse error: {e}") from e
    if parsed.get("templates"):
        raise PolicyError(f"{path}: templates are not allowed")
    ids: dict[str, str] = {}
    for pid, body in parsed["staticPolicies"].items():
        rid = (body.get("annotations") or {}).get("id")
        if not rid:
            raise PolicyError(f"{path}: {pid} has no @id")
        if rid in ids.values():
            raise PolicyError(f"{path}: @id {rid!r} used twice")
        ids[pid] = rid
    if not ids:
        raise PolicyError(f"{path}: no policies")
    result = cedarpy.validate_policies(text, schema)
    if not result.validation_passed:
        raise PolicyError(f"{path}: validation failed: {result.errors}")
    return Policy(policy_set=policy_set, schema=schema, ids=ids)


def policy_file() -> Path:
    return Path(os.environ.get("VALIDIO_POLICY_FILE") or POLICY_FILE)


@cache
def _cached(path: Path) -> Policy:
    return load_policy(path)


def default_policy() -> Policy:
    return _cached(policy_file())


def _ask(policy: Policy, action: str, product_id: str, agent_id: str, ctx: dict) -> tuple[bool, list[str]]:
    request = {
        "principal": f'Agent::"{agent_id}"',
        "action": f'Action::"{action}"',
        "resource": f'Product::"{product_id}"',
        "context": ctx,
    }
    r = cedarpy.is_authorized(request, policy.policy_set, [], schema=policy.schema)
    if r.diagnostics.errors or r.decision not in (cedarpy.Decision.Allow, cedarpy.Decision.Deny):
        raise PolicyError(f"cedar error on {action}: {r.diagnostics.errors}")
    return r.allowed, [policy.ids.get(p, p) for p in r.diagnostics.reasons]


def _escalation_reasons(c: PolicyContext) -> list[str]:
    out = []
    if c.total_cents > c.auto_limit_cents:
        out.append(f"{eur(c.total_cents)} is over the auto limit of {eur(c.auto_limit_cents)}")
    if c.diet_unchecked:
        out.append("a diet rule cannot be checked")
    if not c.quantity_attested:
        out.append("Valio does not confirm the stock")
    if not c.cutoff_ok:
        out.append("the order cut-off has passed")
    if c.is_substitute and not c.on_valio_list:
        out.append("the substitute is not on Valio's list")
    if c.is_split and c.split_extra_bp > c.split_max_extra_bp:
        out.append(f"the split costs {c.split_extra_bp / 100:.2f} % more, over the limit")
    if c.drift_flag:
        out.append("Drift Watch flagged this line")
    return out


def decide(
    ctx: PolicyContext, product_id: str, agent_id: str = "buyer-1", policy: Policy | None = None
) -> Decision:
    policy = policy or default_policy()
    c = ctx.to_cedar()
    allowed, rules = _ask(policy, "PlaceOrder", product_id, agent_id, c)
    if allowed:
        sentence = (
            f"May order {product_id} alone: {eur(ctx.total_cents)} is inside the auto limit of "
            f"{eur(ctx.auto_limit_cents)} and every fact it needs is attested."
        )
        return Decision(Outcome.ALLOW, rules, sentence, c)
    allowed, esc_rules = _ask(policy, "Escalate", product_id, agent_id, c)
    if allowed:
        reasons = _escalation_reasons(ctx) or ["no rule lets the agent order it alone"]
        return Decision(Outcome.ESCALATE, esc_rules, "Needs a person: " + "; ".join(reasons) + ".", c)
    blocked = sorted(set(rules) | set(esc_rules))
    parts = []
    if "never-break-diet" in blocked:
        parts.append("a diet rule of the Spend Pass is contradicted by Valio's data")
    if "never-over-hard-cap" in blocked:
        parts.append(f"{eur(ctx.total_cents)} is over the hard cap of {eur(ctx.hard_cap_cents)}")
    if not parts:
        parts.append("no rule allows it (category outside the Spend Pass or a sales block)")
    return Decision(Outcome.DENY, blocked, "Blocked: " + "; ".join(parts) + ".", c)
