-- compare: claims of the anchor edition alive at the instant, [infobox] and [lead] first, reference lists last
SELECT a.page_id, a.h, a.section, a.text, a.born_rev, a.died_rev, a.time_precision, a.row_start, a.row_end,
       COUNT(*) OVER () AS total
FROM claim FOR SYSTEM_TIME AS OF TIMESTAMP %(as_of)s AS a
LEFT JOIN section_text FOR SYSTEM_TIME AS OF TIMESTAMP %(as_of)s AS s
  ON s.topic_id = a.topic_id AND s.lang = a.lang AND s.section = a.section
WHERE a.topic_id = %(topic)s AND a.lang = %(anchor)s AND (%(section)s IS NULL OR a.section = %(section)s)
ORDER BY CASE a.section WHEN '[infobox]' THEN 0 WHEN '[lead]' THEN 1 ELSE 2 END,
         a.section IN %(tail)s, a.section, LOCATE(a.text, s.text), a.h
LIMIT %(limit)s OFFSET %(offset)s
