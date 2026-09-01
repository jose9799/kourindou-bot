-- Kourindou Bot schema. Idempotent: safe to run on every startup.
-- All timestamps are Unix epoch integers in UTC.

CREATE TABLE IF NOT EXISTS users (
    user_id        INTEGER NOT NULL,
    guild_id       INTEGER NOT NULL,
    faith_points   INTEGER NOT NULL DEFAULT 0,
    breakcoins     INTEGER NOT NULL DEFAULT 0,
    last_daily     INTEGER,
    daily_streak   INTEGER NOT NULL DEFAULT 0,
    voice_minutes  INTEGER NOT NULL DEFAULT 0,
    last_message   INTEGER,
    created_at     INTEGER NOT NULL,
    PRIMARY KEY (user_id, guild_id)
);

CREATE TABLE IF NOT EXISTS shop_items (
    item_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id     INTEGER NOT NULL,
    name         TEXT    NOT NULL,
    description  TEXT,
    price        INTEGER NOT NULL,
    kind         TEXT    NOT NULL,
    payload      TEXT,
    stock        INTEGER,
    unique_owned INTEGER NOT NULL DEFAULT 1,
    enabled      INTEGER NOT NULL DEFAULT 1,
    UNIQUE (guild_id, name)
);

CREATE TABLE IF NOT EXISTS inventory (
    entry_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    guild_id     INTEGER NOT NULL,
    item_id      INTEGER NOT NULL,
    acquired_at  INTEGER NOT NULL,
    FOREIGN KEY (user_id, guild_id) REFERENCES users (user_id, guild_id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES shop_items (item_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS voice_sessions (
    user_id      INTEGER NOT NULL,
    guild_id     INTEGER NOT NULL,
    channel_id   INTEGER NOT NULL,
    joined_at    INTEGER NOT NULL,
    PRIMARY KEY (user_id, guild_id)
);

CREATE TABLE IF NOT EXISTS quotes (
    quote_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id     INTEGER NOT NULL,
    author_id    INTEGER NOT NULL,
    added_by     INTEGER NOT NULL,
    content      TEXT    NOT NULL,
    message_link TEXT,
    created_at   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS guild_config (
    guild_id     INTEGER NOT NULL,
    key          TEXT    NOT NULL,
    value        TEXT    NOT NULL,
    PRIMARY KEY (guild_id, key)
);

CREATE TABLE IF NOT EXISTS transactions (
    tx_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id     INTEGER NOT NULL,
    user_id      INTEGER NOT NULL,
    delta        INTEGER NOT NULL,
    reason       TEXT    NOT NULL,
    counterparty INTEGER,
    currency     TEXT    NOT NULL DEFAULT 'faith',
    created_at   INTEGER NOT NULL
);

-- Squad calls. Persisted so their buttons keep working after a restart.
CREATE TABLE IF NOT EXISTS squads (
    message_id   INTEGER PRIMARY KEY,
    guild_id     INTEGER NOT NULL,
    channel_id   INTEGER NOT NULL,
    host_id      INTEGER NOT NULL,
    game         TEXT    NOT NULL,
    scheduled_at TEXT,
    created_at   INTEGER NOT NULL,
    closed       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS squad_signups (
    message_id   INTEGER NOT NULL,
    user_id      INTEGER NOT NULL,
    status       TEXT    NOT NULL,
    updated_at   INTEGER NOT NULL,
    PRIMARY KEY (message_id, user_id),
    FOREIGN KEY (message_id) REFERENCES squads (message_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_users_faith ON users (guild_id, faith_points DESC);
CREATE INDEX IF NOT EXISTS idx_inv_user    ON inventory (guild_id, user_id);
CREATE INDEX IF NOT EXISTS idx_tx_user     ON transactions (guild_id, user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_quotes_guild ON quotes (guild_id);
CREATE INDEX IF NOT EXISTS idx_shop_guild  ON shop_items (guild_id, enabled);
