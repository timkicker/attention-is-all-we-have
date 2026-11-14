-- atlas: how many topics exist in which editions (fi alone, fi+sv, fi+en, all three)
SELECT coverage, COUNT(*) AS n FROM atlas_topic GROUP BY coverage
