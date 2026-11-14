-- check, within one topic: the nearest sentence lives of one large edition of that topic over the whole history.
-- The vector index (ANN, ef 1000) finds the 50 nearest lives of the edition across all topics; of those, the 5 of the
-- topic are its 5 nearest, since any closer life of the topic would be among the 50. When fewer than 5 of the 50 are
-- the topic's, the API asks check_nearest_topic_exact for that edition. Repeated once per edition with UNION ALL.
SELECT lang, page_id, h, text, born_rev, died_rev, died_comment, row_start, row_end, dist
FROM (
  SELECT lang, page_id, h, topic_id, text, born_rev, died_rev, died_comment, row_start, row_end,
         VEC_DISTANCE_COSINE(emb, VEC_FromText(%(vec)s)) AS dist
  FROM claim FOR SYSTEM_TIME ALL FORCE INDEX (emb)
  WHERE lang = %(lang_{n})s
  ORDER BY dist
  LIMIT 50
) AS near
WHERE topic_id = %(topic)s
ORDER BY dist
LIMIT 5
