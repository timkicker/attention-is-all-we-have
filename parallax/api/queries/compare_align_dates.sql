-- compare: the newest date of the align cache for this anchor edition and topic, on or before the day, if no claim of
-- the topic was born or removed between that date and the instant: the cached nearest are then the same
SELECT d.day FROM (
  SELECT MAX(as_of) AS day FROM align
  WHERE as_of <= %(day)s AND src_lang = %(anchor)s
    AND src_page IN (SELECT page_id FROM page WHERE topic_id = %(topic)s AND lang = %(anchor)s)
) AS d
WHERE d.day = %(day)s OR NOT EXISTS (
  SELECT 1 FROM claim FOR SYSTEM_TIME ALL AS c
  WHERE c.topic_id = %(topic)s
    AND (c.row_start > d.day AND c.row_start <= %(as_of)s OR c.row_end > d.day AND c.row_end <= %(as_of)s)
)
