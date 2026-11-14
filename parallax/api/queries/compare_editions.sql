-- compare: the parsed revision of every edition at the instant, the one each quote links to
SELECT lang, page_id, rev_id, ts FROM (
  SELECT p.lang, p.page_id, r.rev_id, r.ts,
         ROW_NUMBER() OVER (PARTITION BY p.lang ORDER BY r.ts DESC) AS rn
  FROM page p
  JOIN revision r ON r.lang = p.lang AND r.page_id = p.page_id
  WHERE p.topic_id = %(topic)s AND r.snapshot = 1 AND r.ts <= %(as_of)s
) x
WHERE rn = 1
