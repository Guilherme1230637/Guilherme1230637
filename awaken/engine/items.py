"""Loot e inventário (secção 6.2)."""

import random
from enum import Enum

from . import config


class Item(Enum):
    HP_POTION = "HP Potion"          # +30 HP
    STREAK_SHIELD = "Streak Shield"  # protege a streak de um hábito numa falha (usado automaticamente)
    XP_SCROLL = "XP Scroll"          # ×2 XP nas próximas 3 quests
    GOLD_POUCH = "Gold Pouch"        # +50 a 200 Gold ao abrir


# Probabilidade relativa de cada item quando há drop (soma 1)
ITEM_WEIGHTS = {
    Item.HP_POTION: 0.40,
    Item.XP_SCROLL: 0.25,
    Item.STREAK_SHIELD: 0.20,
    Item.GOLD_POUCH: 0.15,
}

HP_POTION_HEAL = 30
XP_SCROLL_CHARGES = 3
GOLD_POUCH_RANGE = (50, 200)


def roll_loot(habit_rank: str, rng: random.Random) -> Item | None:
    """Dois sorteios: primeiro se há drop (probabilidade do rank), depois qual o item (pesos)."""
    if rng.random() >= config.HABIT_RANKS[habit_rank].loot_chance:
        return None
    return rng.choices(list(ITEM_WEIGHTS), weights=list(ITEM_WEIGHTS.values()))[0]


def gold_pouch_amount(rng: random.Random) -> int:
    return rng.randint(*GOLD_POUCH_RANGE)
