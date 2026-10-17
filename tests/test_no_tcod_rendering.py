"""Rendering and input are pygame-only; tcod stays for FOV, pathfinding, noise and line drawing."""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"

FORBIDDEN = [
    r"tcod\.console", r"tcod\.event", r"tcod\.tileset", r"tcod\.render", r"tcod\.sdl", r"tcod\.image",
    r"libtcodpy\.(CENTER|LEFT|RIGHT|BKGND)", r"map_codepoints", r"CHARMAP", r"global_tileset", r"root_console",
]


def test_no_tcod_rendering_or_input_apis_in_src():
    offenders = []
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN:
            for match in re.finditer(pattern, text):
                line = text[: match.start()].count("\n") + 1
                offenders.append(f"{path.relative_to(SRC)}:{line}: {match.group(0)}")
    # comments mentioning the old API are fine, code is not
    offenders = [o for o in offenders if not _is_comment(o)]
    assert offenders == []


def _is_comment(offender: str) -> bool:
    name, line, _ = offender.split(":", 2)
    source = (SRC / name).read_text(encoding="utf-8").splitlines()[int(line) - 1].strip()
    return source.startswith(("#", '"""', "`")) or ("``" in source)


def test_tcod_is_still_used_for_utilities_only():
    used = set()
    for path in SRC.rglob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip().startswith(("#", '"""', "`")) and "``" not in line:
                used |= set(re.findall(r"tcod\.(\w+)\.", line))
    assert used <= {"noise", "los", "path", "map"}
