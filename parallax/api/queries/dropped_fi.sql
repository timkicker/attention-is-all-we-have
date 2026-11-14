-- dropped, fi scale: lives in every Finnish revision that ended, lived at least min_days and are not stated today
SELECT 'fi' AS lang, l.page_id, COALESCE(p.title, CONCAT('page ', l.page_id)) AS title, l.h, l.text,
       l.born_rev, l.died_rev, l.died_comment, l.reason, 'exact' AS time_precision,
       l.row_start, l.row_end, DATEDIFF(l.row_end, l.row_start) AS days,
       (SELECT r.parent_id FROM revision r WHERE r.lang = 'fi' AND r.rev_id = l.died_rev) AS last_rev,
       COUNT(*) OVER () AS total
FROM claim_life_fi FOR SYSTEM_TIME ALL AS l
LEFT JOIN page p ON p.lang = 'fi' AND p.page_id = l.page_id
WHERE l.row_end < NOW()
  AND (%(reason)s IS NULL OR l.reason = %(reason)s)
  AND DATEDIFF(l.row_end, l.row_start) >= %(min_days)s
  AND NOT EXISTS (SELECT 1 FROM claim_life_fi c WHERE c.page_id = l.page_id AND c.h = l.h)
ORDER BY days DESC, l.page_id, l.h
LIMIT %(limit)s OFFSET %(offset)s
