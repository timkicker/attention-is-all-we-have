-- compare: the cached nearest candidates of table align for that date, with the candidate rows at the instant
SELECT al.src_h, al.dst_lang AS lang, b.page_id, b.h, b.section, b.text, b.born_rev, b.died_rev,
       b.time_precision, b.row_start, b.row_end, al.dist, al.`rank` AS rnk
FROM align al
JOIN claim FOR SYSTEM_TIME AS OF TIMESTAMP %(as_of)s AS b
  ON b.lang = al.dst_lang AND b.page_id = al.dst_page AND b.h = al.dst_h
WHERE al.as_of = %(day)s AND al.src_lang = %(anchor)s AND al.src_h IN %(hs)s AND al.dst_lang IN %(langs)s
  AND al.`rank` <= 5
ORDER BY al.src_h, al.dst_lang, al.`rank`
