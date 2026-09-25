"""Guardar e carregar o GameState completo em SQLite.

Estratégia: cada `save` reescreve o estado inteiro dentro de UMA transação. Com poucos milhares de registos
por ano isto demora milissegundos, e garante que a base de dados nunca fica meio escrita: ou grava tudo,
ou (se algo falhar) não grava nada e o estado anterior mantém-se intacto.
"""

import json
import sqlite3
from dataclasses import asdict
from datetime import date, time
from pathlib import Path

from ..engine.achievements import Stats
from ..engine.habits import Habit, HabitType, Periodicity
from ..engine.items import Item
from ..engine.penalty import PenaltyQuest
from ..engine.player import Player
from ..engine.report import WeekAccumulator
from ..engine.skills import Skill
from ..engine.state import GameState, LogEntry
from .schema import migrate

# Ordem de limpeza: primeiro as tabelas que apontam para outras (filhas), depois as "pais"
TABLES_IN_DELETE_ORDER = (
    "logs", "habit_weights", "habit_tags", "skills", "completions_by_habit", "habits",
    "player", "attributes", "awarded_triggers", "inventory", "stats", "completions_by_attribute",
    "minutes_by_tag", "achievements", "titles", "penalty_quest", "paused_days", "week_state",
)


def connect(path: str | Path) -> sqlite3.Connection:
    """Abre (ou cria) a base de dados, liga as chaves estrangeiras e aplica migrações."""
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON")   # no SQLite vêm desligadas por defeito
    migrate(conn)
    return conn


def _d(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _p(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


# ======================= gravar =======================
def save(conn: sqlite3.Connection, state: GameState) -> None:
    with conn:  # transação: commit no fim, rollback automático se houver exceção
        for table in TABLES_IN_DELETE_ORDER:
            conn.execute(f"DELETE FROM {table}")
        _save_player(conn, state)
        _save_habits(conn, state)
        _save_progress(conn, state)


def _save_player(conn, state: GameState) -> None:
    p = state.player
    conn.execute(
        "INSERT INTO player VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (p.name, p.level, p.xp_into_level, p.gold, p.free_points, p.rank_index, p.hp, int(p.in_penalty_zone),
         state.active_title, state.xp_scroll_charges, _d(state.created_on), _d(state.last_closed_day),
         state.next_habit_id),
    )
    conn.executemany("INSERT INTO attributes VALUES (?, ?)", p.attributes.items())


def _save_habits(conn, state: GameState) -> None:
    for h in state.habits.values():
        conn.execute(
            "INSERT INTO habits (id, name, habit_type, rank, target, periodicity, streak_threshold, streak,"
            " created_on, archived, unit, reminder) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (h.id, h.name, h.habit_type.value, h.rank, h.target, h.periodicity.value, h.streak_threshold,
             h.streak, _d(h.created_on), int(h.archived), h.unit,
             h.reminder.strftime("%H:%M") if h.reminder else None),
        )
        conn.executemany("INSERT INTO habit_weights VALUES (?, ?, ?)",
                         [(h.id, a, w) for a, w in h.attribute_weights.items()])
        conn.executemany("INSERT INTO habit_tags VALUES (?, ?, ?)",
                         [(h.id, i, t) for i, t in enumerate(h.tags)])
    conn.executemany(
        "INSERT INTO logs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(hid, _d(start), e.value, e.xp_awarded, e.gold_awarded, e.ratio_rewarded, int(e.boosted), e.final_ratio)
         for (hid, start), e in state.logs.items()],
    )


def _save_progress(conn, state: GameState) -> None:
    conn.executemany(
        "INSERT INTO skills VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(i, s.name, s.description, s.trigger_id, s.linked_habit_id, s.linked_attribute, s.level, s.proficiency)
         for i, s in enumerate(state.skills)],
    )
    conn.executemany("INSERT INTO awarded_triggers VALUES (?)", [(t,) for t in state.awarded_triggers])
    conn.executemany("INSERT INTO inventory VALUES (?, ?)", [(i.name, n) for i, n in state.inventory.items()])
    st = state.stats
    conn.execute("INSERT INTO stats VALUES (1, ?, ?, ?, ?, ?, ?)",
                 (st.total_completions, st.perfect_day_streak, st.best_perfect_day_streak, st.best_habit_streak,
                  st.penalty_entries, st.penalty_exits))
    conn.executemany("INSERT INTO completions_by_habit VALUES (?, ?)", st.completions_by_habit.items())
    conn.executemany("INSERT INTO completions_by_attribute VALUES (?, ?)", st.completions_by_attribute.items())
    conn.executemany("INSERT INTO minutes_by_tag VALUES (?, ?)", st.minutes_by_tag.items())
    conn.executemany("INSERT INTO achievements VALUES (?)", [(a,) for a in state.unlocked_achievements])
    conn.executemany("INSERT INTO titles VALUES (?, ?)", enumerate(state.unlocked_titles))
    if state.penalty_quest:
        q = state.penalty_quest
        conn.execute("INSERT INTO penalty_quest VALUES (1, ?, ?, ?)", (q.task, q.rank, _d(q.due)))
    conn.executemany("INSERT INTO paused_days VALUES (?)", [(_d(d),) for d in state.paused_days])
    week = asdict(state.week)
    week["loot"] = [i.name for i in state.week.loot]
    week["ratios"] = {str(k): v for k, v in state.week.ratios.items()}   # JSON só aceita chaves de texto
    conn.execute("INSERT INTO week_state VALUES (1, ?)", (json.dumps(week),))


