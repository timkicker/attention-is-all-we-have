-- dropped: sentence lives of the topic that ended, lived at least min_days and are not stated again today
SELECT d.lang, d.page_id, p.title, d.h, d.text, d.born_rev, d.died_rev, d.died_comment, d.time_precision,
       d.row_start, d.row_end, DATEDIFF(d.row_end, d.row_start) AS days,
       IF(d.time_precision = 'exact',
          (SELECT r.parent_id FROM revision r WHERE r.lang = d.lang AND r.rev_id = d.died_rev),
          (SELECT r.rev_id FROM revision r
           WHERE r.lang = d.lang AND r.page_id = d.page_id AND r.snapshot = 1 AND r.rev_id <> d.died_rev
             AND r.ts < d.row_end
           ORDER BY r.ts DESC LIMIT 1)) AS last_rev
FROM claim FOR SYSTEM_TIME ALL AS d
JOIN page p ON p.lang = d.lang AND p.page_id = d.page_id
WHERE d.topic_id = %(topic)s
  AND d.row_end < NOW()
  AND (%(lang)s IS NULL OR d.lang = %(lang)s)
  AND DATEDIFF(d.row_end, d.row_start) >= %(min_days)s
  AND NOT EXISTS (SELECT 1 FROM claim c WHERE c.lang = d.lang AND c.page_id = d.page_id AND c.h = d.h)
ORDER BY days DESC, d.lang, d.h
