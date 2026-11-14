-- Exact top 5 per source claim in one destination edition, both cut AS OF the same instant (A8).
-- Parameters: as_of date, then the instant twice, topic, src lang, topic, dst lang.
INSERT INTO align (as_of, src_lang, src_page, src_h, dst_lang, `rank`, dst_page, dst_h, dist, method)
SELECT %s, src_lang, src_page, src_h, dst_lang, rk, dst_page, dst_h, dist, 'exact' FROM (
  SELECT s.lang src_lang, s.page_id src_page, s.h src_h, d.lang dst_lang, d.page_id dst_page, d.h dst_h,
         VEC_DISTANCE_COSINE(s.emb, d.emb) dist,
         ROW_NUMBER() OVER (PARTITION BY s.page_id, s.h ORDER BY VEC_DISTANCE_COSINE(s.emb, d.emb), d.h) rk
  FROM claim FOR SYSTEM_TIME AS OF TIMESTAMP %s s IGNORE INDEX(emb)
  JOIN claim FOR SYSTEM_TIME AS OF TIMESTAMP %s d IGNORE INDEX(emb)
  WHERE s.topic_id = %s AND s.lang = %s AND d.topic_id = %s AND d.lang = %s
) x WHERE rk <= 5
