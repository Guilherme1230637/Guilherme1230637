"""O namer de IA com um cliente falso: nenhum teste faz pedidos reais nem precisa de chave."""

import json
import random
from types import SimpleNamespace

from awaken.engine.skills import SkillTrigger, TriggerKind
from awaken.services.ai_namer import MODEL, ClaudeSkillNamer

TRIGGER = SkillTrigger(TriggerKind.STREAK, "1", 7, "INT", "Study Japanese")


class FakeClient:
    def __init__(self, reply=None, error=None, stop_reason="end_turn"):
        self.calls = []
        self.reply, self.error, self.stop_reason = reply, error, stop_reason
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        block = SimpleNamespace(type="text", text=self.reply)
        return SimpleNamespace(stop_reason=self.stop_reason, content=[block])


def namer(client):
    return ClaudeSkillNamer(random.Random(0), client_factory=lambda: client)


def test_uses_ai_name_and_keeps_exact_bonus_text():
    client = FakeClient(json.dumps({"name": "Kanji Blade", "description": "Seven days of strokes sharpened your mind."}))
    name, description = namer(client).name(TRIGGER, set())
    assert name == "Kanji Blade"
    assert description.startswith("Seven days of strokes")
    assert description.endswith("+2% XP per level on that quest.")
    call = client.calls[0]
    assert call["model"] == MODEL and call["fallbacks"] == "default"
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert "Study Japanese" in call["messages"][0]["content"]


def test_falls_back_to_tables_without_key():
    name, _ = namer(None).name(TRIGGER, set())
    assert name                                   # nome das tabelas


def test_falls_back_on_network_error_and_stops_retrying():
    client = FakeClient(error=ConnectionError("offline"))
    n = namer(client)
    n.name(TRIGGER, set())
    n.name(TRIGGER, set())
    assert len(client.calls) == 1                 # depois da 1.ª falha não insiste


def test_falls_back_on_refusal_invalid_json_or_taken_name():
    for client in (FakeClient(json.dumps({"name": "X", "description": "y"}), stop_reason="refusal"),
                   FakeClient("not json"),
                   FakeClient(json.dumps({"name": "Taken Name", "description": "d"})),
                   FakeClient(json.dumps({"name": "A" * 80, "description": "d"}))):
        name, _ = namer(client).name(TRIGGER, {"Taken Name"})
        assert name not in ("X", "Taken Name", "A" * 80)


def test_broken_credential_store_never_breaks_the_app(monkeypatch):
    import sys
    from types import ModuleType

    from awaken.services import ai_namer

    class NativePanic(BaseException):     # como o PanicException do Rust: não herda de Exception
        pass

    broken = ModuleType("keyring")
    broken.get_password = lambda *a: (_ for _ in ()).throw(NativePanic("boom"))
    monkeypatch.setitem(sys.modules, "keyring", broken)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env")
    assert ai_namer.load_api_key() == "from-env"
