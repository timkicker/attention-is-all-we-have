-- dropped: nearest sentence the dropping revision wrote on the same page, as cosine distance (small = reworded)
SELECT d.lang, d.page_id, d.h, MIN(VEC_DISTANCE_COSINE(d.emb, s.emb)) AS dist
FROM claim FOR SYSTEM_TIME ALL AS d
JOIN claim FOR SYSTEM_TIME ALL AS s
  ON s.topic_id = d.topic_id AND s.lang = d.lang AND s.page_id = d.page_id AND s.row_start = d.row_end AND s.h <> d.h
WHERE d.topic_id = %(topic)s AND (d.lang, d.page_id, d.h, d.row_end) IN %(keys)s
GROUP BY d.lang, d.page_id, d.h
