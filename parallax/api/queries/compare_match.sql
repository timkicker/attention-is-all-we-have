-- compare: for every anchor claim on the page, the 5 nearest claims per other edition at the same instant.
-- Exact search inside the topic (IGNORE INDEX), so AS OF and the vector distance are one statement.
SELECT * FROM (
  SELECT a.h AS src_h, b.lang, b.page_id, b.h, b.section, b.text, b.born_rev, b.died_rev, b.time_precision,
         b.row_start, b.row_end, VEC_DISTANCE_COSINE(b.emb, a.emb) AS dist,
         ROW_NUMBER() OVER (PARTITION BY a.h, b.lang ORDER BY VEC_DISTANCE_COSINE(b.emb, a.emb)) AS rnk
  FROM claim FOR SYSTEM_TIME AS OF TIMESTAMP %(as_of)s AS a
  JOIN claim FOR SYSTEM_TIME AS OF TIMESTAMP %(as_of)s AS b IGNORE INDEX (emb)
    ON b.topic_id = a.topic_id AND b.lang IN %(langs)s
  WHERE a.topic_id = %(topic)s AND a.lang = %(anchor)s AND a.h IN %(hs)s
) c
WHERE rnk <= 5
ORDER BY src_h, lang, rnk
