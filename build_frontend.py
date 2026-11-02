#!/usr/bin/env python3
"""Build the Vite dashboard before Vercel packages the unified FastAPI app."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"


def main() -> None:
    if not shutil.which("npm"):
        raise SystemExit("Node.js/npm is required to build the BharatSim frontend")
    subprocess.run(["npm", "ci"], cwd=FRONTEND, check=True)
    subprocess.run(["npm", "run", "build"], cwd=FRONTEND, check=True)
    if not (FRONTEND / "dist" / "index.html").is_file():
        raise SystemExit("Vite build completed without frontend/dist/index.html")


if __name__ == "__main__":
    main()
