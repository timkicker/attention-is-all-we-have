-- health: row counts behind the scale line
SELECT (SELECT COUNT(*) FROM claim FOR SYSTEM_TIME ALL) AS claim,
       (SELECT COUNT(*) FROM claim_life_fi FOR SYSTEM_TIME ALL) AS claim_life_fi,
       (SELECT COUNT(*) FROM verdict) AS verdict
