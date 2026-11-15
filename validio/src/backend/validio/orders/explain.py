"""Why a request ended where it did, for the owner: a reason code and one plain sentence in the words of the
kitchen's own limits ("1,010.00 € is under your 1,200.00 € auto-order limit.").

Read from the decision Validio stored (its outcome, rule ids and sentence), never from the agent. The stored
sentence stays as it is; this only says it again for a person. Exceptions decided before any rule ran
(Valio not answering, a request that cannot be read, too many products) carry their code with them."""

import re
from datetime import date

MONEY = r"(\d[\d,]*\.\d\d €)"

# a sentence of its own, whatever the status: the decision never reached the limits
WHOLE = frozenset({"valio_down", "too_many", "unreadable", "none_available"})
WAITING = ("over_alone", "over_budget", "swap_unlisted", "diet_unchecked", "stock_unconfirmed", "ask_other")
BLOCKED = ("week_cap", "hard_cap", "diet", "no_price", "sales_block", "outside_groups", "none_available",
           "blocked_other")
CODES = ("auto_ok", *WAITING, *BLOCKED, "valio_down", "too_many", "unreadable")


def _day(iso: str | None) -> str:
    if not iso:
        return "your delivery date"
    d = date.fromisoformat(iso[:10])
    return f"{d:%a} {d.day} {d:%b}"


def _diet(diet: list[str] | tuple[str, ...]) -> str:
    return " and ".join(diet) or "diet"


def _lower(s: str) -> str:
    return s[:1].lower() + s[1:] if s[1:2].islower() or len(s) == 1 else s


def reason(decision: dict, diet: list[str] | tuple[str, ...] = (), deliver_by: str | None = None) -> tuple[str, str]:
    """(reasonCode, why). `why` is a clause for the status to lead ("Waiting for you: ..."), or a whole sentence
    when the code is in WHOLE."""
    if decision.get("reasonCode") and decision.get("ownerText"):
        return decision["reasonCode"], decision["ownerText"]
    s = decision.get("sentence") or ""
    rules = decision.get("ruleIds") or []
    outcome = decision.get("outcome")
    if outcome == "auto_order":
        m = re.search(rf"May order it (?:alone|automatically): {MONEY} is inside the auto limit of {MONEY}", s)
        if m:
            return "auto_ok", f"{m.group(1)} is under your {m.group(2)} auto-order limit"
        return "auto_ok", "it is inside your auto-order limit"
    if outcome == "ask_human":
        if m := re.search(rf"{MONEY} is over the auto limit of {MONEY}", s):
            return "over_alone", f"{m.group(1)} is over your {m.group(2)} auto-order limit"
        if "over-budget" in rules and (m := re.search(rf"{MONEY} is over the budget of {MONEY}", s)):
            return "over_budget", f"{m.group(1)} is over the {m.group(2)} budget the request names"
        if re.search(r"substitute (that )?is not on Valio's list", s):
            return "swap_unlisted", "the best swap isn't on Valio's own list, so you decide"
        if "a diet rule cannot be checked" in s:
            return "diet_unchecked", f"Valio's data doesn't confirm it is {_diet(diet)}, so you decide"
        if "does not confirm" in s and "stock" in s:
            return "stock_unconfirmed", "Valio doesn't confirm enough stock, so you decide"
        why = re.sub(r"^.*?Needs a person: ", "", s).split(". ")[0].rstrip(".")
        return "ask_other", _lower(why) or "your limits ask you to decide"
    # blocked
    if "never-over-week-cap" in rules and (m := re.search(rf"would make {MONEY}, over the weekly limit of {MONEY}", s)):
        return "week_cap", f"this week would reach {m.group(1)}, over your {m.group(2)} weekly limit"
    m = (re.search(rf"{MONEY} is over the hard cap of {MONEY}", s)
         or re.search(rf"{MONEY} is over the {MONEY} never-above limit", s))
    if "never-over-hard-cap" in rules or m:
        if m:
            return "hard_cap", (f"{m.group(1)} is over your {m.group(2)} never-above limit. "
                                "Your buying agent can't change this")
        return "hard_cap", "it is over your never-above limit. Your buying agent can't change this"
    if "never-break-diet" in rules:
        return "diet", f"Valio's own data shows it isn't {_diet(diet)}"
    if "Valio has no price for" in s:
        return "no_price", "Valio gives no price for " + s.split("Valio has no price for ", 1)[1].split(".")[0]
    if "sales block" in s:
        return "sales_block", "Valio has a sales block on it"
    if "outside the Spend Pass's product groups" in s:
        if m := re.search(r"outside the Spend Pass's product groups \(([^)]+)\)", s):
            names = m.group(1).split("; ")  # the groups the options sit in (supply._why_none)
            names = [names[0], *(n[:1].lower() + n[1:] for n in names[1:])]
            said = names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"
            return "outside_groups", f"{said} {'is' if len(names) == 1 else 'are'}n't in your product groups"
        return "outside_groups", "it is outside the product groups your limits allow"
    if s.startswith(("No plain ", "Valio's data doesn't show ")) and diet:  # every option broke the diet
        return "diet", f"Valio's own data doesn't show it is {_diet(diet)}"
    if not rules or "Valio gives no delivery line" in s:
        return "none_available", f"Nothing suitable arrives by {_day(deliver_by)}. Nothing was ordered."
    why = re.sub(r"^Blocked: ", "", s).split(". ")[0].rstrip(".")
    return "blocked_other", _lower(why)


def owner_text(status: str, code: str, why: str) -> str:
    """One sentence for the head of the request page, led by what happened."""
    if code in WHOLE:
        return why
    if status == "rejected":
        return "You chose not to order it. Nothing was ordered."
    if status in ("ordered", "approved"):
        return "Ordered after you approved. Validio asked Valio again first."
    lead = {"ordered_alone": "Bought without asking", "waiting": "Waiting for you", "blocked": "Not ordered",
            "working": "Cleared to buy without asking" if code == "auto_ok" else "Checking"}.get(status, "Not ordered")
    return f"{lead}: {why}."


def explain(decision: dict | None, status: str, diet: list[str] | tuple[str, ...] = (),
            deliver_by: str | None = None) -> dict:
    """{"reasonCode", "ownerText"} for a decision and the status the request or order is in now."""
    if not decision:
        return {}
    code, why = reason(decision, diet, deliver_by)
    return {"reasonCode": code, "ownerText": owner_text(status, code, why)}
