# Zombie Facts

**Replaced on Saturday 14 November** by the cross-language plan [PROJECT_BLUEPRINT-parallax.md](../PROJECT_BLUEPRINT-parallax.md). Zombie Facts continues there as one view across languages.

Zombie Facts checks an AI answer against what Finnish Wikipedia stopped saying. It keeps the life of every sentence in MariaDB's dataset M as a row in a system versioned table, with Wikipedia's own times as the row's period, so a sentence that left an article becomes a history row. A demo set of those rows also carries a bge-m3 vector. A language model splits the answer into short claims, MariaDB finds the nearest living and dead sentences in one table and a second model call judges each pair. Every claim then reads "Wikipedia says this", "stopped saying this", "contradicts this" or "never said this". A dead match shows the date, the editor's comment and the old version.

The full plan with the reasoning behind each part is in [PROJECT_BLUEPRINT-zombie-facts.md](../PROJECT_BLUEPRINT-zombie-facts.md).

This folder will hold the loaders for the sentence lives and the vectors, the check service with its API, the web page and `make demo-check`. Data, vectors and recorded answers stay local and never go into git.
