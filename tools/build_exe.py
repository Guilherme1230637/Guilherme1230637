"""Cria o executável da app com PyInstaller.

Uso (no Windows, dentro do venv):   pip install pyinstaller   e depois   python tools/build_exe.py
Resultado: dist/AwakenSystem.exe  (um único ficheiro, sem consola)

O PyInstaller só gera executáveis para o sistema onde corre: um .exe tem de ser criado em Windows
(no teu PC ou no GitHub Actions — ver .github/workflows/build.yml).
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"


def make_icon() -> Path:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")     # não precisa de ecrã para desenhar o ícone
    sys.path.insert(0, str(ROOT))
    from PySide6.QtGui import QGuiApplication

    from awaken.ui.icon import make_pixmap

    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841 (o Qt exige uma app para desenhar)
    BUILD.mkdir(exist_ok=True)
    path = BUILD / "awaken.ico"
    if not make_pixmap(256).save(str(path), "ICO"):
        raise RuntimeError("Could not write the icon")
    return path


def main() -> None:
    import PyInstaller.__main__

    icon = make_icon()
    PyInstaller.__main__.run([
        str(ROOT / "tools" / "launcher.py"),
        "--name", "AwakenSystem",
        "--onefile",            # um único .exe
        "--windowed",           # sem janela de consola
        "--icon", str(icon),
        "--paths", str(ROOT),
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(BUILD / "pyinstaller"),
        "--specpath", str(BUILD),
        # não é usada pela app: só aparece porque o keyring a importa em Linux (no Windows usa o cofre do Windows)
        "--exclude-module", "cryptography",
        "--noconfirm",
        "--clean",
    ])


if __name__ == "__main__":
    main()
