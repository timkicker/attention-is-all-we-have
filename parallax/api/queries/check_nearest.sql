-- check: for one claim of the answer, the nearest sentence lives of one edition over the whole history (ANN, ef 1000).
-- The API repeats this block once per edition with UNION ALL, so it stays one statement.
SELECT lang, page_id, h, text, born_rev, died_rev, died_comment, row_start, row_end,
       VEC_DISTANCE_COSINE(emb, VEC_FromText(%(vec)s)) AS dist
FROM claim FOR SYSTEM_TIME ALL FORCE INDEX (emb)
WHERE lang = %(lang_{n})s
ORDER BY dist
LIMIT 5
