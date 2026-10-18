from typing import Iterable, List, Reversible, Tuple
import textwrap

import color


def legible(fg: Tuple[int, int, int], minimum: int = 150) -> Tuple[int, int, int]:
    """Lift a dark text colour (blue, brown, grey) towards white until it can be read on the dark window background."""
    r, g, b = fg
    brightness = 0.299 * r + 0.587 * g + 0.114 * b
    if brightness >= minimum:
        return fg
    t = min(1.0, (minimum - brightness) / max(1.0, 255 - brightness))
    return (round(r + (255 - r) * t), round(g + (255 - g) * t), round(b + (255 - b) * t))


class Message:
    def __init__(self, text: str, fg: Tuple[int, int, int]):
        self.plain_text = text
        self.fg = fg
        self.count = 1

    @property
    def full_text(self) -> str:
        """The full text of this message, including the count if necessary."""
        if self.count > 1:
            return f"{self.plain_text} (x{self.count})"
        return self.plain_text


class MessageLog:
    def __init__(self) -> None:
        self.messages: List[Message] = []

    def add_message(
        self, text: str, fg: Tuple[int, int, int] = color.white, *, stack: bool = True,
    ) -> None:
        """Add a message to this log.
        `text` is the message text, `fg` is the text color.
        If `stack` is True then the message can stack with a previous message
        of the same text.
        """
        if stack and self.messages and text == self.messages[-1].plain_text:
            self.messages[-1].count += 1
        else:
            self.messages.append(Message(text, fg))

    def render(
        self, canvas, x: int, y: int, width: int, height: int,
    ) -> None:
        """Render this log over the given area.
        `x`, `y`, `width`, `height` is the rectangular region (in cells) to render onto
        the `canvas`.
        """
        self.render_messages(canvas, x, y, width, height, self.messages)

    @staticmethod
    def wrap(string: str, width: int) -> Iterable[str]:
        """Return a wrapped text message."""
        for line in string.splitlines():  # Handle newlines in messages.
            yield from textwrap.wrap(
                line, width * 2, expand_tabs=True,   # text is set two characters to a cell (see `ui`)
            )

    @classmethod
    def render_messages(
        cls,
        canvas,
        x: int,
        y: int,
        width: int,
        height: int,
        messages: Reversible[Message],
    ) -> None:
        """Render the messages provided.
        The `messages` are rendered starting at the last message and working
        backwards.
        """
        y_offset = height - 1

        for message in reversed(messages):
            for line in reversed(list(cls.wrap(message.full_text, width))):
                canvas.print(x, y + y_offset, line, fg=legible(message.fg))
                y_offset -= 1
                if y_offset < 0:
                    return  # No more space to print messages.