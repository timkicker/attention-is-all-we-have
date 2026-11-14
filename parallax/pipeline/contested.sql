-- Contested claims: sentences that were removed and restored again and again (edit wars at sentence level).
-- Gaps were healed and vandal lives dropped before loading, so 3 or more lives are deliberate back and forth.
-- The grouping reads only the (page_id, h) key; texts are fetched for the groups that qualify.
SELECT g.page_id, p.title, g.h, g.lives,
       (SELECT COUNT(*) FROM claim_life_fi a WHERE a.page_id = g.page_id AND a.h = g.h) AS alive_now,
       (SELECT x.text FROM claim_life_fi FOR SYSTEM_TIME ALL x WHERE x.page_id = g.page_id AND x.h = g.h LIMIT 1) AS text
FROM (
  SELECT page_id, h, COUNT(*) AS lives
  FROM claim_life_fi FOR SYSTEM_TIME ALL
  GROUP BY page_id, h
  HAVING lives >= 3
) g
JOIN page p ON p.lang = 'fi' AND p.page_id = g.page_id
ORDER BY g.lives DESC, g.page_id, g.h
