-- timeline: every life of one claim, from the revision that added it to the one that removed it
SELECT lang, page_id, h, topic_id, section, text, born_rev, died_rev, died_comment, time_precision, row_start, row_end
FROM claim FOR SYSTEM_TIME ALL
WHERE lang = %(lang)s AND page_id = %(page_id)s AND h = %(h)s
ORDER BY row_start
