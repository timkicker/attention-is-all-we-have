-- dropped: the fi scale line as Track A stored it
SELECT k, v FROM stat WHERE k IN ('fi_lives', 'fi_dead', 'fi_dead_1y', 'fi_revisions')
