"""Skills: quando aparecem, como se chamam e como sobem de nível (secção 5).

O motor de regras decide QUANDO e QUE TIPO de Skill aparece. O texto (nome e descrição) vem de um
`SkillNamer`: por defeito o de tabelas, que funciona offline; a IA pode ser ligada depois sem mexer aqui.
"""

import random
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

SKILL_MAX_LEVEL = 10
SKILL_XP_BONUS_PER_LEVEL = 0.02

HABIT_COMPLETION_THRESHOLDS = (10, 30, 100)
ATTRIBUTE_COMPLETION_THRESHOLDS = (25, 50, 100, 250)
STREAK_THRESHOLDS = (7, 21, 66)


class TriggerKind(Enum):
    HABIT = "habit"          # nº de vezes que completaste UM hábito
    ATTRIBUTE = "attribute"  # nº total de missões cujo atributo principal é X
    STREAK = "streak"        # streak de um hábito


@dataclass(frozen=True)
class SkillTrigger:
    kind: TriggerKind
    key: str             # id do hábito (HABIT/STREAK) ou sigla do atributo (ATTRIBUTE)
    threshold: int
    attribute: str       # atributo que dá o "sabor" ao nome
    habit_name: str = ""

    @property
    def trigger_id(self) -> str:
        """Identificador único: garante que cada gatilho só gera uma Skill."""
        return f"{self.kind.value}:{self.key}:{self.threshold}"


@dataclass
class Skill:
    name: str
    description: str
    trigger_id: str
    linked_habit_id: int | None     # Skills de hábito/streak
    linked_attribute: str | None    # Skills de atributo: valem para todos os hábitos desse atributo
    level: int = 1
    proficiency: float = 0.0

    @property
    def xp_bonus(self) -> float:
        return SKILL_XP_BONUS_PER_LEVEL * self.level

    def applies_to(self, habit_id: int, dominant_attribute: str) -> bool:
        return self.linked_habit_id == habit_id or self.linked_attribute == dominant_attribute

    def gain_proficiency(self, amount: float) -> int:
        """Proficiência para o nível seguinte = 10 × nível. Devolve os níveis ganhos."""
        if self.level >= SKILL_MAX_LEVEL:
            return 0
        self.proficiency += amount
        gained = 0
        while self.level < SKILL_MAX_LEVEL and self.proficiency >= 10 * self.level:
            self.proficiency -= 10 * self.level
            self.level += 1
            gained += 1
        if self.level == SKILL_MAX_LEVEL:
            self.proficiency = 0.0
        return gained


def pending_triggers(
    completions_by_habit: dict[int, int],
    completions_by_attribute: dict[str, int],
    streaks: dict[int, int],
    habit_info: dict[int, tuple[str, str]],   # id → (nome, atributo principal)
    awarded: set[str],
) -> list[SkillTrigger]:
    """Todos os gatilhos atingidos que ainda não geraram Skill."""
    found: list[SkillTrigger] = []
    for habit_id, count in completions_by_habit.items():
        name, attr = habit_info[habit_id]
        found += [SkillTrigger(TriggerKind.HABIT, str(habit_id), t, attr, name)
                  for t in HABIT_COMPLETION_THRESHOLDS if count >= t]
    for attr, count in completions_by_attribute.items():
        found += [SkillTrigger(TriggerKind.ATTRIBUTE, attr, t, attr)
                  for t in ATTRIBUTE_COMPLETION_THRESHOLDS if count >= t]
    for habit_id, streak in streaks.items():
        name, attr = habit_info[habit_id]
        found += [SkillTrigger(TriggerKind.STREAK, str(habit_id), t, attr, name)
                  for t in STREAK_THRESHOLDS if streak >= t]
    return [t for t in found if t.trigger_id not in awarded]


# ---------------- nomes ----------------
class SkillNamer(Protocol):
    def name(self, trigger: SkillTrigger, taken: set[str]) -> tuple[str, str]:
        """Devolve (nome, descrição). `taken` são os nomes já usados."""


NAME_TABLES = {
    "STR": (("Iron", "Titan's", "Crushing", "Mountain"), ("Body", "Fist", "Might", "Grip")),
    "AGI": (("Swift", "Phantom", "Wind", "Shadow"), ("Step", "Dash", "Reflex", "Stride")),
    "VIT": (("Undying", "Verdant", "Blood", "Life"), ("Vigor", "Heart", "Regeneration", "Pulse")),
    "END": (("Enduring", "Stone", "Tireless", "Bastion"), ("Stamina", "Frame", "March", "Guard")),
    "INT": (("Arcane", "Sage's", "Crystal", "Deep"), ("Mind", "Focus", "Insight", "Intellect")),
    "PER": (("Hawk", "Keen", "Clear", "Third"), ("Eye", "Sense", "Awareness", "Sight")),
    "CHA": (("Silver", "Royal", "Radiant", "Commanding"), ("Tongue", "Presence", "Aura", "Voice")),
    "WIS": (("Ancient", "Serene", "Hermit's", "Dao"), ("Wisdom", "Scroll", "Heart", "Path")),
    "TEN": (("Unbreakable", "Indomitable", "Burning", "Relentless"), ("Will", "Spirit", "Resolve", "Soul")),
}
ROMAN = ("", " II", " III", " IV", " V", " VI", " VII", " VIII", " IX", " X")


class TableSkillNamer:
    """Nomes compostos por prefixo + núcleo do atributo (ex.: 'Iron' + 'Body'). Funciona sem internet."""

    def __init__(self, rng: random.Random):
        self.rng = rng

    def name(self, trigger: SkillTrigger, taken: set[str]) -> tuple[str, str]:
        prefixes, cores = NAME_TABLES[trigger.attribute]
        combos = [f"{p} {c}" for p in prefixes for c in cores]
        self.rng.shuffle(combos)
        for suffix in ROMAN:                       # se todas as combinações estiverem usadas: "Iron Body II"
            for base in combos:
                if base + suffix not in taken:
                    return base + suffix, describe(trigger)
        raise RuntimeError("No skill names left")  # 16 combinações × 10 sufixos por atributo


def describe(trigger: SkillTrigger) -> str:
    bonus = f"+{SKILL_XP_BONUS_PER_LEVEL:.0%} XP per level"
    if trigger.kind == TriggerKind.HABIT:
        return f"Forged by completing '{trigger.habit_name}' {trigger.threshold} times. {bonus} on that quest."
    if trigger.kind == TriggerKind.STREAK:
        return f"Born from a {trigger.threshold}-day streak of '{trigger.habit_name}'. {bonus} on that quest."
    return f"Earned through {trigger.threshold} {trigger.attribute} quests. {bonus} on all {trigger.attribute} quests."


def create_skill(trigger: SkillTrigger, namer: SkillNamer, taken: set[str]) -> Skill:
    name, description = namer.name(trigger, taken)
    by_habit = trigger.kind in (TriggerKind.HABIT, TriggerKind.STREAK)
    return Skill(
        name=name,
        description=description,
        trigger_id=trigger.trigger_id,
        linked_habit_id=int(trigger.key) if by_habit else None,
        linked_attribute=None if by_habit else trigger.key,
    )


def skills_bonus_for(skills: list[Skill], habit_id: int, dominant_attribute: str) -> float:
    """Soma dos bónus das Skills que se aplicam ao hábito (o teto de +50 % é aplicado em xp_multiplier)."""
    return sum(s.xp_bonus for s in skills if s.applies_to(habit_id, dominant_attribute))
