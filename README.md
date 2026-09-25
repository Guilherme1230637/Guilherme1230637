# Awaken System

App desktop (Windows) de hábitos gamificada, inspirada no "Sistema" de *Solo Leveling* e nos rankings de cultivação
de *Tales of Demons and Gods*.

- **Especificação completa:** [`docs/ESPECIFICACAO.md`](docs/ESPECIFICACAO.md)
- **Estado:** app completa — motor de regras, SQLite, interface, PIN, lembretes, nomes de Skills por IA (opcional) e `.exe`.

## Descarregar o `.exe` (sem instalar Python)
Cada push é testado e compilado num Windows real pelo GitHub Actions:
**GitHub → separador Actions → última execução verde → Artifacts → `AwakenSystem-windows`**.

![Ecrã principal](docs/screenshots/01_status.png)

## Correr a app (Windows / PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install ".[ai]"          # PySide6 + (opcional) SDK da Anthropic e keyring
python -m awaken
```
Criar o `.exe` localmente: `pip install pyinstaller` e depois `python tools/build_exe.py` → `dist\AwakenSystem.exe`.
Os dados ficam em `%APPDATA%\AwakenSystem\awaken.db`.

## Correr os testes (Windows / PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install pytest PySide6
python -m pytest
```

## Simulador de equilíbrio
```powershell
python tools/simular_progressao.py            # tempos até cada ranking com os valores atuais
python tools/simular_progressao.py 100 3 1.5  # testar outra curva XP(n) = B + C × n^P
```

## Capturas de ecrã (jogo de demonstração)
```powershell
python tools/capturas.py            # gera docs/screenshots/*.png
```
