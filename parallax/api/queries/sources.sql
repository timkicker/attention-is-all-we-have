-- sources: what each edition cited at one instant, counted per revision by Track A (A14)
SELECT lang, rev_id, refs, isbn, domains, row_start
FROM ref_stat FOR SYSTEM_TIME AS OF TIMESTAMP %(as_of)s
WHERE topic_id = %(topic)s
