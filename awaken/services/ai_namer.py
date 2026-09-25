"""Nomes de Skills gerados por IA (opcional, secção 5.2).

O motor de regras decide QUANDO e QUE TIPO de Skill aparece; esta peça só escreve o nome e a descrição.
Qualquer falha — sem SDK instalado, sem chave, sem internet, recusa, JSON inválido, nome repetido — cai para
os nomes das tabelas (TableSkillNamer). A app nunca depende da IA para funcionar.

Privacidade: apenas o nome do hábito, o atributo e o gatilho são enviados. Nada mais do jogo sai do computador.
"""

import json
import logging
import os
import random
from typing import Any, Callable

from ..engine.skills import SkillNamer, SkillTrigger, TableSkillNamer, TriggerKind, describe

log = logging.getLogger(__name__)

MODEL = "claude-opus-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"   # se o modelo recusar, o servidor tenta outro modelo
TIMEOUT_SECONDS = 20.0
MAX_NAME_LENGTH = 40
MAX_DESCRIPTION_LENGTH = 160

KEYRING_SERVICE = "AwakenSystem"
KEYRING_USER = "anthropic_api_key"

SYSTEM_PROMPT = (
    "You name skills for a habit-tracking app styled after the 'System' in the manhwa Solo Leveling. "
    "Given a habit and the milestone the player just reached, invent one skill: a short, evocative name "
    f"(2-3 words, at most {MAX_NAME_LENGTH} characters, Title Case, no quotes, not one of the names already taken) "
    "and a single-sentence flavour description that mentions the real habit. Write in English."
)

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
    },
    "required": ["name", "description"],
    "additionalProperties": False,
}


# ---------------- chave da API ----------------
def load_api_key() -> str | None:
    """Windows Credential Manager (via keyring) e, em alternativa, a variável de ambiente ANTHROPIC_API_KEY."""
    try:
        import keyring
        key = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
        if key:
            return key
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException:
        # keyring não instalado, sem cofre disponível, ou até erros nativos que não herdam de Exception
        # (ex.: PanicException de bibliotecas em Rust). Nada disto pode impedir a app de funcionar.
        pass
    return os.environ.get("ANTHROPIC_API_KEY") or None


def save_api_key(key: str | None) -> None:
    """Guarda (ou apaga, com None) a chave no cofre do sistema. Nunca vai para a base de dados da app."""
    import keyring
    if key:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USER, key.strip())
    else:
        try:
            keyring.delete_password(KEYRING_SERVICE, KEYRING_USER)
        except keyring.errors.PasswordDeleteError:
            pass


def default_client_factory() -> Any | None:
    """Cria o cliente oficial da Anthropic, ou None se o SDK não estiver instalado ou não houver chave."""
    key = load_api_key()
    if not key:
        return None
    try:
        import anthropic
    except ImportError:
        return None
    return anthropic.Anthropic(api_key=key, timeout=TIMEOUT_SECONDS, max_retries=1)


# ---------------- o "namer" ----------------
class ClaudeSkillNamer:
    """SkillNamer que pede o texto à API do Claude, com recurso automático às tabelas."""

    def __init__(self, rng: random.Random, client_factory: Callable[[], Any | None] = default_client_factory):
        self.fallback: SkillNamer = TableSkillNamer(rng)
        self.client_factory = client_factory
        self._client = None
        self._unavailable = False    # depois de uma falha de ligação, não insiste neste fecho de dia

    def name(self, trigger: SkillTrigger, taken: set[str]) -> tuple[str, str]:
        generated = None if self._unavailable else self._ask(trigger, taken)
        return generated or self.fallback.name(trigger, taken)

    def _ask(self, trigger: SkillTrigger, taken: set[str]) -> tuple[str, str] | None:
        try:
            if self._client is None:
                self._client = self.client_factory()
            if self._client is None:
                self._unavailable = True
                return None
            response = self._client.beta.messages.create(
                model=MODEL,
                max_tokens=2000,
                betas=[FALLBACK_BETA],
                fallbacks="default",
                output_config={"effort": "low", "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": _context(trigger, taken)}],
            )
        except Exception as e:       # sem internet, chave inválida, limite de pedidos, ...
            log.warning("AI skill naming unavailable, using tables: %s", e)
            self._unavailable = True
            return None
        return _parse(response, taken, trigger)


def _context(trigger: SkillTrigger, taken: set[str]) -> str:
    milestone = {
        TriggerKind.HABIT: f"completed the habit '{trigger.habit_name}' {trigger.threshold} times",
        TriggerKind.STREAK: f"kept a {trigger.threshold}-day streak on the habit '{trigger.habit_name}'",
        TriggerKind.ATTRIBUTE: f"completed {trigger.threshold} quests that train {trigger.attribute}",
    }[trigger.kind]
    return json.dumps({
        "milestone": milestone,
        "attribute": trigger.attribute,
        "names_already_taken": sorted(taken),
    })


def _parse(response: Any, taken: set[str], trigger: SkillTrigger) -> tuple[str, str] | None:
    """Valida a resposta; devolve None (→ tabelas) se algo não bater certo."""
    if getattr(response, "stop_reason", None) in ("refusal", "max_tokens"):
        return None
    text = next((b.text for b in response.content if getattr(b, "type", None) == "text"), None)
    try:
        data = json.loads(text or "")
        name, description = str(data["name"]).strip(), str(data["description"]).strip()
    except (ValueError, KeyError, TypeError):
        return None
    if not name or len(name) > MAX_NAME_LENGTH or name in taken:
        return None
    description = description[:MAX_DESCRIPTION_LENGTH]
    # a parte mecânica (bónus) é sempre escrita pela app, para ser exata
    bonus = describe(trigger).split(". ", 1)[1]
    return name, f"{description} {bonus}"
