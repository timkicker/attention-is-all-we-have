-- topics: every topic with its editions, revision count, first and last stored revision
SELECT t.topic_id, t.label_en, t.wikidata_id, t.depth, p.lang, p.page_id, p.title, p.history,
       COUNT(r.rev_id) AS revisions, MIN(r.ts) AS first_ts, MAX(r.ts) AS last_ts
FROM topic t
JOIN page p ON p.topic_id = t.topic_id
LEFT JOIN revision r ON r.lang = p.lang AND r.page_id = p.page_id
GROUP BY t.topic_id, t.label_en, t.wikidata_id, t.depth, p.lang, p.page_id, p.title, p.history
ORDER BY t.depth, t.topic_id, FIELD(p.lang, 'fi', 'sv', 'de', 'en', 'ru', 'et', 'uk')
