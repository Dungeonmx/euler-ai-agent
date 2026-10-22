import sys
from pathlib import Path

# Los tests importan el paquete `guards` sin instalar el proyecto, igual que
# `src/main.py` agrega `src/` al path al arrancar.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
