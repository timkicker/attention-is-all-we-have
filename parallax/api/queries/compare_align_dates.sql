-- compare: is there a cached alignment for this date and anchor edition
SELECT COUNT(*) AS n FROM align WHERE as_of = %(day)s AND src_lang = %(anchor)s
