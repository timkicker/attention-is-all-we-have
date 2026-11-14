-- Parallax schema v1, MariaDB 12.3.3. Change only through a contract commit on main.
CREATE TABLE topic (
  topic_id    VARCHAR(32)  NOT NULL PRIMARY KEY,          -- 'winterwar'; S atlas topics use the Wikidata id
  wikidata_id VARCHAR(16)  NOT NULL UNIQUE,
  label_en    VARCHAR(255) NOT NULL,
  depth       ENUM('deep','atlas') NOT NULL
);

CREATE TABLE page (
  lang     VARCHAR(8)   NOT NULL,
  page_id  INT UNSIGNED NOT NULL,
  topic_id VARCHAR(32)  NULL,
  title    VARCHAR(255) NOT NULL,
  source   ENUM('api','M','S') NOT NULL,
  history  ENUM('every','yearly','none') NOT NULL,
  PRIMARY KEY (lang, page_id), KEY (topic_id)
);

CREATE TABLE revision (                                   -- metadata only, never a user name
  lang      VARCHAR(8)      NOT NULL,
  rev_id    BIGINT UNSIGNED NOT NULL,
  page_id   INT UNSIGNED    NOT NULL,
  parent_id BIGINT UNSIGNED NULL,
  ts        DATETIME(6)     NOT NULL,
  bytes     INT UNSIGNED    NULL,
  minor     TINYINT(1)      NOT NULL DEFAULT 0,
  comment   VARCHAR(1000)   NULL,
  snapshot  TINYINT(1)      NOT NULL DEFAULT 0,             -- 1 if its text was parsed
  PRIMARY KEY (lang, rev_id), KEY (lang, page_id, ts)
);

CREATE TABLE section_text (
  topic_id VARCHAR(32) NOT NULL, lang VARCHAR(8) NOT NULL, section VARCHAR(255) NOT NULL,
  rev_id BIGINT UNSIGNED NOT NULL, n_sent INT UNSIGNED NOT NULL, text MEDIUMTEXT NOT NULL,
  row_start TIMESTAMP(6) GENERATED ALWAYS AS ROW START INVISIBLE,
  row_end   TIMESTAMP(6) GENERATED ALWAYS AS ROW END INVISIBLE,
  PERIOD FOR SYSTEM_TIME (row_start, row_end),
  PRIMARY KEY (topic_id, lang, section), KEY (topic_id, lang, row_start)
) WITH SYSTEM VERSIONING;

CREATE TABLE claim (                                      -- one row per sentence life, with a vector
  lang VARCHAR(8) NOT NULL, page_id INT UNSIGNED NOT NULL, h CHAR(16) NOT NULL,
  topic_id VARCHAR(32) NULL,
  section VARCHAR(255) NOT NULL, text TEXT NOT NULL,
  born_rev BIGINT UNSIGNED NOT NULL,
  died_rev BIGINT UNSIGNED NULL, died_comment VARCHAR(1000) NULL,
  time_precision ENUM('exact','snapshot') NOT NULL,      -- snapshot: bounds are yearly snapshot times
  has_ref TINYINT(1) NOT NULL DEFAULT 0, had_ref TINYINT(1) NOT NULL DEFAULT 0,
  emb VECTOR(1024) NOT NULL,
  row_start TIMESTAMP(6) GENERATED ALWAYS AS ROW START INVISIBLE,
  row_end   TIMESTAMP(6) GENERATED ALWAYS AS ROW END INVISIBLE,
  PERIOD FOR SYSTEM_TIME (row_start, row_end),
  PRIMARY KEY (lang, page_id, h),
  KEY (topic_id, lang, row_start), KEY (lang, row_start),
  VECTOR INDEX (emb) M=16 DISTANCE=cosine
) WITH SYSTEM VERSIONING;

CREATE TABLE claim_life_fi (                              -- all M lives, no vectors
  page_id INT UNSIGNED NOT NULL, h CHAR(16) NOT NULL, text TEXT NOT NULL,
  born_rev BIGINT UNSIGNED NOT NULL, died_rev BIGINT UNSIGNED NULL, died_comment VARCHAR(1000) NULL,
  reason ENUM('none','unsourced','error','speculation','other') NOT NULL DEFAULT 'none',
  has_ref TINYINT(1) NOT NULL DEFAULT 0, had_ref TINYINT(1) NOT NULL DEFAULT 0,
  row_start TIMESTAMP(6) GENERATED ALWAYS AS ROW START INVISIBLE,
  row_end   TIMESTAMP(6) GENERATED ALWAYS AS ROW END INVISIBLE,
  PERIOD FOR SYSTEM_TIME (row_start, row_end),
  PRIMARY KEY (page_id, h), KEY (page_id, row_start), KEY (reason)
) WITH SYSTEM VERSIONING;

CREATE TABLE article_vec (                                -- S article vectors as shipped
  lang VARCHAR(8) NOT NULL, page_id INT UNSIGNED NOT NULL, wikidata_id VARCHAR(16) NOT NULL,
  title VARCHAR(255) NOT NULL, truncated TINYINT(1) NOT NULL, emb VECTOR(1024) NOT NULL,
  PRIMARY KEY (lang, page_id), KEY (wikidata_id),
  VECTOR INDEX (emb) M=16 DISTANCE=cosine
);

