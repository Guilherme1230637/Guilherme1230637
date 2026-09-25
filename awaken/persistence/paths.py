"""Onde fica o ficheiro da base de dados."""

import os
import sys
from pathlib import Path

APP_DIR_NAME = "AwakenSystem"
DB_FILE_NAME = "awaken.db"


def default_db_path() -> Path:
    """Windows: %APPDATA%\\AwakenSystem\\awaken.db (pasta de dados do utilizador).
    Outros sistemas (desenvolvimento/testes): ~/.local/share/AwakenSystem/awaken.db."""
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        base = Path(os.environ["APPDATA"])
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    folder = base / APP_DIR_NAME
    folder.mkdir(parents=True, exist_ok=True)
    return folder / DB_FILE_NAME
