-- compare: claims of the other editions alive at the instant that the judge paired with an anchor claim
-- (same, partial, contradicts), at whatever rank their vector distance puts them
SELECT x.src_h, b.lang, b.page_id, b.h, b.section, b.text, b.born_rev, b.died_rev, b.time_precision,
       b.row_start, b.row_end, VEC_DISTANCE_COSINE(b.emb, a.emb) AS dist
FROM (
  SELECT a_h AS src_h, b_lang AS lang, b_h AS h FROM verdict
  WHERE a_lang = %(anchor)s AND a_h IN %(hs)s AND b_lang IN %(langs)s AND label IN ('same', 'partial', 'contradicts')
  UNION
  SELECT b_h, a_lang, a_h FROM verdict
  WHERE b_lang = %(anchor)s AND b_h IN %(hs)s AND a_lang IN %(langs)s AND label IN ('same', 'partial', 'contradicts')
) x
JOIN claim FOR SYSTEM_TIME AS OF TIMESTAMP %(as_of)s AS a
  ON a.topic_id = %(topic)s AND a.lang = %(anchor)s AND a.h = x.src_h
JOIN claim FOR SYSTEM_TIME AS OF TIMESTAMP %(as_of)s AS b IGNORE INDEX (emb)
  ON b.topic_id = %(topic)s AND b.lang = x.lang AND b.h = x.h
