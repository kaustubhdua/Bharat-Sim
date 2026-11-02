from __future__ import annotations

import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _requirement_name(requirement: str) -> str:
    return re.split(r"[\s<=>!~;\[]", requirement.strip(), maxsplit=1)[0].lower().replace("_", "-")


def test_vercel_project_dependencies_cover_backend_runtime_requirements() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = {
        _requirement_name(item)
        for item in project.get("project", {}).get("dependencies", [])
    }
    backend_requirements = {
        _requirement_name(line)
        for line in (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert backend_requirements <= declared, (
        "Vercel installs the root pyproject.toml, so it must declare every backend "
        f"runtime dependency. Missing: {sorted(backend_requirements - declared)}"
    )
