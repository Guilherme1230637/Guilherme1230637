"""Estado da personagem e as ações que o alteram (atributos, XP, HP, Penalty Zone, breakthroughs)."""

import math
from dataclasses import dataclass, field

from . import config, cultivation, leveling
from .habits import Reward


def _starting_attributes() -> dict[str, float]:
    return {attr: config.STARTING_ATTRIBUTE_VALUE for attr in config.ATTRIBUTES}


@dataclass
class Player:
    name: str
    level: int = 1
    xp_into_level: int = 0
    gold: int = 0
    free_points: int = 0
    rank_index: int = 0                    # índice em CULTIVATION_RANKS (0 = Unranked)
    attributes: dict[str, float] = field(default_factory=_starting_attributes)
    hp: int = config.BASE_HP
    in_penalty_zone: bool = False

    # ---------- derivados ----------
    @property
    def max_hp(self) -> int:
        """HP máximo = 100 + 5 × (VIT − 10). Usa a parte inteira do VIT, como a UI mostra."""
        return config.BASE_HP + config.HP_PER_VIT_POINT * (math.floor(self.attributes["VIT"]) - 10)

    @property
    def hunter_rank(self) -> str:
        return leveling.hunter_rank(self.level)

    @property
    def rank(self) -> config.CultivationRank:
        return config.CULTIVATION_RANKS[self.rank_index]

    @property
    def rank_label(self) -> str:
        return cultivation.rank_label(self.rank_index, self.level, self.xp_into_level)

    # ---------- XP, Gold e atributos ----------
    def apply_reward(self, reward: Reward) -> int:
        """Aplica uma recompensa (ou a sua correção negativa). Devolve os níveis ganhos."""
        gained = 0
        if reward.xp >= 0:
            progress = leveling.add_xp(self.level, self.xp_into_level, reward.xp)
            self.level, self.xp_into_level = progress.level, progress.xp_into_level
            self.free_points += progress.free_points_gained
            gained = progress.levels_gained
        else:
            self.xp_into_level = leveling.remove_xp(self.xp_into_level, -reward.xp)
        self.gold = max(0, self.gold + reward.gold)
        for attr, amount in reward.attributes.items():
            self.attributes[attr] = max(config.STARTING_ATTRIBUTE_VALUE, self.attributes[attr] + amount)
        return gained

    def spend_free_point(self, attribute: str, points: int = 1) -> None:
        if attribute not in self.attributes:
            raise ValueError(f"Unknown attribute: {attribute}")
        if not 0 < points <= self.free_points:
            raise ValueError("Not enough free points.")
        self.free_points -= points
        self.attributes[attribute] += points
        # subir VIT aumenta o HP máximo; o HP atual sobe o mesmo para não "perder" a subida
        self.hp = min(self.hp + (config.HP_PER_VIT_POINT * points if attribute == "VIT" else 0), self.max_hp)

    # ---------- HP e Penalty Zone ----------
    def take_damage(self, amount: int) -> bool:
        """Retira HP. Devolve True se isto fez entrar na Penalty Zone."""
        if amount <= 0 or self.in_penalty_zone:
            return False
        self.hp = max(0, self.hp - amount)
        if self.hp == 0:
            self._enter_penalty_zone()
            return True
        return False

    def _enter_penalty_zone(self) -> None:
        self.in_penalty_zone = True
        xp_loss = round(leveling.xp_to_next_level(self.level) * config.PENALTY_XP_LOSS)
        self.xp_into_level = leveling.remove_xp(self.xp_into_level, xp_loss)
        self.gold -= round(self.gold * config.PENALTY_GOLD_LOSS)

    def complete_penalty_quest(self) -> None:
        if not self.in_penalty_zone:
            raise ValueError("Not in the Penalty Zone.")
        self.in_penalty_zone = False
        self.hp = round(self.max_hp * config.PENALTY_QUEST_HP_RESTORE)

    def heal(self, amount: int) -> None:
        if not self.in_penalty_zone:
            self.hp = min(self.max_hp, self.hp + amount)

    # ---------- Ranking ----------
    def breakthrough(self) -> config.CultivationRank:
        result = cultivation.breakthrough(self.rank_index, self.level, self.gold, self.in_penalty_zone)
        self.rank_index, self.gold = result.rank_index, result.gold
        self.free_points += result.bonus_points
        return self.rank
