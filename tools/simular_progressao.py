"""Simulador de progressão do Awaken System.

Simula, dia a dia, quanto tempo três perfis de jogador demoram a atingir os
níveis importantes (subidas de ranking de cultivação), para calibrar a curva de XP
e os custos em Gold antes de os fixar na app.

Uso:  python tools/simular_progressao.py            (valores da especificação)
      python tools/simular_progressao.py 120 1.2    (testar outra curva: C e P)
"""

import sys

# --- Parâmetros da curva de XP: XP para passar do nível n para n+1 = C * n^P ---
C = 130
P = 1.2

# --- Multiplicadores de XP (valores da especificação) ---
BONUS_STREAK_MAX = 0.30   # +1 % por dia de streak, até +30 %
BONUS_SKILLS_MAX = 0.50   # teto do bónus das Skills
DIAS_SKILLS_MAX = 730     # assumimos que as Skills chegam ao teto em ~2 anos

# --- Fração do Gold ganho que o jogador gasta na Shop ---
GASTO_SHOP = 0.5

# --- Rankings de cultivação: (nome, nível mínimo, custo em Gold) ---
MARCOS = [
    ("Bronze", 10, 1_000),
    ("Silver", 25, 4_000),
    ("Gold", 40, 10_000),
    ("Dark Gold", 55, 20_000),
    ("Legend", 70, 35_000),
    ("Heavenly Fate", 85, 55_000),
]

# --- Perfis: XP base potencial por dia (soma dos ranks) e taxa média de cumprimento r ---
PERFIS = {
    "Casual":   {"xp_base": 145, "r": 0.65},
    "Regular":  {"xp_base": 250, "r": 0.80},
    "Hardcore": {"xp_base": 420, "r": 0.95},
}


def xp_para_subir(nivel: int) -> int:
    return round(C * nivel ** P)


def multiplicador(dia: int, r: float) -> float:
    """Bónus crescem com o tempo: streaks enchem em ~30 dias, Skills em ~2 anos."""
    streak = BONUS_STREAK_MAX * min(dia / 30, 1) * r   # quem falha mais perde streaks
    skills = BONUS_SKILLS_MAX * min(dia / DIAS_SKILLS_MAX, 1)
    return 1 + streak + skills


def simular(xp_base: float, r: float, max_dias: int = 3650) -> dict:
    nivel, xp, gold = 1, 0.0, 0.0
    marcos_pendentes = list(MARCOS)
    resultado = {}
    for dia in range(1, max_dias + 1):
        xp += xp_base * r * multiplicador(dia, r)
        gold += (xp_base / 2) * r * (1 - GASTO_SHOP)   # Gold base = XP base / 2, sem bónus
        while xp >= xp_para_subir(nivel):
            xp -= xp_para_subir(nivel)
            nivel += 1
        # Um marco só é atingido com o nível E o Gold necessário (o Gold é pago)
        while marcos_pendentes:
            nome, nivel_min, custo = marcos_pendentes[0]
            if nivel >= nivel_min and gold >= custo:
                gold -= custo
                resultado[nome] = dia
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
    if len(sys.argv) == 3:
        C, P = float(sys.argv[1]), float(sys.argv[2])
    print(f"Curva: XP(n) = {C} * n^{P}\n")
    colunas = [f"{m[0]} (Lv {m[1]}, {m[2]} G)" for m in MARCOS]
    print("| Perfil | " + " | ".join(colunas) + " |")
    print("|---" * (len(colunas) + 1) + "|")
    for nome, p in PERFIS.items():
        res = simular(p["xp_base"], p["r"])
        celulas = [formatar(res.get(m[0])) for m in MARCOS]
        print(f"| {nome} | " + " | ".join(celulas) + " |")
