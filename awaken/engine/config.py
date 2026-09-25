"""Todos os números que equilibram o jogo, num só sítio.

Os valores vêm da especificação (docs/ESPECIFICACAO.md) e foram calibrados com
tools/simular_progressao.py. Qualquer ajuste de equilíbrio faz-se aqui e em mais lado nenhum.
"""

from dataclasses import dataclass

# --- Atributos (secção 3.2) ---
ATTRIBUTES = ("STR", "AGI", "VIT", "END", "INT", "PER", "CHA", "WIS", "TEN")
STARTING_ATTRIBUTE_VALUE = 10.0

# --- Curva de XP (secção 3.4): XP para passar do nível n para n+1 = BASE + COEF * n^EXP ---
XP_CURVE_BASE = 100
XP_CURVE_COEF = 2
XP_CURVE_EXP = 1.5

FREE_POINTS_PER_LEVEL = 3


# --- Rank de dificuldade dos hábitos (secção 2.4) ---
@dataclass(frozen=True)
class HabitRankValues:
    xp: int              # XP base ao cumprir 100 %
    gold: int            # Gold base ao cumprir 100 %
    hp_penalty: int      # HP perdido ao falhar 100 %
    stat_points: float   # pontos de atributo distribuídos pelos pesos do hábito
    loot_chance: float   # probabilidade de drop por conclusão


HABIT_RANKS = {
    "E": HabitRankValues(xp=10, gold=5, hp_penalty=5, stat_points=0.2, loot_chance=0.03),
    "D": HabitRankValues(xp=20, gold=10, hp_penalty=8, stat_points=0.4, loot_chance=0.05),
    "C": HabitRankValues(xp=35, gold=18, hp_penalty=12, stat_points=0.6, loot_chance=0.08),
    "B": HabitRankValues(xp=55, gold=28, hp_penalty=16, stat_points=0.8, loot_chance=0.12),
    "A": HabitRankValues(xp=80, gold=40, hp_penalty=22, stat_points=1.0, loot_chance=0.17),
    "S": HabitRankValues(xp=120, gold=60, hp_penalty=30, stat_points=1.5, loot_chance=0.25),
}

# --- Multiplicadores de XP (secções 2.6 e 5.4) ---
STREAK_BONUS_PER_DAY = 0.01
STREAK_BONUS_MAX = 0.30
SKILLS_BONUS_MAX = 0.50
XP_SCROLL_MULTIPLIER = 2.0

# --- HP e Penalty Zone (secções 3.5 e 4) ---
BASE_HP = 100
HP_PER_VIT_POINT = 5
PERFECT_DAY_HP_REGEN = 10
PENALTY_XP_LOSS = 0.10          # fração do XP necessário para o nível atual
PENALTY_GOLD_LOSS = 0.20        # fração do Gold atual
PENALTY_QUEST_HP_RESTORE = 0.50  # fração do HP máximo devolvida ao cumprir a Penalty Quest

# --- Hunter Rank por nível (secção 3.6): (nível mínimo, nome) ---
HUNTER_RANKS = (
    (1, "E"),
    (10, "D"),
    (20, "C"),
    (35, "B"),
    (50, "A"),
    (70, "S"),
    (100, "National Level"),
)


# --- Ranking de cultivação (secção 3.7) ---
@dataclass(frozen=True)
class CultivationRank:
    name: str
    min_level: int
    gold_cost: int
    divisions: int        # 5 estrelas, 10 estágios, ou 0 (Unranked)
    bonus_points: int     # pontos livres extra no breakthrough
    xp_bonus: float       # bónus de XP global enquanto estiveres neste ranking


STARS = 5
STAGES = 10
RANK_LEVEL_SPAN = 15  # níveis entre rankings; usado também para o "fim" do último ranking

CULTIVATION_RANKS = (
    CultivationRank("Unranked", 1, 0, 0, 0, 0.00),
    CultivationRank("Bronze", 10, 500, STARS, 5, 0.02),
    CultivationRank("Silver", 25, 1_500, STARS, 10, 0.04),
    CultivationRank("Gold", 40, 2_500, STARS, 15, 0.06),
    CultivationRank("Dark Gold", 55, 4_000, STARS, 20, 0.08),
    CultivationRank("Legend", 70, 5_500, STARS, 25, 0.10),
    CultivationRank("Heavenly Fate", 85, 7_000, STAGES, 30, 0.12),
    CultivationRank("Heavenly Star", 100, 9_000, STAGES, 35, 0.14),
    CultivationRank("Heavenly Axis", 115, 10_500, STAGES, 40, 0.16),
    CultivationRank("Dao of Dragon", 130, 12_000, STAGES, 45, 0.18),
    CultivationRank("Martial Ancestor", 145, 13_500, STAGES, 50, 0.20),
    CultivationRank("Deity", 160, 14_500, STAGES, 55, 0.22),
    CultivationRank("Emperor", 175, 16_500, STAGES, 60, 0.24),
    CultivationRank("Supreme", 190, 18_500, STAGES, 65, 0.26),
)
