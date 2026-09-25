"""Esquema da base de dados SQLite e migrações por versão (PRAGMA user_version).

Cada migração é aplicada uma única vez, por ordem. Para mudar o esquema no futuro, acrescenta-se uma
nova entrada a MIGRATIONS (nunca se altera uma já publicada): assim as bases de dados antigas atualizam-se
sem perder dados.
"""

import sqlite3

SCHEMA_V1 = """
CREATE TABLE player (
    id                 INTEGER PRIMARY KEY CHECK (id = 1),   -- uma só personagem
    name               TEXT    NOT NULL,
    level              INTEGER NOT NULL,
    xp_into_level      INTEGER NOT NULL,
    gold               INTEGER NOT NULL,
    free_points        INTEGER NOT NULL,
    rank_index         INTEGER NOT NULL,
    hp                 INTEGER NOT NULL,
    in_penalty_zone    INTEGER NOT NULL,
    active_title       TEXT,
    xp_scroll_charges  INTEGER NOT NULL,
    created_on         TEXT    NOT NULL,                      -- datas em ISO 8601 (AAAA-MM-DD)
    last_closed_day    TEXT    NOT NULL,
    next_habit_id      INTEGER NOT NULL
);

CREATE TABLE attributes (
    name   TEXT PRIMARY KEY,
    value  REAL NOT NULL
);

CREATE TABLE habits (
    id                INTEGER PRIMARY KEY,
    name              TEXT    NOT NULL,
    habit_type        TEXT    NOT NULL,
    rank              TEXT    NOT NULL,
    target            REAL    NOT NULL,
    periodicity       TEXT    NOT NULL,
    streak_threshold  REAL    NOT NULL,
    streak            INTEGER NOT NULL,
    created_on        TEXT
);

CREATE TABLE habit_weights (
    habit_id   INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
    attribute  TEXT    NOT NULL,
    weight     REAL    NOT NULL,
    PRIMARY KEY (habit_id, attribute)
);

CREATE TABLE habit_tags (
    habit_id  INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
    position  INTEGER NOT NULL,
    tag       TEXT    NOT NULL,
    PRIMARY KEY (habit_id, position)
);

CREATE TABLE logs (
    habit_id        INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
    period_start    TEXT    NOT NULL,
    value           REAL    NOT NULL,
    xp_awarded      INTEGER NOT NULL,
    gold_awarded    INTEGER NOT NULL,
    ratio_rewarded  REAL    NOT NULL,
    boosted         INTEGER NOT NULL,
    final_ratio     REAL,                                     -- NULL enquanto o período está aberto
    PRIMARY KEY (habit_id, period_start)
);

CREATE TABLE skills (
    position          INTEGER PRIMARY KEY,                    -- mantém a ordem de aquisição
    name              TEXT    NOT NULL UNIQUE,
    description       TEXT    NOT NULL,
    trigger_id        TEXT    NOT NULL UNIQUE,
    linked_habit_id   INTEGER REFERENCES habits(id) ON DELETE CASCADE,
    linked_attribute  TEXT,
    level             INTEGER NOT NULL,
    proficiency       REAL    NOT NULL
);

CREATE TABLE awarded_triggers (trigger_id TEXT PRIMARY KEY);

CREATE TABLE inventory (
    item      TEXT PRIMARY KEY,
    quantity  INTEGER NOT NULL CHECK (quantity >= 0)
);

CREATE TABLE stats (
    id                       INTEGER PRIMARY KEY CHECK (id = 1),
    total_completions        INTEGER NOT NULL,
    perfect_day_streak       INTEGER NOT NULL,
    best_perfect_day_streak  INTEGER NOT NULL,
    best_habit_streak        INTEGER NOT NULL,
    penalty_entries          INTEGER NOT NULL,
    penalty_exits            INTEGER NOT NULL
);

CREATE TABLE completions_by_habit (
    habit_id  INTEGER PRIMARY KEY REFERENCES habits(id) ON DELETE CASCADE,
    count     INTEGER NOT NULL
);

CREATE TABLE completions_by_attribute (
    attribute  TEXT PRIMARY KEY,
    count      INTEGER NOT NULL
);

CREATE TABLE minutes_by_tag (
    tag      TEXT PRIMARY KEY,
    minutes  REAL NOT NULL
);

CREATE TABLE achievements (id TEXT PRIMARY KEY);

CREATE TABLE titles (
    position  INTEGER PRIMARY KEY,
    title     TEXT NOT NULL UNIQUE
);

CREATE TABLE penalty_quest (
    id    INTEGER PRIMARY KEY CHECK (id = 1),
    task  TEXT NOT NULL,
    rank  TEXT NOT NULL,
    due   TEXT NOT NULL
);

CREATE TABLE paused_days (day TEXT PRIMARY KEY);

-- Resumo da semana em curso: é temporário (reinicia todos os domingos), por isso fica em JSON.
CREATE TABLE week_state (
    id    INTEGER PRIMARY KEY CHECK (id = 1),
    data  TEXT NOT NULL
);

-- Definições da app (PIN, lembretes, IA...), usadas pelas próximas fases.
CREATE TABLE settings (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);
"""

MIGRATIONS = [SCHEMA_V1]   # MIGRATIONS[i] leva a base de dados da versão i para a i+1
LATEST_VERSION = len(MIGRATIONS)


def migrate(conn: sqlite3.Connection) -> None:
    """Aplica as migrações em falta, cada uma na sua transação."""
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version > LATEST_VERSION:
        raise RuntimeError(f"Database version {version} is newer than this app ({LATEST_VERSION}).")
    for target in range(version, LATEST_VERSION):
        with conn:
            conn.executescript("BEGIN;" + MIGRATIONS[target] + f"PRAGMA user_version = {target + 1};")
