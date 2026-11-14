-- check, within one topic: the nearest sentence lives of one edition of that topic over the whole history.
-- Exact search (IGNORE INDEX): a topic holds a few thousand lives per edition, and filtering an index scan of the
-- whole table by topic could return fewer than 5. The API repeats this block once per edition with UNION ALL.
SELECT lang, page_id, h, text, born_rev, died_rev, died_comment, row_start, row_end,
       VEC_DISTANCE_COSINE(emb, VEC_FromText(%(vec)s)) AS dist
FROM claim FOR SYSTEM_TIME ALL IGNORE INDEX (emb)
WHERE topic_id = %(topic)s AND lang = %(lang_{n})s
ORDER BY dist
LIMIT 5
