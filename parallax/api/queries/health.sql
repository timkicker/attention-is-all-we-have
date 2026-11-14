-- health: row counts behind the scale line and the seed the database was loaded from
SELECT (SELECT COUNT(*) FROM claim FOR SYSTEM_TIME ALL) AS claim,
       (SELECT COUNT(*) FROM claim_life_fi FOR SYSTEM_TIME ALL) AS claim_life_fi,
       (SELECT COUNT(*) FROM verdict) AS verdict,
       (SELECT JSON_UNQUOTE(v) FROM stat WHERE k = 'seed') AS seed
