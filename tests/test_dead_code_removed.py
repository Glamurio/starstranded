"""Dead, broken helpers that were deleted."""
import utilities


def test_text_input_is_gone():
    """It referenced tcod.eventKeySym, which does not exist in the pinned tcod, and nothing called it.
    Text entry is handled by CharacterCreation.ev_textinput / ev_keydown."""
    assert not hasattr(utilities, "text_input")


def test_tcod_has_no_eventKeySym():
    import tcod
    assert not hasattr(tcod, "eventKeySym")