CREATE TABLE atlas_topic (
  wikidata_id VARCHAR(16) NOT NULL PRIMARY KEY,
  title_fi VARCHAR(255) NULL, title_sv VARCHAR(255) NULL, title_en VARCHAR(255) NULL,
  coverage ENUM('fi','fi+sv','fi+en','all') NOT NULL,
  dist_fi_sv FLOAT NULL, dist_fi_en FLOAT NULL, dist_sv_en FLOAT NULL,
  topic_id VARCHAR(32) NULL,                              -- set when deep data exists
  KEY (coverage)
);

CREATE TABLE align (                                      -- cached nearest candidates per anchor date
  as_of DATE NOT NULL,
  src_lang VARCHAR(8) NOT NULL, src_page INT UNSIGNED NOT NULL, src_h CHAR(16) NOT NULL,
  dst_lang VARCHAR(8) NOT NULL, rank TINYINT UNSIGNED NOT NULL,
  dst_page INT UNSIGNED NOT NULL, dst_h CHAR(16) NOT NULL,
  dist FLOAT NOT NULL, method ENUM('exact','ann') NOT NULL,
  PRIMARY KEY (as_of, src_lang, src_page, src_h, dst_lang, rank), KEY (dst_lang, dst_h)
);

CREATE TABLE verdict (
  a_lang VARCHAR(8) NOT NULL, a_h CHAR(16) NOT NULL, b_lang VARCHAR(8) NOT NULL, b_h CHAR(16) NOT NULL,
  prompt_version VARCHAR(16) NOT NULL,
  label ENUM('same','partial','contradicts','different') NOT NULL,
  numbers JSON NULL, terms JSON NULL,                     -- [["26 662","25 904"]], [["lavasti","reported"]]
  model VARCHAR(80) NOT NULL, raw JSON NULL, judged_at DATETIME(6) NOT NULL,
  PRIMARY KEY (a_lang, a_h, b_lang, b_h, prompt_version)
);

CREATE TABLE gloss (
  lang VARCHAR(8) NOT NULL, h CHAR(16) NOT NULL, text_en TEXT NOT NULL, model VARCHAR(80) NOT NULL,
  PRIMARY KEY (lang, h)
);

CREATE TABLE term (
  term_id VARCHAR(32) NOT NULL, lang VARCHAR(8) NOT NULL, pattern VARCHAR(255) NOT NULL,
  concept VARCHAR(64) NOT NULL, gloss_en VARCHAR(255) NOT NULL,
  PRIMARY KEY (term_id, lang)
);

CREATE TABLE term_hit (
  topic_id VARCHAR(32) NOT NULL, lang VARCHAR(8) NOT NULL, term_id VARCHAR(32) NOT NULL, h CHAR(16) NOT NULL,
  row_start TIMESTAMP(6) GENERATED ALWAYS AS ROW START INVISIBLE,
  row_end   TIMESTAMP(6) GENERATED ALWAYS AS ROW END INVISIBLE,
  PERIOD FOR SYSTEM_TIME (row_start, row_end),
  PRIMARY KEY (topic_id, lang, term_id, h)
) WITH SYSTEM VERSIONING;

CREATE TABLE ref_stat (
  topic_id VARCHAR(32) NOT NULL, lang VARCHAR(8) NOT NULL, rev_id BIGINT UNSIGNED NOT NULL,
  refs INT UNSIGNED NOT NULL, isbn JSON NOT NULL, domains JSON NOT NULL,
  row_start TIMESTAMP(6) GENERATED ALWAYS AS ROW START INVISIBLE,
  row_end   TIMESTAMP(6) GENERATED ALWAYS AS ROW END INVISIBLE,
  PERIOD FOR SYSTEM_TIME (row_start, row_end),
  PRIMARY KEY (topic_id, lang)
) WITH SYSTEM VERSIONING;

CREATE TABLE check_run (
  run_id CHAR(12) NOT NULL PRIMARY KEY, created_at DATETIME(6) NOT NULL,
  input_text MEDIUMTEXT NOT NULL, source ENUM('recorded','live') NOT NULL,
  answer_model VARCHAR(80) NULL, answer_date DATE NULL, question TEXT NULL,
  as_of DATETIME NULL, engine ENUM('fake','real') NOT NULL
);

CREATE TABLE check_claim (
  run_id CHAR(12) NOT NULL, idx SMALLINT UNSIGNED NOT NULL, text TEXT NOT NULL,
  emb VECTOR(1024) NULL, labels JSON NOT NULL,
  PRIMARY KEY (run_id, idx)
);

CREATE TABLE gold_pair (
  a_lang VARCHAR(8) NOT NULL, a_h CHAR(16) NOT NULL, b_lang VARCHAR(8) NOT NULL, b_h CHAR(16) NOT NULL,
  label ENUM('same','partial','contradicts','different') NOT NULL,
  labeller VARCHAR(16) NOT NULL, note VARCHAR(255) NULL,
  PRIMARY KEY (a_lang, a_h, b_lang, b_h)
);

CREATE TABLE stat (                                       -- numbers for the scale line and the docs
  k VARCHAR(64) NOT NULL PRIMARY KEY, v JSON NOT NULL, computed_at DATETIME(6) NOT NULL
);
