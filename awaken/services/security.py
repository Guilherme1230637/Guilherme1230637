"""PIN da app (secção 9).

O PIN nunca é guardado. Guarda-se apenas o resultado de PBKDF2-HMAC-SHA256 com um salt aleatório:
- PBKDF2 repete o hash muitas vezes (ITERATIONS) de propósito, para tornar lento cada palpite de um atacante;
- o salt (16 bytes aleatórios) faz com que o mesmo PIN gere hashes diferentes em instalações diferentes,
  inutilizando tabelas pré-calculadas;
- a comparação é feita em tempo constante (hmac.compare_digest), para não revelar pelo tempo de resposta
  quantos bytes estavam certos.

Limitação assumida: um PIN de 4–6 dígitos tem no máximo 1 111 000 combinações. Protege o acesso à app,
não é cifra dos dados (o ficheiro SQLite continua legível por quem tenha acesso ao disco).
"""

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field
from typing import Callable

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 200_000
SALT_BYTES = 16
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 30


def validate_pin(pin: str) -> None:
    if not (pin.isdigit() and 4 <= len(pin) <= 6):
        raise ValueError("The PIN must have 4 to 6 digits.")


def hash_pin(pin: str, salt: bytes | None = None, iterations: int = ITERATIONS) -> str:
    """Devolve 'pbkdf2_sha256$iterações$salt$hash' — tudo o que é preciso para verificar mais tarde."""
    validate_pin(pin)
    salt = salt or secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, iterations)
    return f"{ALGORITHM}${iterations}${salt.hex()}${digest.hex()}"


def verify_pin(pin: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if algorithm != ALGORITHM:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt_hex), int(iterations))
    return hmac.compare_digest(candidate, bytes.fromhex(digest_hex))


@dataclass
class PinGate:
    """Controla as tentativas: após MAX_ATTEMPTS erros seguidos, bloqueia durante LOCKOUT_SECONDS."""
    stored_hash: str
    clock: Callable[[], float] = time.monotonic
    failures: int = 0
    locked_until: float = field(default=0.0)

    def seconds_locked(self) -> int:
        return max(0, round(self.locked_until - self.clock()))

    def try_pin(self, pin: str) -> bool:
        if self.seconds_locked():
            return False
        if verify_pin(pin, self.stored_hash):
            self.failures = 0
            return True
        self.failures += 1
        if self.failures >= MAX_ATTEMPTS:
            self.failures = 0
            self.locked_until = self.clock() + LOCKOUT_SECONDS
        return False
