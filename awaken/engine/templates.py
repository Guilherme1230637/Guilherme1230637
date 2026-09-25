"""Distribuições de atributos sugeridas por categoria (secção 3.3). O jogador pode ajustá-las."""

WEIGHT_TEMPLATES: dict[str, dict[str, float]] = {
    "Study":            {"INT": 0.6, "WIS": 0.3, "TEN": 0.1},
    "Language":         {"INT": 0.5, "CHA": 0.3, "TEN": 0.2},
    "Reading":          {"WIS": 0.6, "INT": 0.4},
    "Strength training": {"STR": 0.6, "END": 0.3, "VIT": 0.1},
    "Cardio":           {"AGI": 0.5, "END": 0.4, "VIT": 0.1},
    "Health & sleep":   {"VIT": 0.8, "TEN": 0.2},
    "Meditation & focus": {"PER": 0.6, "WIS": 0.3, "TEN": 0.1},
    "Social":           {"CHA": 0.8, "PER": 0.2},
    "Finance":          {"WIS": 0.7, "PER": 0.3},
    "Avoid a vice":     {"TEN": 0.7, "PER": 0.3},
}
