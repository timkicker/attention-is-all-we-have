-- check: store one claim of a run with its vector and every judged candidate per edition
INSERT INTO check_claim (run_id, idx, text, emb, labels)
VALUES (%(run_id)s, %(idx)s, %(text)s, VEC_FromText(%(vec)s), %(labels)s)
