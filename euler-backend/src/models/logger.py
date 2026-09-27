from __future__ import annotations

import logging
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = REPO_ROOT / "logs"
LOG_FILE = LOG_DIR / "euler.log"

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("euler")
logger.setLevel(LOG_LEVEL)

formatter = logging.Formatter("%(levelname)s %(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

file_handler = logging.FileHandler(LOG_FILE)
file_handler.setLevel(LOG_LEVEL)
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler()
stream_handler.setLevel(LOG_LEVEL)
stream_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(stream_handler)
