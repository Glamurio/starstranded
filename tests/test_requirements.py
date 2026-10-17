"""requirements.txt and pyproject.toml must not disagree about runtime dependencies."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _names(lines):
    return {re.split(r"[<>=!~ ]", line.strip().strip('",'))[0].lower() for line in lines if line.strip().strip('",')}


def test_requirements_match_pyproject_dependencies():
    pyproject = (ROOT / "pyproject.toml").read_text()
    deps = pyproject.split("dependencies = [", 1)[1].split("]", 1)[0].splitlines()
    req = (ROOT / "requirements.txt").read_text().splitlines()
    assert _names(deps) == _names(req)
    assert "tcod==20.1.0" not in (ROOT / "requirements.txt").read_text()
