-- check: a stored run and its claims
SELECT r.run_id, r.source, r.answer_model, r.answer_date, r.question, r.as_of, r.engine, c.idx, c.text, c.labels
FROM check_run r LEFT JOIN check_claim c ON c.run_id = r.run_id
WHERE r.run_id = %(run_id)s
ORDER BY c.idx
