-- check: for ended sentence lives, the nearest sentence the ending revision wrote on the same page (cosine distance)
SELECT d.lang, d.page_id, d.h, d.row_end, MIN(VEC_DISTANCE_COSINE(d.emb, s.emb)) AS dist
FROM claim FOR SYSTEM_TIME ALL AS d
JOIN claim FOR SYSTEM_TIME ALL AS s
  ON s.lang = d.lang AND s.page_id = d.page_id AND s.row_start = d.row_end AND s.h <> d.h
WHERE (d.lang, d.page_id, d.h, d.row_end) IN %(keys)s
GROUP BY d.lang, d.page_id, d.h, d.row_end
