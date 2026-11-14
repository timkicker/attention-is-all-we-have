-- check, within one topic, for a small edition (at most EXACT_MAX_LIVES lives of the topic) or one where the index's
-- 50 nearest lives held fewer than 5 of the topic: every life of the topic in that edition, measured one by one.
SELECT lang, page_id, h, text, born_rev, died_rev, died_comment, row_start, row_end,
       VEC_DISTANCE_COSINE(emb, VEC_FromText(%(vec)s)) AS dist
FROM claim FOR SYSTEM_TIME ALL IGNORE INDEX (emb)
WHERE topic_id = %(topic)s AND lang = %(lang_{n})s
ORDER BY dist
LIMIT 5
