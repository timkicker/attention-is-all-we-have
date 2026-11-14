-- check: store one run so it can be replayed without the engine
INSERT INTO check_run (run_id, created_at, input_text, source, answer_model, answer_date, question, as_of, engine)
VALUES (%(run_id)s, UTC_TIMESTAMP(6), %(text)s, %(source)s, %(answer_model)s, %(answer_date)s, %(question)s,
        %(as_of)s, %(engine)s)
