-- dropped: judge verdicts that pair two sentences as the same claim (newest per pair wins)
SELECT a_lang, a_h, b_lang, b_h, label, model, prompt_version
FROM verdict
WHERE label IN ('same', 'partial')
ORDER BY judged_at
