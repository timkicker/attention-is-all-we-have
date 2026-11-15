-- timeline: every life of one claim, from the revision that added it to the one that removed it
-- (the lives of a loaded topic only, once a topic took over the page from the Finnish M sample)
SELECT lang, page_id, h, topic_id, section, text, born_rev, died_rev, died_comment, time_precision, row_start, row_end
FROM claim FOR SYSTEM_TIME ALL AS c
WHERE lang = %(lang)s AND page_id = %(page_id)s AND h = %(h)s
  AND (topic_id IS NOT NULL OR NOT EXISTS (
    SELECT 1 FROM claim FOR SYSTEM_TIME ALL AS t
    WHERE t.lang = %(lang)s AND t.page_id = %(page_id)s AND t.h = %(h)s AND t.topic_id IS NOT NULL))
ORDER BY row_start
