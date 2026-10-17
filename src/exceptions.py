class Impossible(Exception):
    """Exception raised when an action is impossible to be performed.

    The reason is given as the exception message.
    """

class IncompatibleSave(Exception):
    """The save file was written by an incompatible version of the game (or is not a save file)."""


class QuitWithoutSaving(SystemExit):
    """Can be raised to exit the game without automatically saving."""