-- dropped: the fi scale line, counted over every Finnish sentence life when table stat does not hold it yet
SELECT COUNT(*) AS fi_lives,
       COALESCE(SUM(row_end < NOW()), 0) AS fi_dead,
       COALESCE(SUM(row_end < NOW() AND DATEDIFF(row_end, row_start) >= 365), 0) AS fi_dead_1y,
       (SELECT COUNT(*) FROM revision WHERE lang = 'fi') AS fi_revisions
FROM claim_life_fi FOR SYSTEM_TIME ALL
