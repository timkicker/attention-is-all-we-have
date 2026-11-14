-- dropped: sentences born in the revision that dropped a sentence (same page), to see whether only a part was cut
SELECT lang, page_id, h, text, row_start
FROM claim FOR SYSTEM_TIME ALL
WHERE topic_id = %(topic)s AND (lang, page_id, row_start) IN %(keys)s
