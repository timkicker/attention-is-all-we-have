-- timeline: every life of the claims the judge paired with the claim (same, partial, contradicts), at any distance
SELECT b.lang, b.page_id, b.h, b.text, b.born_rev, b.died_rev, b.died_comment, b.time_precision,
       b.row_start, b.row_end, VEC_DISTANCE_COSINE(b.emb, q.emb) AS dist
FROM (
  SELECT b_lang AS lang, b_h AS h FROM verdict
  WHERE a_lang = %(lang)s AND a_h = %(h)s AND label IN ('same', 'partial', 'contradicts')
  UNION
  SELECT a_lang, a_h FROM verdict
  WHERE b_lang = %(lang)s AND b_h = %(h)s AND label IN ('same', 'partial', 'contradicts')
) x
JOIN (SELECT emb FROM claim FOR SYSTEM_TIME ALL
      WHERE lang = %(lang)s AND page_id = %(page_id)s AND h = %(h)s LIMIT 1) AS q
JOIN claim FOR SYSTEM_TIME ALL AS b IGNORE INDEX (emb)
  ON b.topic_id = %(topic)s AND b.lang = x.lang AND b.h = x.h
ORDER BY b.lang, b.row_start
