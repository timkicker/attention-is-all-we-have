# Parallax (working name): one event, many Wikipedias

Plan for our MariaDB entry (c-307), rebuilt on 14 Nov 2026 after Tim's talk at the Wikipedia/MariaDB booth. Deadline Sunday 10:00. Every number was measured on Saturday; the notes behind them get added to the repo with the loader.

## What changed and why

* The booth wants **cross-language comparison**: how the same topic reads in fi, sv, de, en, ru and others, which way each edition leans and how that moved over time. Their example was the Winter War.
* They **want vector search**. Yesterday's "vector search is not being used" was a misunderstanding.
* Tim's principle: **an assistant, never an editor.** The tool shows evidence and suggests; a person decides and edits on Wikipedia. That also fits the German AI policy of February 2026 (flagging tools allowed with human review of each suggestion, AI edits forbidden).
* Zombie Facts stays as one feature, now across languages: a claim one edition dropped while others still state it.
* We submit one MariaDB project (one entry per challenge). This plan replaces the Zombie Facts plan as that entry.

## The product

Pick a topic. Parallax lines up what each language edition says, claim by claim and lets you scrub through time.

1. **Compare.** One row per claim, one column per edition (fi, sv, de, en, ru, et, uk). Each cell is the edition's own sentence with an English gloss or "not found". Numbers that disagree are marked (Finnish dead: 26,662 fi, 22,830 sv, 25,904 en/ru/et/uk). Loaded terms are marked (Mainila: "fabricated" fi, "staged" de, "proven Soviet provocation" sv, "false flag" en, "according to the Soviet side" ru).
2. **Time.** A slider sets one date for all editions (`FOR SYSTEM_TIME AS OF`). The Mainila row replays live: en said "staged" until 2009, then "reported"; ru said "presumably staged" in 2009 and dropped "staged" on 9 Jul 2014 (rev 64106894).
3. **Dropped here, alive there** (Zombie Facts reborn). Claims an edition removed while other editions still state them, sorted by how long they stood. Each shows the edit comment and the oldid.
4. **Sources.** Where each edition's references come from: 78 of fi's 82 ISBNs are Finnish, 51 of ru's 96 are Russian or Soviet, en has the most references (288). Shown as one bar per edition, no verdict.
5. **For editors.** A suggestion card: "Stated in 4 editions with these sources, not found in fi." Buttons only open the section on that Wikipedia. No write API, no bot, no generated article text.
6. **Ask.** "What did each Wikipedia say about Mainila in 2010?" The answer quotes each edition's own sentences with links, no free text of our own.

Wording rules in the whole UI: "differs", "not found in", "uses the term", "cites mostly". Never "biased", "propaganda" or a ranking of editions. No editor names next to framing findings.

## How MariaDB carries it

* **System-versioned tables** `section` and `claim`, keyed by (topic, lang, section), loaded revision by revision so each row's period is the time the edition said it. One `AS OF` cuts all editions at the same instant: 1 to 2 ms measured.
* **Vectors** (`VECTOR(1024)`, bge-m3, multilingual) on every distinct claim. Cross-language nearest claim: 6 to 8 ms per language measured. AS OF plus `VEC_DISTANCE_COSINE` in **one statement** works and keeps the index ("as of 2008" en returns "staged", "as of 2012" returns "reported").
* **Each distinct sentence embedded once** across all revisions, so full history stays affordable. We report the ratio (revisions vs distinct sentences vs embeddings) on the video.
* Measured caveat: recall on 28 hand-checked pairs is top-1 0.57, top-5 0.89, top-10 0.96. So vectors fetch 5 candidates and **Nemotron judges** each pair (same claim, contradicts, different). The judge's verdicts are cached in a table, never shown as our own prose.
* Use `mhnsw_ef_search` 1000 or exact search per topic (exact was faster at this size while ef 80 with LIMIT 2 once missed).

## Data

* **Depth:** full history of 4 topics in 7 languages from the Wikimedia API: Winter War (88 editions exist), Finnish Civil War 1918, Continuation War, Shelling of Mainila. Winter War alone: en 6,720 revisions, ru 3,885, fi 2,148, de 1,197, sv 781, uk 660, et 253.
* **Breadth:** MariaDB's S dataset has fi, sv and en with one vector per article; 2,919 topics exist in all three. That gives an atlas: which topics each edition covers and how far apart their article vectors sit, with full depth for the 4 demo topics.
* **Zombie depth in fi:** the M dataset (862,076 fi revisions) we already parsed stays the source for long-lived dropped claims in Finnish.
* Rate limits: we hit HTTP 429 after about 8 fast calls. Fix: a User-Agent with our public repo URL (Wikimedia allows 200 requests a minute then; not yet tested), cache everything, fetch once.

