-- timeline: lives of the other editions of the topic nearest to the claim, over the whole history
SELECT * FROM (
  SELECT b.lang, b.page_id, b.h, b.text, b.born_rev, b.died_rev, b.died_comment, b.time_precision,
         b.row_start, b.row_end, VEC_DISTANCE_COSINE(b.emb, q.emb) AS dist,
         ROW_NUMBER() OVER (PARTITION BY b.lang ORDER BY VEC_DISTANCE_COSINE(b.emb, q.emb)) AS rnk
  FROM (SELECT emb FROM claim FOR SYSTEM_TIME ALL
        WHERE lang = %(lang)s AND page_id = %(page_id)s AND h = %(h)s LIMIT 1) AS q
  JOIN claim FOR SYSTEM_TIME ALL AS b IGNORE INDEX (emb)
    ON b.topic_id = %(topic)s AND b.lang <> %(lang)s
) c
WHERE rnk <= %(near)s
ORDER BY lang, row_start
