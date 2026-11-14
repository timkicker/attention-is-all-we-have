-- ask: the k sentences of one edition nearest to the question, as the edition stood at as_of (vector index).
-- The API repeats this block once per edition with UNION ALL, so it stays one statement.
SELECT lang, h, text, born_rev, row_start, row_end,
       VEC_DISTANCE_COSINE(emb, VEC_FromText(%(vec)s)) AS dist
FROM claim FOR SYSTEM_TIME AS OF TIMESTAMP %(as_of)s FORCE INDEX (emb)
WHERE lang = %(lang_{n})s
ORDER BY VEC_DISTANCE_COSINE(emb, VEC_FromText(%(vec)s))
LIMIT %(k)s
