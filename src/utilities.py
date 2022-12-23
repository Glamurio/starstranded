# Utility functions
import tcod

def clamp(n, smallest, largest): return max(smallest, min(n, largest))

def is_mouse_in_rectangle(mouse: tcod.event.MouseState, rectangle: tcod.event.Point, width: int, height: int):
    mouse_pt = mouse.pixel

    return (rectangle.x - width / 2) < (mouse_pt.x / 10) and (rectangle.x + width / 2) > (mouse_pt.x / 10) \
        and (rectangle.y - height / 2) < (mouse_pt.y // 10) and (rectangle.y + height / 2) > (mouse_pt.y // 10)