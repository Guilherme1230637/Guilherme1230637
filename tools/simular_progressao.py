"""Simulador de progressão do Awaken System.

Simula, dia a dia, quanto tempo três perfis de jogador demoram a atingir os
níveis importantes (subidas de ranking de cultivação), para calibrar a curva de XP
e os custos em Gold antes de os fixar na app.

Uso:  python tools/simular_progressao.py            (valores da especificação)
      python tools/simular_progressao.py 100 3 1.5  (testar outra curva: B, C e P)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # permite importar o pacote awaken

from awaken.engine import config, leveling  # noqa: E402  (fonte única dos números do jogo)

BONUS_STREAK_MAX = config.STREAK_BONUS_MAX
BONUS_SKILLS_MAX = config.SKILLS_BONUS_MAX
DIAS_SKILLS_MAX = 730     # pressuposto do modelo: as Skills chegam ao teto em ~2 anos

# Rankings de cultivação: (nome, nível mínimo, custo em Gold), lidos do motor
MARCOS = [(r.name, r.min_level, r.gold_cost) for r in config.CULTIVATION_RANKS[1:]]

# --- Perfis: XP base potencial por dia (soma dos ranks) e taxa média de cumprimento r ---
PERFIS = {
    "Casual":   {"xp_base": 145, "r": 0.65},
    "Regular":  {"xp_base": 250, "r": 0.80},
    "Hardcore": {"xp_base": 420, "r": 0.95},
}


def xp_para_subir(nivel: int) -> int:
    return leveling.xp_to_next_level(nivel)


def multiplicador(dia: int, r: float, bonus_ranking: float) -> float:
    """Bónus crescem com o tempo: streaks enchem em ~30 dias, Skills em ~2 anos; mais o bónus do ranking atual."""
    streak = BONUS_STREAK_MAX * min(dia / 30, 1) * r   # quem falha mais perde streaks
    skills = BONUS_SKILLS_MAX * min(dia / DIAS_SKILLS_MAX, 1)
    return 1 + streak + skills + bonus_ranking


def simular(xp_base: float, r: float, max_dias: int = 3650) -> dict:
    nivel, xp, gold = 1, 0.0, 0.0
    marcos_pendentes = list(MARCOS)
    resultado = {}
    bonus_ranking = 0.0
    for dia in range(1, max_dias + 1):
        xp += xp_base * r * multiplicador(dia, r, bonus_ranking)
        gold += (xp_base / 2) * r   # Gold base = XP base / 2, sem bónus; só se gasta em breakthroughs
        while xp >= xp_para_subir(nivel):
            xp -= xp_para_subir(nivel)
            nivel += 1
        # Um marco só é atingido com o nível E o Gold necessário (o Gold é pago)
        while marcos_pendentes:
            nome, nivel_min, custo = marcos_pendentes[0]
            if nivel >= nivel_min and gold >= custo:
                gold -= custo
                resultado[nome] = dia
                bonus_ranking = next(rk.xp_bonus for rk in config.CULTIVATION_RANKS if rk.name == nome)
                marcos_pendentes.pop(0)
            else:
                break
        if not marcos_pendentes:
            break
    return resultado


def formatar(dias) -> str:
    if dias is None:
        return "> 10 anos"
    if dias < 60:
        return f"{dias} dias"
    if dias < 730:
        return f"{dias / 30.4:.1f} meses"
    return f"{dias / 365:.1f} anos"


if __name__ == "__main__":
    if len(sys.argv) == 4:  # testar outra curva sem mexer no motor
        config.XP_CURVE_BASE, config.XP_CURVE_COEF, config.XP_CURVE_EXP = (float(x) for x in sys.argv[1:])
    print(f"Curva: XP(n) = {config.XP_CURVE_BASE} + {config.XP_CURVE_COEF} * n^{config.XP_CURVE_EXP}\n")
    resultados = {nome: simular(p["xp_base"], p["r"]) for nome, p in PERFIS.items()}
    print("| Ranking | Requisito | " + " | ".join(PERFIS) + " |")
    print("|---" * (len(PERFIS) + 2) + "|")
    for nome, nivel, custo in MARCOS:
        celulas = [formatar(resultados[p].get(nome)) for p in PERFIS]
        print(f"| {nome} | Lv {nivel} + {custo:,} Gold | " + " | ".join(celulas) + " |")
