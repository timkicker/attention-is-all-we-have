-- dropped: the sentences of the topic that are stated today, among those the judge paired with a dropped one
SELECT lang, page_id, h, text, born_rev
FROM claim
WHERE topic_id = %(topic)s AND h IN %(hs)s
