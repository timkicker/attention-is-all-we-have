-- check: recorded answers available offline
SELECT run_id, question, answer_model, answer_date FROM check_run WHERE source = 'recorded' ORDER BY question, answer_model
