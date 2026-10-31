import sys
from pathlib import Path

WORKER_DIR = Path(__file__).resolve().parents[2]
if str(WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(WORKER_DIR))
