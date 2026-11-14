-- check, within one topic: how many sentence lives each edition of the topic has over the whole history. A small
-- edition is searched exactly, a large one through the vector index (api/checker.py nearest).
SELECT lang, COUNT(*) AS n
FROM claim FOR SYSTEM_TIME ALL
WHERE topic_id = %(topic)s
GROUP BY lang
