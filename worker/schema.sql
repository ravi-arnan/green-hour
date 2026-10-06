-- Green Hour journal schema (Cloudflare D1).
--
-- One row per voice note or text log. `outdoors` drives the streak, so it is
-- an INTEGER (0/1) rather than a boolean; `local_date` is precomputed in the
-- user's timezone so streak arithmetic never has to reason about offsets.

CREATE TABLE IF NOT EXISTS entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,
    local_date  TEXT NOT NULL,
    outdoors    INTEGER NOT NULL,
    summary     TEXT NOT NULL,
    location    TEXT,
    weather     TEXT,
    mood        TEXT,
    notable     TEXT NOT NULL DEFAULT '[]',
    species     TEXT NOT NULL DEFAULT '[]',
    transcript  TEXT,
    source      TEXT NOT NULL DEFAULT 'voice',
    model       TEXT
);

CREATE INDEX IF NOT EXISTS idx_entries_local_date ON entries(local_date);
CREATE INDEX IF NOT EXISTS idx_entries_outdoors ON entries(outdoors, local_date);
