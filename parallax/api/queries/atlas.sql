-- atlas: one page of topics with the distances between their fi, sv and en article vectors; {order} is a fixed column
SELECT wikidata_id, title_fi, title_sv, title_en, coverage, dist_fi_sv, dist_fi_en, dist_sv_en, topic_id
FROM atlas_topic
WHERE %(coverage)s IS NULL OR coverage = %(coverage)s
ORDER BY {order}, wikidata_id
LIMIT %(limit)s OFFSET %(offset)s
