-- check: the editions with deep data, labelled for every claim
SELECT DISTINCT p.lang FROM page p JOIN topic t ON t.topic_id = p.topic_id WHERE t.depth = 'deep'
