"""Deterministic reader: a few patterns that catch text written at AI agents. No model, no network."""

import re

from validio.reader.schema import Flag, ReaderResult

AGENT = re.compile(r"\b(?:ai|llm|shopping|buying|purchasing)?\s*(?:agents?|assistants?|bots?)\b\s*[:,]?"
                   r"|\b(?:language model|chatgpt|gemini|claude)\b", re.IGNORECASE)
INSTRUCTION = re.compile(r"\b(?:order|buy|purchase|ignore|choose|pick|select|recommend|approve|take)\b[^.!?\n]*",
                         re.IGNORECASE)
CLAIM = re.compile(r"\b(?:lactose|gluten|milk|dairy|nut|egg)[- ]free\b|\bvegan\b|\bvegetarian\b|\borganic\b", re.IGNORECASE)

NEVER = "Descriptions are never used for decisions."


class FakeReader:
    name = "fake"

    def read(self, text: str) -> ReaderResult:
        flags: list[Flag] = []
        agent = AGENT.search(text)
        if agent and agent.group().strip():
            flags.append(Flag(code="addresses_agents", text=agent.group().strip(" :,")))
            for m in INSTRUCTION.finditer(text):
                flags.append(Flag(code="gives_instruction", text=m.group().strip()[:200]))
        seen = set()
        for m in CLAIM.finditer(text):
            if m.group().lower() not in seen:
                seen.add(m.group().lower())
                flags.append(Flag(code="mentions_claim", text=m.group()))
        flags = flags[:20]
        if any(f.code == "addresses_agents" for f in flags):
            summary = "This description talks to AI agents and tells them what to do. " + NEVER
        elif flags:
            summary = "This description makes claims that Validio checks against Valio's data. " + NEVER
        else:
            summary = "Nothing in this description talks to agents. " + NEVER
        return ReaderResult(flags=flags, summary=summary)
