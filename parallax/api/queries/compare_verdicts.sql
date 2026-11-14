-- compare: judge verdicts for the anchor claims of the page, in either direction (newest per pair wins)
SELECT a_lang, a_h, b_lang, b_h, label, numbers, terms, model, prompt_version, judged_at
FROM verdict
WHERE (a_lang = %(anchor)s AND a_h IN %(hs)s) OR (b_lang = %(anchor)s AND b_h IN %(hs)s)
ORDER BY judged_at
