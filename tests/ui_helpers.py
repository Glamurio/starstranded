"""The window/canvas/handler stack the tests draw on (one shared headless session).

`conftest` makes every `Engine` built without an explicit session use it, so engine handlers push onto
`SESSION.handlers` and screens render onto `SESSION.canvas`.
"""
from session import Session

SESSION = Session.create(headless=True)  # conftest has switched to src/ (assets) before importing this


def reopen() -> None:
    """Recreate the shared window (a test that opened its own display replaced it)."""
    fresh = Session.create(headless=True)
    SESSION.display, SESSION.canvas = fresh.display, fresh.canvas
