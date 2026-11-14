-- Checks for a loaded topic. `make checks` runs each block and diffs the output with checks_expected.txt.
-- name: claims_current_per_lang
SELECT lang, COUNT(*) FROM claim WHERE topic_id='winterwar' GROUP BY lang ORDER BY lang;
-- name: claims_all_per_lang
SELECT lang, COUNT(*) FROM claim FOR SYSTEM_TIME ALL WHERE topic_id='winterwar' GROUP BY lang ORDER BY lang;
-- name: sections_all_per_lang
SELECT lang, COUNT(*) FROM section_text FOR SYSTEM_TIME ALL WHERE topic_id='winterwar' GROUP BY lang ORDER BY lang;
-- name: revisions_per_lang
SELECT lang, COUNT(*), SUM(snapshot) FROM revision GROUP BY lang ORDER BY lang;
-- name: set_probe_vector
SET @v = (SELECT emb FROM claim WHERE lang='en' AND text LIKE 'On 26 November 1939, an incident was reported near the Soviet village of Mainila%' LIMIT 1);
-- name: probe_en_2008_nearest
SELECT LEFT(text, 60) FROM claim FOR SYSTEM_TIME AS OF TIMESTAMP '2008-06-01 00:00:00' IGNORE INDEX(emb) WHERE topic_id='winterwar' AND lang='en' ORDER BY VEC_DISTANCE_COSINE(emb, @v) LIMIT 1;
-- name: probe_en_2012_nearest
SELECT LEFT(text, 60) FROM claim FOR SYSTEM_TIME AS OF TIMESTAMP '2012-06-01 00:00:00' IGNORE INDEX(emb) WHERE topic_id='winterwar' AND lang='en' ORDER BY VEC_DISTANCE_COSINE(emb, @v) LIMIT 1;
-- name: probe_de_today_nearest
SELECT LEFT(text, 60) FROM claim IGNORE INDEX(emb) WHERE topic_id='winterwar' AND lang='de' ORDER BY VEC_DISTANCE_COSINE(emb, @v) LIMIT 1;
-- name: exact_staged_death
SELECT died_rev, row_end, time_precision FROM claim FOR SYSTEM_TIME ALL WHERE lang='en' AND text LIKE '%staged the shelling of Mainila%' AND died_rev=309285088;
-- name: ru_staged_term_2012_vs_2016
SELECT (SELECT COUNT(*) FROM term_hit FOR SYSTEM_TIME AS OF TIMESTAMP '2012-06-01 00:00:00' WHERE lang='ru' AND term_id='staged'), (SELECT COUNT(*) FROM term_hit FOR SYSTEM_TIME AS OF TIMESTAMP '2016-06-01 00:00:00' WHERE lang='ru' AND term_id='staged');
-- name: probe_en_2009_10_nearest
SELECT LEFT(text, 60) FROM claim FOR SYSTEM_TIME AS OF TIMESTAMP '2009-10-01 00:00:00' IGNORE INDEX(emb) WHERE topic_id='winterwar' AND lang='en' ORDER BY VEC_DISTANCE_COSINE(emb, @v) LIMIT 1;
-- name: en_mainila_2009_10_after_bisect
SELECT time_precision, LEFT(text, 70) FROM claim FOR SYSTEM_TIME AS OF TIMESTAMP '2009-10-01 00:00:00' WHERE topic_id='winterwar' AND lang='en' AND text LIKE '%Mainila%' AND text LIKE 'On 26 November%' ORDER BY text;
-- name: ru_mainila_2014_09_after_bisect
SELECT time_precision, LEFT(text, 90) FROM claim FOR SYSTEM_TIME AS OF TIMESTAMP '2014-09-01 00:00:00' WHERE topic_id='winterwar' AND lang='ru' AND text LIKE 'В тот же день%Майнила%' ORDER BY text;
-- name: ru_mainila_2010_11_after_bisect
SELECT time_precision, LEFT(text, 120) FROM claim FOR SYSTEM_TIME AS OF TIMESTAMP '2010-11-01 00:00:00' WHERE topic_id='winterwar' AND lang='ru' AND text LIKE 'В тот же день%Майнила%' ORDER BY text;
-- name: mainila_gap_after_exact_death
-- An exact death of a Mainila sentence must be followed at once by another Mainila sentence or by what the same edit wrote.
SELECT COUNT(*) FROM claim FOR SYSTEM_TIME ALL d WHERE d.topic_id='winterwar' AND d.time_precision='exact' AND d.row_end < NOW() AND d.text REGEXP 'Mainil|Майнил|Майніл' AND NOT EXISTS (SELECT 1 FROM claim FOR SYSTEM_TIME ALL r WHERE r.topic_id='winterwar' AND r.lang=d.lang AND r.row_start <= d.row_end AND r.row_end > d.row_end AND (r.born_rev = d.died_rev OR r.text REGEXP 'Mainil|Майнил|Майніл'));
-- name: exact_died_with_comment_per_lang
SELECT lang, COUNT(*), SUM(died_comment IS NOT NULL) FROM claim FOR SYSTEM_TIME ALL WHERE topic_id='winterwar' AND time_precision='exact' AND row_end < NOW() GROUP BY lang ORDER BY lang;
-- name: term_hits_current_per_lang
SELECT lang, COUNT(*) FROM term_hit WHERE topic_id='winterwar' GROUP BY lang ORDER BY lang;
-- name: term_hits_all_per_lang
SELECT lang, COUNT(*) FROM term_hit FOR SYSTEM_TIME ALL WHERE topic_id='winterwar' GROUP BY lang ORDER BY lang;
-- name: explain_ann_uses_emb
EXPLAIN SELECT h FROM claim ORDER BY VEC_DISTANCE_COSINE(emb, @v) LIMIT 5;
