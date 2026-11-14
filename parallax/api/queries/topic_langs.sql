-- check: the editions one topic has
SELECT DISTINCT lang FROM page WHERE topic_id = %(topic)s
