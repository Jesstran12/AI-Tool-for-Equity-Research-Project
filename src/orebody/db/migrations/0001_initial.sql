-- F0.3 initial schema (SPEC §5.6, claims per §4.3). Applied once by orebody.db.migrate.
-- Lists and dicts are stored as JSON text. Dates are ISO 'YYYY-MM-DD'; timestamps ISO 8601 UTC.

CREATE TABLE companies (
    ticker            TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    exchange          TEXT NOT NULL DEFAULT '',
    cik               TEXT NOT NULL DEFAULT '',
    flagship_project  TEXT NOT NULL DEFAULT '',
    primary_commodity TEXT NOT NULL DEFAULT '',
    by_products       TEXT NOT NULL DEFAULT '[]',          -- JSON list
    reporting_currency TEXT NOT NULL DEFAULT 'USD'
);

CREATE TABLE documents (
    doc_id         TEXT PRIMARY KEY,                      -- = sha256 prefix used by ingest/extract
    ticker         TEXT NOT NULL REFERENCES companies(ticker),
    type           TEXT NOT NULL CHECK (type IN ('technical_report', 'annual_financials',
                       'quarterly_financials', 'mdna', 'aif', 'news_release', 'presentation')),
    standard       TEXT NOT NULL DEFAULT 'none' CHECK (standard IN ('NI43-101', 'SK1300', 'JORC', 'none')),
    effective_date TEXT,
    filing_date    TEXT NOT NULL,
    path           TEXT NOT NULL,
    url            TEXT NOT NULL DEFAULT '',
    sha256         TEXT NOT NULL CHECK (length(sha256) = 64),
    pages          INTEGER CHECK (pages IS NULL OR pages > 0),
    UNIQUE (ticker, sha256)
);

CREATE TABLE runs (                                       -- §5.5 reproducibility record
    run_id          TEXT PRIMARY KEY,
    ticker          TEXT NOT NULL REFERENCES companies(ticker),
    as_of           TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    git_sha         TEXT NOT NULL DEFAULT '',
    models          TEXT NOT NULL DEFAULT '{}',           -- JSON {agent: {model, effort}}
    prompt_versions TEXT NOT NULL DEFAULT '{}',           -- JSON {prompt: version}
    document_ids    TEXT NOT NULL DEFAULT '[]',           -- JSON list of doc_id used
    excluded_docs   TEXT NOT NULL DEFAULT '[]',           -- JSON list, filed after as-of (D15)
    price_deck      TEXT NOT NULL DEFAULT '{}',           -- JSON {spot, deck_a, deck_b, source, timestamp}
    fx              TEXT NOT NULL DEFAULT '{}',
    cost_usd        REAL NOT NULL DEFAULT 0 CHECK (cost_usd >= 0),
    wall_seconds    REAL,
    status          TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'done', 'failed'))
);

CREATE TABLE notes (
    note_id           TEXT PRIMARY KEY,
    run_id            TEXT NOT NULL REFERENCES runs(run_id),
    ticker            TEXT NOT NULL REFERENCES companies(ticker),
    author            TEXT NOT NULL DEFAULT 'agent' CHECK (author IN ('agent', 'human')),  -- D44
    stance            TEXT CHECK (stance IS NULL OR stance IN ('Favourable', 'Neutral', 'Unfavourable')),
    markdown          TEXT NOT NULL DEFAULT '',
    verification_rate REAL CHECK (verification_rate IS NULL OR verification_rate BETWEEN 0 AND 1),
    created_at        TEXT NOT NULL
);

CREATE TABLE overrides (                                  -- Phase L1; table exists so claims can reference it
    override_id TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    author      TEXT NOT NULL,
    reason      TEXT NOT NULL CHECK (length(reason) > 0)
);

CREATE TABLE claims (                                     -- §4.3, field for field
    claim_id       TEXT PRIMARY KEY,
    note_id        TEXT NOT NULL REFERENCES notes(note_id),
    section        INTEGER NOT NULL CHECK (section BETWEEN 1 AND 5),
    field          TEXT NOT NULL,
    claim_type     TEXT NOT NULL CHECK (claim_type IN ('number', 'entity', 'date', 'synthesis')),
    value_norm     TEXT,
    unit_norm      TEXT,
    value_orig     TEXT,
    unit_orig      TEXT,
    currency_orig  TEXT,
    fx_rate_used   REAL,
    doc_id         TEXT REFERENCES documents(doc_id),
    page           INTEGER CHECK (page IS NULL OR page >= 1),
    quote          TEXT CHECK (quote IS NULL OR length(quote) <= 300),
    tier1_status   TEXT NOT NULL DEFAULT 'na' CHECK (tier1_status IN ('pass', 'fail', 'na')),
    tier2_status   TEXT NOT NULL DEFAULT 'skipped' CHECK (tier2_status IN ('pass', 'fail', 'skipped')),
    final_status   TEXT NOT NULL CHECK (final_status IN ('verified', 'unverified', 'synthesis')),
    revision_round INTEGER NOT NULL DEFAULT 0 CHECK (revision_round >= 0),
    override_id    TEXT REFERENCES overrides(override_id),
    -- ground rule 3: no number without a source. Only synthesis may lack a document and page.
    CHECK (claim_type = 'synthesis' OR (doc_id IS NOT NULL AND page IS NOT NULL)),
    -- §4.4: synthesis claims carry the synthesis status and nothing else does
    CHECK ((claim_type = 'synthesis') = (final_status = 'synthesis'))
);
CREATE INDEX claims_by_note ON claims(note_id);

CREATE TABLE judge_scores (
    judge_id    TEXT PRIMARY KEY,
    note_id     TEXT NOT NULL REFERENCES notes(note_id),
    judge_model TEXT NOT NULL,
    rubric_item TEXT NOT NULL,
    score       REAL NOT NULL,
    rationale   TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE TABLE prices (                                     -- as-of cache (§6.3)
    commodity TEXT NOT NULL,
    as_of     TEXT NOT NULL,
    value     REAL NOT NULL CHECK (value > 0),
    unit      TEXT NOT NULL CHECK (unit IN ('USD/lb', 'USD/t')),
    source    TEXT NOT NULL CHECK (length(source) > 0),
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (commodity, as_of, source)
);
