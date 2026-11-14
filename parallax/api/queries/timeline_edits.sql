-- timeline: the sentence each life replaced (died where it was born) and the one that replaced it, with how close they are
SELECT p.lang, p.h AS p_h, p.born_rev AS p_born, p.died_rev AS p_died, p.died_comment AS p_comment,
       c.h, c.text, c.born_rev, c.died_rev, c.died_comment, c.time_precision, c.row_start, c.row_end,
       VEC_DISTANCE_COSINE(c.emb, p.emb) AS dist
FROM claim FOR SYSTEM_TIME ALL AS p
JOIN claim FOR SYSTEM_TIME ALL AS c
  ON c.lang = p.lang AND c.page_id = p.page_id AND c.h <> p.h
 AND (c.died_rev = p.born_rev OR c.born_rev = p.died_rev)
WHERE (p.lang, p.h) IN %(pairs)s