# ======================= carregar =======================
def has_game(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT COUNT(*) FROM player").fetchone()[0] == 1


def load(conn: sqlite3.Connection) -> GameState:
    row = conn.execute("SELECT * FROM player WHERE id = 1").fetchone()
    if row is None:
        raise LookupError("No saved game.")
    (_, name, level, xp, gold, free_points, rank_index, hp, in_pz, active_title, scroll_charges,
     created_on, last_closed_day, next_habit_id) = row
    player = Player(name, level, xp, gold, free_points, rank_index,
                    dict(conn.execute("SELECT name, value FROM attributes")), hp, bool(in_pz))
    week = json.loads(conn.execute("SELECT data FROM week_state").fetchone()[0])
    week["loot"] = [Item[n] for n in week["loot"]]
    week["ratios"] = {int(k): v for k, v in week["ratios"].items()}
    quest = conn.execute("SELECT task, rank, due FROM penalty_quest").fetchone()
    return GameState(
        player=player,
        created_on=_p(created_on),
        habits=_load_habits(conn),
        logs={(hid, _p(start)): LogEntry(v, xa, ga, rr, bool(b), fr)
              for hid, start, v, xa, ga, rr, b, fr in conn.execute("SELECT * FROM logs")},
        skills=[Skill(n, d, t, lh, la, lv, pr) for _, n, d, t, lh, la, lv, pr
                in conn.execute("SELECT * FROM skills ORDER BY position")],
        awarded_triggers={t for (t,) in conn.execute("SELECT trigger_id FROM awarded_triggers")},
        inventory={Item[i]: n for i, n in conn.execute("SELECT item, quantity FROM inventory")},
        xp_scroll_charges=scroll_charges,
        stats=_load_stats(conn),
        unlocked_achievements={a for (a,) in conn.execute("SELECT id FROM achievements")},
        unlocked_titles=[t for (t,) in conn.execute("SELECT title FROM titles ORDER BY position")],
        active_title=active_title,
        penalty_quest=PenaltyQuest(quest[0], quest[1], _p(quest[2])) if quest else None,
        paused_days={_p(d) for (d,) in conn.execute("SELECT day FROM paused_days")},
        last_closed_day=_p(last_closed_day),
        week=WeekAccumulator(**week),
        next_habit_id=next_habit_id,
    )


def _load_habits(conn) -> dict[int, Habit]:
    weights: dict[int, dict[str, float]] = {}
    for hid, attr, w in conn.execute("SELECT habit_id, attribute, weight FROM habit_weights"):
        weights.setdefault(hid, {})[attr] = w
    tags: dict[int, list[str]] = {}
    for hid, tag in conn.execute("SELECT habit_id, tag FROM habit_tags ORDER BY habit_id, position"):
        tags.setdefault(hid, []).append(tag)
    habits = {}
    for hid, name, htype, rank, target, period, threshold, streak, created, archived, unit, reminder in \
            conn.execute("SELECT id, name, habit_type, rank, target, periodicity, streak_threshold, streak,"
                         " created_on, archived, unit, reminder FROM habits ORDER BY id"):
        habits[hid] = Habit(name, HabitType(htype), rank, weights[hid], target, Periodicity(period),
                            threshold, streak, tags.get(hid, []), hid, _p(created), bool(archived), unit,
                            time.fromisoformat(reminder) if reminder else None)
    return habits


def _load_stats(conn) -> Stats:
    _, total, pds, best_pds, best_streak, entries, exits = conn.execute("SELECT * FROM stats").fetchone()
    return Stats(
        total_completions=total,
        completions_by_habit=dict(conn.execute("SELECT habit_id, count FROM completions_by_habit")),
        completions_by_attribute=dict(conn.execute("SELECT attribute, count FROM completions_by_attribute")),
        minutes_by_tag=dict(conn.execute("SELECT tag, minutes FROM minutes_by_tag")),
        perfect_day_streak=pds,
        best_perfect_day_streak=best_pds,
        best_habit_streak=best_streak,
        penalty_entries=entries,
        penalty_exits=exits,
    )


# ======================= definições =======================
def get_setting(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row[0] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    with conn:
        conn.execute("INSERT INTO settings VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                     (key, value))
