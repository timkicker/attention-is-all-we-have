"""Write contract/fixtures/engine/*.json: a recorded answer, its three claims, judge labels and glosses.

The claim vectors are copies of seed rows, so the Check view finds real rows in fake mode.
Needs seed-mini loaded. Glosses are machine translation written for the demo path.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from contract.db import connect  # noqa: E402
from contract.engine import FIXTURES, claim_hash, vec_to_b64  # noqa: E402

c = connect().cursor()


def row(lang, h):
    c.execute("SELECT text, VEC_ToText(emb) FROM claim FOR SYSTEM_TIME ALL WHERE lang=%s AND h=%s LIMIT 1", (lang, h))
    t, e = c.fetchone()
    return t, json.loads(e)


ANSWER = (
    "The Shelling of Mainila on 26 November 1939 was staged by the Soviet Union to justify the invasion of Finland. "
    "According to the Soviet report, four Soviet soldiers were killed in the incident. "
    "Finnish artillery could not reach the village of Mainila."
)
claims = [
    (
        "The Shelling of Mainila on 26 November 1939 was staged by the Soviet Union to justify the invasion of Finland.",
        "en",
        "7aee25bc3466a2fc",
    ),
    ("According to the Soviet report, four Soviet soldiers were killed in the incident.", "sv", "a37b690a0d1e8d7f"),
    ("Finnish artillery could not reach the village of Mainila.", "sv", "fafe6f169258cd13"),
]
embed = {}
for text, lang, h in claims:
    _, v = row(lang, h)
    embed[claim_hash(text)] = {"text": text, "copy_of": f"{lang}:{h}", "emb": vec_to_b64(v)}
split = {claim_hash(ANSWER): {"text": ANSWER, "claims": [t for t, _, _ in claims]}}
C1, C2, C3 = (claim_hash(t) for t, _, _ in claims)
FI_M, FI_DEAD = "8519fbaf22d33984", "6fcbf86eca6b8af2"


def j(a_lang, b_lang, label, numbers=(), terms=(), note=""):
    return {
        "a_lang": a_lang,
        "b_lang": b_lang,
        "label": label,
        "numbers": [list(x) for x in numbers],
        "terms": [list(x) for x in terms],
        "note": note,
    }


judge = {
    # anchor fi: the Soviet Union staged the Mainila shots
    f"{FI_M}:176471723f110570": j("fi", "de", "same", terms=[("lavasti", "inszenierte")]),
    f"{FI_M}:a3b291dafd10d41b": j(
        "fi",
        "en",
        "partial",
        terms=[("lavasti", "reported")],
        note="en states that an incident was reported, not who caused it",
    ),
    f"{FI_M}:7aee25bc3466a2fc": j("fi", "en", "same", terms=[("lavasti", "staged")]),
    f"{FI_M}:fafe6f169258cd13": j("fi", "sv", "same", terms=[("lavasti", "kunnat bevisas")]),
    f"{FI_M}:07b09eb9ae0069c6": j("fi", "ru", "partial", note="ru quotes the Soviet note of 26 November"),
    f"{FI_M}:ac5853856a89a0eb": j("fi", "ru", "same", terms=[("lavasti", "инсценированный")]),
    f"{FI_M}:d74b5b02e646bb53": j("fi", "ru", "partial", note="ru states the shelling took place, not who caused it"),
    f"{FI_M}:b174df1b06bad0f0": j("fi", "et", "partial", note="et states what the Soviet government announced"),
    # anchor fi: Finnish dead
    f"{FI_DEAD}:1f3cc9d5435b2e2b": j("fi", "de", "same", numbers=[("26 662", "26.662")]),
    f"{FI_DEAD}:aabfc471f2095919": j("fi", "en", "contradicts", numbers=[("26 662", "25,904")]),
    f"{FI_DEAD}:3305d2b8a0f9e905": j("fi", "et", "same", numbers=[("26 662", "26 662")]),
    f"{FI_DEAD}:b36db6e825131f80": j("fi", "ru", "same", numbers=[("26 662", "26 662")]),
    # the recorded answer's claims
    f"{C1}:7aee25bc3466a2fc": j("en", "en", "same", terms=[("staged", "staged")]),
    f"{C1}:a3b291dafd10d41b": j("en", "en", "partial", terms=[("staged", "reported")]),
    f"{C1}:8519fbaf22d33984": j("en", "fi", "same", terms=[("staged", "lavasti")]),
    f"{C1}:176471723f110570": j("en", "de", "same", terms=[("staged", "inszenierte")]),
    f"{C1}:fafe6f169258cd13": j("en", "sv", "same"),
    f"{C1}:07b09eb9ae0069c6": j("en", "ru", "partial"),
    f"{C1}:b174df1b06bad0f0": j("en", "et", "partial"),
    f"{C2}:a37b690a0d1e8d7f": j("en", "sv", "same", numbers=[("four", "fyra")]),
    f"{C2}:07b09eb9ae0069c6": j("en", "ru", "partial"),
    f"{C3}:fafe6f169258cd13": j("en", "sv", "same"),
}
gloss_src = {
    (
        "fi",
        "8519fbaf22d33984",
    ): "The Soviet Union staged the Mainila shots on 26 November 1939, with which it justified the war as a defensive measure.",
    (
        "fi",
        "637a9e2c2dd2f38e",
    ): "Finally, on 26 November 1939, the Soviet Union staged the Mainila shots, with which the Soviet Union justified the war as a defensive measure.",
    (
        "fi",
        "aab5f383bc4504f0",
    ): "Against this background it made no difference whether shots had been fired at Mainila or not.",
    (
        "fi",
        "6fcbf86eca6b8af2",
    ): "Finnish losses in the Winter War were 26,662 killed in action and about 950 civilians.",
    (
        "de",
        "176471723f110570",
    ): "On 26 November the Red Army staged a border incident in the village of Mainila (Russian Майнило), in which Soviet troops were allegedly shelled by Finnish artillery.",
    ("de", "1f3cc9d5435b2e2b"): "Finnish historiography today counts 26,662 fallen soldiers.",
    (
        "sv",
        "fafe6f169258cd13",
    ): "It has since been proven that the incident was a Soviet provocation, since among other things no Finnish artillery could reach Mainila and Soviet prisoners during the Continuation War could give important details of how the episode was orchestrated on the Soviet side.",
    (
        "sv",
        "a37b690a0d1e8d7f",
    ): "On 26 November, at the village of Mainila on the Russian side next to the border, an incident occurred in which, according to the official Soviet report, four Soviet soldiers were killed by artillery fire.",
    (
        "sv",
        "635a8e4bb9af4a1d",
    ): "The official Soviet explanation for the attack referred to the above-mentioned shots at Mainila.",
    (
        "ru",
        "07b09eb9ae0069c6",
    ): "On 26 November 1939 the Soviet government addressed the government of Finland with an official note, which stated: «On 26 November, at 15:45, our troops stationed on the Karelian Isthmus at the Finnish border, near the village of Mainila, were unexpectedly fired on with artillery from Finnish territory.",
    (
        "ru",
        "d74b5b02e646bb53",
    ): "On the same day an artillery shelling of USSR territory took place near the settlement of Mainila.",
    (
        "ru",
        "ac5853856a89a0eb",
    ): "On the same day an artillery shelling of USSR territory took place near the settlement of Mainila, staged by the Soviet side, which is also confirmed by the corresponding orders of Mannerheim, who was sure a Soviet provocation would come and had therefore pulled his troops back from the border beforehand to a distance that ruled out misunderstandings.",
    ("ru", "0129ba24fb15e088"): "The Mainila incident became the official pretext for the war.",
    ("ru", "b36db6e825131f80"): "In total 26,662 Finnish servicemen died.",
    (
        "et",
        "b174df1b06bad0f0",
    ): "The government of the Soviet Union announced that Finland had fired on Red Army soldiers on exercises in the village of Mainila.",
    (
        "et",
        "3305d2b8a0f9e905",
    ): "In the Winter War Finland lost 26,662 men killed, 39,886 wounded and 1,434 missing or taken prisoner.",
}
gloss = {}
for (lang, h), en in gloss_src.items():
    c.execute("SELECT COUNT(*) FROM claim FOR SYSTEM_TIME ALL WHERE lang=%s AND h=%s", (lang, h))
    assert c.fetchone()[0], (lang, h)
    gloss[f"{lang}:{h}"] = {"text_en": en}
for k in judge:
    a, b = k.split(":")
    c.execute("SELECT COUNT(*) FROM claim FOR SYSTEM_TIME ALL WHERE h=%s", (b,))
    assert c.fetchone()[0], k
for name, d in [("embed", embed), ("split", split), ("judge", judge), ("gloss", gloss)]:
    (FIXTURES / f"{name}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("ok", len(judge), len(gloss))
