"""The game must not depend on matplotlib at runtime."""
import os
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"


def test_importing_the_game_does_not_import_matplotlib():
    code = (
        "import sys, setup_game, procgen, main\n"
        "bad = sorted(m for m in sys.modules if m == 'matplotlib' or m.startswith('matplotlib.'))\n"
        "assert not bad, bad\n"
    )
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    result = subprocess.run([sys.executable, "-W", "ignore", "-c", code], cwd=SRC, env=env,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_matplotlib_is_not_a_declared_dependency():
    text = (SRC.parent / "pyproject.toml").read_text()
    deps = text.split("dependencies = [", 1)[1].split("]", 1)[0]
    assert "matplotlib" not in deps
