"""Ponto de entrada para o PyInstaller (ele precisa de um script, não de um módulo com imports relativos)."""

import sys

from awaken.app import main

if __name__ == "__main__":
    sys.exit(main())