## Side quests (one project per tech challenge; Validio already uses Modal)

1. **Nemotron:** the pair judge. Deliverable: form text with model id, what it does, how we improved it, plus the agreement score on our gold pairs.
2. **Verda:** batch job that embeds the distinct sentences of every revision (en history alone is 641 MB of text). Deliverable: process doc in the repo plus a post in Verda's Discord channel.
3. **Gemma:** English glosses of fi, sv, ru, et and uk sentences, run on Verda. One paragraph on why an open model on EU compute.
4. Skip Gemini, Context.dev and the database prizes. Fallback if Verda takes more than 2 hours to set up: embed locally, keep Nemotron, drop Verda and Gemma.

## Look

* Wikimedia's design system **Codex 2.7.0** (CSS tokens, components, dark mode, right-to-left), our own layout and name. Wikimedia's trademark policy forbids copying Wikipedia's look and feel and imitated articles, so no puzzle globe, no wordmark, no Vector header or sidebar, no "Wiki" in the name.
* Footer line "Not affiliated with the Wikimedia Foundation", CC BY-SA credit and a link on every quoted sentence. The repo becomes GPL-3.0-or-later if Codex CSS is vendored.
* Tim's density rule applies: a word or a number instead of a sentence, each fact once, rows not paragraphs.

## Originality (20 % of the score)

The challenge itself suggests comparing languages, so the idea alone scores nothing. What we can claim, worded carefully ("to our knowledge"): a live tool that treats five or more editions equally instead of measuring against English, follows single claims, terms and numbers through time and does alignment and time travel in one MariaDB query. Prior work we cite: MultiWiki (2016, pairs only, offline), WikiGap and InfoGap (English as reference), Xia and Gomez-Zara 2026 and Vestel 2026 (papers, no tool). A Meta-Wiki page edited in May 2026 says no tool compares editions for contradictions at scale.

## Timeline to Sunday 10:00

| When | What |
|---|---|
| Sat 13:00 to 15:00 | History loader for 4 topics × 7 languages with the cache and User-Agent fix; sentence splitter per language; schema in the repo |
| Sat 15:00 to 18:00 | Embeddings (Verda batch, local fallback); Nemotron judge on top 5 candidates; 30-pair gold set and agreement score |
| Sat 18:00 to 23:00 | Web app on Codex: Compare, Time, Dropped here, Sources; screenshot and reviewer pass per view |
| Sat 23:00 to 02:00 | Editor cards, Ask, S atlas; deploy |
| Sun 02:00 to 07:00 | Tests, numbers from the final run, video script, deck, Verda doc |
| Sun 07:00 to 09:30 | Tim records and submits; buffer |

## 2 minute demo

* 0:00 Title card: "Same war, seven Wikipedias."
* 0:10 Compare on the Winter War: the casualty row lights up, then the Mainila row with five different verbs.
* 0:40 Drag the slider: en flips from "staged" to "reported" in 2009, ru drops "staged" in 2014.
* 1:00 Dropped here, alive there: a claim fi removed that sv and en still state.
* 1:15 Sources bars per edition.
* 1:30 Editor card, the button opens fi.wikipedia; nothing is edited for you.
* 1:45 The one SQL statement (AS OF plus VEC_DISTANCE_COSINE), timings and the scale line.

## Risks

* **"Different" read as "biased".** Neutral wording everywhere, both sentences always visible, no scores per edition.
* **Matching quality.** Top 5 plus judge, gold set, show the agreement number honestly.
* **Rate limits.** Fetch once, cache, polite User-Agent; the 4 demo topics are about 15k revisions in total.
* **Parsing noise.** Navbox text leaked into de and en leads and the de infobox was not parsed; fix the splitter before the full run.
* **Time.** Cut order if late: Ask, S atlas, Gemma, Verda. Never cut Compare, Time, Dropped here.

## Open

1. Name: Parallax or another, as long as it has no "Wiki".
2. Who builds besides Tim, now that Validio is nearly done.
