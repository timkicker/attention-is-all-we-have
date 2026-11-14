-- compare: is there a cached alignment for this date, anchor edition and topic
SELECT COUNT(*) AS n FROM align
WHERE as_of = %(day)s AND src_lang = %(anchor)s
  AND src_page IN (SELECT page_id FROM page WHERE topic_id = %(topic)s AND lang = %(anchor)s)
