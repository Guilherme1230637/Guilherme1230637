# Awaken System

App desktop (Windows) de hábitos gamificada, inspirada no "Sistema" de *Solo Leveling* e nos rankings de cultivação
de *Tales of Demons and Gods*.

- **Especificação completa:** [`docs/ESPECIFICACAO.md`](docs/ESPECIFICACAO.md)
- **Estado:** fase 1 concluída — motor de regras do jogo com testes. Interface (PySide6) e base de dados a seguir.

## Correr os testes (Windows / PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install pytest
python -m pytest
```

## Simulador de equilíbrio
```powershell
python tools/simular_progressao.py            # tempos até cada ranking com os valores atuais
python tools/simular_progressao.py 100 3 1.5  # testar outra curva XP(n) = B + C × n^P
```
