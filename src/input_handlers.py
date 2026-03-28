from __future__ import annotations

import os

from typing import Callable, List, Optional, Tuple, TYPE_CHECKING, Union

from tcod import libtcodpy
import g

import actions
import color
import exceptions
from utilities import is_mouse_in_rectangle

from entity import Item, Entity

if TYPE_CHECKING:
    from engine import Engine
    from components.unit import Unit
    from components.equippable import Equippable
    from components.inventory import Inventory

MOVE_KEYS = {
    # Arrow keys.
    libtcodpy.tcod.event.KeySym.UP: (0, -1),
    libtcodpy.tcod.event.KeySym.DOWN: (0, 1),
    libtcodpy.tcod.event.KeySym.LEFT: (-1, 0),
    libtcodpy.tcod.event.KeySym.RIGHT: (1, 0),
    libtcodpy.tcod.event.KeySym.HOME: (-1, -1),
    libtcodpy.tcod.event.KeySym.END: (-1, 1),
    libtcodpy.tcod.event.KeySym.PAGEUP: (1, -1),
    libtcodpy.tcod.event.KeySym.PAGEDOWN: (1, 1),
    # Numpad keys.
    libtcodpy.tcod.event.KeySym.KP_1: (-1, 1),
    libtcodpy.tcod.event.KeySym.KP_2: (0, 1),
    libtcodpy.tcod.event.KeySym.KP_3: (1, 1),
    libtcodpy.tcod.event.KeySym.KP_4: (-1, 0),
    libtcodpy.tcod.event.KeySym.KP_6: (1, 0),
    libtcodpy.tcod.event.KeySym.KP_7: (-1, -1),
    libtcodpy.tcod.event.KeySym.KP_8: (0, -1),
    libtcodpy.tcod.event.KeySym.KP_9: (1, -1),
    # Vi keys.
    # libtcodpy.tcod.event.KeySym.h: (-1, 0),
    # libtcodpy.tcod.event.KeySym.j: (0, 1),
    # libtcodpy.tcod.event.KeySym.k: (0, -1),
    # libtcodpy.tcod.event.KeySym.l: (1, 0),
    # libtcodpy.tcod.event.KeySym.y: (-1, -1),
    # libtcodpy.tcod.event.KeySym.u: (1, -1),
    # libtcodpy.tcod.event.KeySym.b: (-1, 1),
    # libtcodpy.tcod.event.KeySym.n: (1, 1),
}

CONFIRM_KEYS = {
    libtcodpy.tcod.event.KeySym.RETURN,
    libtcodpy.tcod.event.KeySym.KP_ENTER,
}

WAIT_KEYS = {
    libtcodpy.tcod.event.KeySym.SPACE,
    libtcodpy.tcod.event.KeySym.KP_5,
    libtcodpy.tcod.event.KeySym.CLEAR,
}

ActionOrHandler = Union[actions.Action, "BaseEventHandler"]
"""An event handler return value which can trigger an action or switch active handlers.

If a handler is returned then it will become the active handler for future events.
If an action is returned it will be attempted and if it's valid then
MainGameEventHandler will become the active handler.
"""


class BaseEventHandler(libtcodpy.tcod.event.EventDispatch[ActionOrHandler]):

    def __init__(self) -> None:
        super().__init__()
        self.on_init()

    def on_init(self):
        """Function that runs after init"""
        pass

    def handle_events(self, event: libtcodpy.tcod.event.Event) -> BaseEventHandler:
        """Handle an event and return the next active event handler."""
        state = self.dispatch(event)
        if isinstance(state, BaseEventHandler):
            return state
        assert not isinstance(state, actions.Action), f"{self!r} can not handle actions."
        return self

    def on_render(self, console: libtcodpy.tcod.console.Console) -> None:
        raise NotImplementedError()

    def ev_quit(self, event: libtcodpy.tcod.event.Quit) -> Optional[actions.Action]:
        raise SystemExit()

class PopupMessage(BaseEventHandler):
    """Display a popup text window."""

    def __init__(self, parent_handler: BaseEventHandler, text: str):
        self.parent = parent_handler
        self.text = text

    def on_render(self, console: libtcodpy.tcod.console.Console) -> None:
        """Render the parent and dim the result, then print the message on top."""
        self.parent.on_render(console)
        console.rgb["fg"] //= 8
        console.rgb["bg"] //= 8

        console.print(
            console.width // 2,
            console.height // 2,
            text=self.text,
            fg=color.white,
            bg=color.black,
            alignment=libtcodpy.CENTER,
        )

    def ev_keydown(self, event: libtcodpy.tcod.event.KeyDown) -> Optional[BaseEventHandler]:
        """Any key returns to the parent handler."""
        return self.parent


class EventHandler(BaseEventHandler):
    def __init__(self, engine: Engine):
        self.engine = engine

    def reset_to_handler(self, handler: EventHandler):
        """Resets active handler to handler provided"""
        g.handlers = [handler]

    def resolve_handler(self) -> EventHandler:
        """Resolves and returns current handler and switches to the next in stack"""
        handler = g.handlers.pop()

        if not len(g.handlers):
            self.reset_to_handler(MainGameEventHandler(self.engine))

        return handler
            

    def handle_events(self, event: libtcodpy.tcod.event.Event) -> BaseEventHandler:
        """Handle events for input handlers with an engine."""
        action_or_state = self.dispatch(event)

        if isinstance(action_or_state, BaseEventHandler):
            g.handlers.append(action_or_state) # Add handler to stack

        if isinstance(action_or_state, actions.Action) and self.handle_action(action_or_state):
            # A valid action was performed.
            if not self.engine.player.is_alive:
                # The player was killed sometime during or after the action.
                return GameOverEventHandler(self.engine)
            elif self.engine.player.level.requires_level_up:
                return LevelUpEventHandler(self.engine)

            if not len(g.handlers):
                self.reset_to_handler(MainGameEventHandler(self.engine)) # Return to the main handler.

        if len(g.handlers):
            return g.handlers[-1] # Switch to most recent handler in stack

        return self

    def handle_action(self, action: Optional[actions.Action]) -> bool:
        """Handle actions returned from event methods.

        Returns True if the action will advance a turn.
        """
        if action is None:
            return None

        try:
            # Actions return `True` for repeat
            repeat = action.perform()
            while repeat:
                repeat = action.perform()
                # time.sleep(0.05)
                g.render(self)
        except exceptions.Impossible as exc:
            self.engine.message_log.add_message(exc.args[0], color.impossible)
            return False  # Skip enemy turn on exceptions.

        return True

    def ev_mousemotion(self, event: libtcodpy.tcod.event.MouseMotion) -> None:
        tx, ty = int(event.position.x), int(event.position.y)
        if self.engine.game_map.in_bounds(tx, ty):
            self.engine.mouse_location = libtcodpy.tcod.event.Point(tx, ty)

    def on_render(self, console: libtcodpy.tcod.console.Console) -> None:
        self.engine.render(console)


class AskUserEventHandler(EventHandler):
    """Handles user input for actions which require special input."""

    def ev_keydown(self, event: libtcodpy.tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        """By default any key exits this input handler."""
        if event.sym in {  # Ignore specific keys
            libtcodpy.tcod.event.KeySym.LSHIFT,
            libtcodpy.tcod.event.KeySym.RSHIFT,
            libtcodpy.tcod.event.KeySym.LCTRL,
            libtcodpy.tcod.event.KeySym.RCTRL,
            libtcodpy.tcod.event.KeySym.LALT,
            libtcodpy.tcod.event.KeySym.RALT,
            libtcodpy.tcod.event.KeySym.UP,
            libtcodpy.tcod.event.KeySym.DOWN
        }:
            return None
        if event.sym in CONFIRM_KEYS:
            return None
        return self.on_exit()

    def ev_mousebuttondown(
        self, event: libtcodpy.tcod.event.MouseButtonDown
    ) -> Optional[ActionOrHandler]:
        """By default any mouse click exits this input handler."""
        return self.on_exit()

    def on_exit(self) -> Optional[ActionOrHandler]:
        """Called when the user is trying to exit or cancel an action.

        By default this simply resolves the current active handler
        """
        self.resolve_handler()
        

class PickupHandler(AskUserEventHandler):

    def __init__(self, engine: Engine):
        super().__init__(engine)
        self.target_location = libtcodpy.tcod.event.Point(0, 0)

    def on_render(self, console: libtcodpy.tcod.console.Console) -> None:
        super().on_render(console)

        player = self.engine.player
        mouse_x, mouse_y = self.engine.mouse_location
        distance = self.engine.distance((player.x, player.y), (mouse_x, mouse_y))
        path = self.engine.get_path_to(player.ai, mouse_x, mouse_y)
        tile = path.pop(0) if path else (player.x, player.y)
        if distance <= 1:
            self.target_location = libtcodpy.tcod.event.Point(mouse_x, mouse_y)
            console.rgb["bg"][mouse_x, mouse_y] = color.white
            console.rgb["fg"][mouse_x, mouse_y] = color.black
        else:
            self.target_location = libtcodpy.tcod.event.Point(tile[0], tile[1])
            console.rgb["bg"][tile[0], tile[1]] = color.white
            console.rgb["fg"][tile[0], tile[1]] = color.black

    def ev_mousebuttondown(
        self, event: libtcodpy.tcod.event.MouseButtonDown
    ) -> Optional[ActionOrHandler]:
        """By default any mouse click exits this input handler."""
        if event.button == libtcodpy.tcod.event.MouseButton.LEFT:
            targets = self.engine.game_map.get_entities_at_location(self.target_location.x, self.target_location.y)
            return self.on_tile_selected(targets)

    def ev_keydown(self, event: libtcodpy.tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        if event.sym == libtcodpy.tcod.event.KeySym.G or event.sym == libtcodpy.tcod.event.KeySym.RETURN:
            targets = self.engine.game_map.get_entities_at_location(self.target_location.x, self.target_location.y)
            return self.on_tile_selected(targets)

    def on_tile_selected(self, targets: List[Entity]) -> Optional[ActionOrHandler]:
        """Called when the user selects a valid item."""

        if self.engine.player in targets:
            targets.remove(self.engine.player)
        if not targets:
            return self.on_exit()
        if len(targets) == 1:
            target = targets[0]
            if hasattr(target, "material"):
                return actions.PickupAction(self.engine.player, target)

        self.resolve_handler()
        return InventoryLootHandler(self.engine, self.engine.player, entities=targets)
        


class CharacterScreenEventHandler(AskUserEventHandler):
    TITLE = "Character Information"

    def on_render(self, console: libtcodpy.tcod.console.Console) -> None:
        super().on_render(console)

        if self.engine.player.x <= 30:
            x = 40
        else:
            x = 0

        y = 0

        width = len(self.TITLE) + 4

        console.draw_frame(
            x=x,
            y=y,
            width=width,
            height=7,
            title=self.TITLE,
            clear=True,
            fg=(255, 255, 255),
            bg=(0, 0, 0),
        )

        console.print(
            x=x + 1, y=y + 1, text=f"Level: {self.engine.player.level.current_level}"
        )
        console.print(
            x=x + 1, y=y + 2, text=f"XP: {self.engine.player.level.current_xp}"
        )
        console.print(
            x=x + 1,
            y=y + 3,
            text=f"XP for next Level: {self.engine.player.level.experience_to_next_level}",
        )

        console.print(
            x=x + 1, y=y + 4, text=f"Attack: {self.engine.player.power}"
        )
        console.print(
            x=x + 1, y=y + 5, text=f"Defense: {self.engine.player.defense}"
        )


class LevelUpEventHandler(AskUserEventHandler):
    TITLE = "Level Up"

    def on_render(self, console: libtcodpy.tcod.console.Console) -> None:
        super().on_render(console)

        x = 0
        y = 0

        console.draw_frame(
            x=x,
            y=y,
            width=35,
            height=8,
            title=self.TITLE,
            clear=True,
            fg=(255, 255, 255),
            bg=(0, 0, 0),
        )

        console.print(x=x + 1, y=1, text="Congratulations! You level up!")
        console.print(x=x + 1, y=2, text="Select an attribute to increase.")

        console.print(
            x=x + 1,
            y=4,
            text=f"a) Constitution (+20 HP, from {self.engine.player.max_hp})",
        )
        console.print(
            x=x + 1,
            y=5,
            text=f"b) Strength (+1 attack, from {self.engine.player.power})",
        )
        console.print(
            x=x + 1,
            y=6,
            text=f"c) Agility (+1 defense, from {self.engine.player.defense})",
        )

    def ev_keydown(self, event: libtcodpy.tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        player = self.engine.player
        key = event.sym
        index = key - libtcodpy.tcod.event.KeySym.A

        if 0 <= index <= 2:
            if index == 0:
                player.level.increase_max_hp()
            elif index == 1:
                player.level.increase_power()
            else:
                player.level.increase_defense()
        else:
            self.engine.message_log.add_message("Invalid entry.", color.invalid)

            return None

        return super().ev_keydown(event)

    def ev_mousebuttondown(
        self, event: libtcodpy.tcod.event.MouseButtonDown
    ) -> Optional[ActionOrHandler]:
        """
        Don't allow the player to click to exit the menu, like normal.
        """
        return None

class InventoryEventHandler(AskUserEventHandler):
    """
    This handler lets the user select an item.

    What happens then depends on the subclass.
    """

    TITLE = "<missing title>"#
    
    console_height: int
    console_width: int
    menu_width: int = 0
    menu_i: int = None
    height_per_item: int = 2

    console_x: int
    console_y: int
    offset: int

    inventory: Inventory
    inventory_entries: List[Item] = []
    entries_amount: int = 0

    buttons = {}
    button_height: int = 2
    button_highlight: str = None

    def __init__(self, engine: Engine, inventory: Inventory = None, entities: List[Entity] = None, console: libtcodpy.tcod.console.Console = None, offset: int = 0):
        super().__init__(engine)
        # If there's only one entity at target location, treat it as single inventory
        entity: Entity = entities[0] if entities and len(entities) == 1 else None
        self.inventory = entity.inventory if entity and not inventory else inventory
        
        self.entities = entities
        self.offset = offset
        self.console = console

    def on_render(self, console: libtcodpy.tcod.console.Console) -> None:
        """
        Render an inventory menu, which displays the items in the inventory.
        """
        is_player = False
        prev_index = g.handlers.index(self) - 1
        parent = g.handlers[prev_index] if prev_index >= 0 else None

        if parent: 
            parent.on_render(console)
        else:
            super().on_render(console)
        
        if self.inventory:
            self.TITLE = f"{self.inventory.parent.get_title()}"

        if self.inventory and self.inventory.parent == self.engine.player:
            is_player = True
            self.TITLE = f"Inventory"

        self.console_x = g.screen_width_offset * (1 + self.offset)
        self.console_y = 1 + self.offset

        if self.inventory:
            # Instantiate placeholders
            self.inventory.instantiate_placeholders()
            self.inventory_entries = self.inventory.items
        else:
            self.inventory_entries = self.entities
        self.entries_amount = len(self.inventory_entries)

        if not self.inventory and self.entries_amount:
            self.TITLE = f"Objects at {(self.inventory_entries[0].x, self.inventory_entries[0].y)}"

        self.menu_height = self.height_per_item * self.entries_amount + 6

        if self.menu_height <= 4:
            self.menu_height = 4

        self.menu_width = 24

        console.draw_frame(
            x=self.console_x,
            y=self.console_y,
            width=self.menu_width,
            height=self.menu_height,
            title=self.TITLE,
            clear=True,
            fg=color.menu_text,
            bg=color.nigh_black,
        )

        if not self.entries_amount:
            console.print(self.console_x + 1, self.console_y + 2, text="(Empty)")
            return

        if self.entries_amount > 0:
            for i, entity in enumerate(self.inventory_entries):

                button_x = self.console_x + 2
                button_y = self.console_y + (i*2) + 2
                is_equipped = False
                entity_title = f"{entity.get_title()}"
                button_string = entity_title

                if hasattr(entity, 'inventory'):
                    button_string = f"{entity_title} >"
                if hasattr(entity, "equipped"):
                    item: Equippable = entity
                    is_equipped = item.equipped
                    button_string = f"{entity_title} (E)" if is_equipped else button_string

                self.buttons[i] = {
                    'x': button_x + self.menu_width // 2 - 2,
                    'y': button_y,
                }

                console.print(
                    button_x,
                    button_y,
                    text=f"{chr(entity.char)} ",
                    fg=entity.color,
                    bg=color.nigh_black,
                )
                console.print(
                    button_x + 2,
                    button_y,
                    text=button_string,
                    fg=color.menu_text_inverse if i == self.button_highlight else color.menu_text,
                    bg=color.white if i == self.button_highlight else color.nigh_black,
                )

            if not is_player:
                grab_i = self.entries_amount + 1
                button_x = self.console_x + 2
                button_y = self.console_y + (grab_i*2) + 2

                self.buttons[grab_i] = {
                    'x': button_x + self.menu_width // 2 - 2,
                    'y': button_y,
                }

                console.print(
                    button_x,
                    button_y,
                    text="g) Grab All",
                    fg=color.menu_text_inverse if grab_i == self.button_highlight else color.menu_text,
                    bg=color.white if grab_i == self.button_highlight else color.nigh_black,
                )

    def on_entity_selected(self, entity: Entity) -> Optional[ActionOrHandler]:
        if hasattr(entity, "inventory"):
            return InventoryLootHandler(self.engine, self.engine.player, entity.inventory, console=self.console, offset=1)

    def ev_keydown(
        self, event: libtcodpy.tcod.event.KeyDown
    ) -> Optional[BaseEventHandler]:

        if event.sym == libtcodpy.tcod.event.KeySym.UP:
            self.menu_i = 0 if self.menu_i is None else self.menu_i
            self.menu_i = self.menu_i-1 if self.menu_i > 0 else self.entries_amount
        elif event.sym == libtcodpy.tcod.event.KeySym.DOWN:
            self.menu_i = -1 if self.menu_i is None else self.menu_i
            self.menu_i = self.menu_i+1 if not self.menu_i == self.entries_amount else 0

        self.button_highlight = self.menu_i if self.menu_i is not None else self.button_highlight

        if event.sym == libtcodpy.tcod.event.KeySym.G:
            return self.on_items_selected(self.inventory_entries)
        
        if event.sym in CONFIRM_KEYS:
            item: Item = self.inventory_entries[self.menu_i]
            if hasattr(item, "material"):
                return self.on_item_selected(item)

            entity: Entity = self.inventory_entries[self.menu_i]
            return self.on_entity_selected(entity)

        return super().ev_keydown(event)

    def on_item_selected(self, item: Item) -> Optional[ActionOrHandler]:
        """Called when the user selects a valid item."""
        raise NotImplementedError()
                

    def ev_mousebuttondown(
        self, event: libtcodpy.tcod.event.MouseButtonDown
    ) -> Optional[ActionOrHandler]:
        """Left click confirms a selection."""
        if not event.button == libtcodpy.tcod.event.MouseButton.LEFT:
            return self.resolve_handler()

        for i, item in enumerate(self.inventory_entries):
            if not self.button_highlight == i:
                continue

            if hasattr(item, "material"):
                item: Item = item
                return self.on_item_selected(item)

            entity: Entity = item
            return self.on_entity_selected(entity)
        return self.resolve_handler()

    def ev_mousemotion(
        self, event: libtcodpy.tcod.event.MouseMotion
    ) -> Optional[ActionOrHandler]:
        """Tracks mouse movement"""

        for key in self.buttons:
            button_pt = libtcodpy.tcod.event.Point(self.buttons[key]['x'], self.buttons[key]['y'])
            in_rect = is_mouse_in_rectangle(event, button_pt, self.menu_width, self.button_height)

            if in_rect:
                self.button_highlight = key


class InventoryActivateHandler(InventoryEventHandler):
    """Handle using an inventory item."""

    TITLE = "Inventory"

    def on_item_selected(self, item: Item) -> Optional[ActionOrHandler]:
        if hasattr(item, 'equipped'):
            return actions.EquipAction(self.inventory.parent, item)
        else:
            return item.activate(self.inventory.parent)


class InventoryDropHandler(InventoryEventHandler):
    """Handle dropping an inventory item."""

    TITLE = "Select an item to drop"

    def on_item_selected(self, item: Item) -> Optional[ActionOrHandler]:
        """Drop this item."""
        return actions.DropItem(self.inventory.parent, item)


class InventoryLootHandler(InventoryEventHandler):
    """Handle looting an item."""

    def __init__(self, engine: Engine, looter: Entity, inventory: Inventory = None, entities: List[Entity] = [], console: libtcodpy.tcod.console.Console = None, offset: int = 0):
        super().__init__(engine, inventory, entities, console, offset)

        self.looter = looter
        self.entities = entities

    def on_render(self, console: libtcodpy.tcod.console.Console) -> None:
        """
        Render an inventory menu, which displays the items in the inventory.
        """
        self.console = console if not self.console else self.console
        super().on_render(self.console)
    
    def on_item_selected(self, item: Item) -> Optional[ActionOrHandler]:
        if not self.inventory:
            self.inventory_entries.remove(item)
        return actions.PickupAction(self.looter, item)

    def on_items_selected(self, items: List[Item]) -> Optional[ActionOrHandler]:
        """Called when the user attempts to grab multiple items at once."""
        #TODO Fix bug when too many items are grabbed?
        if not self.inventory:
            for item in reversed(items):
                self.inventory_entries.remove(item)
        return actions.MassPickupAction(self.looter, items)

class SelectIndexHandler(AskUserEventHandler):
    """Handles asking the user for an index on the map."""

    def __init__(self, engine: Engine):
        """Sets the cursor to the player when this handler is constructed."""
        super().__init__(engine)
        player = self.engine.player
        engine.mouse_location = player.x, player.y

    def ev_keydown(self, event: libtcodpy.tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        """Check for key movement or confirmation keys."""
        key = event.sym
        if key in MOVE_KEYS:
            modifier = 1  # Holding modifier keys will speed up key movement.
            if event.mod & (libtcodpy.tcod.event.Modifier.LSHIFT | libtcodpy.tcod.event.Modifier.RSHIFT):
                 modifier *= 5
            if event.mod & (libtcodpy.tcod.event.Modifier.LCTRL | libtcodpy.tcod.event.Modifier.RCTRL):
                 modifier *= 10
            if event.mod & (libtcodpy.tcod.event.Modifier.LALT | libtcodpy.tcod.event.Modifier.RALT):
                 modifier *= 20

            x, y = self.engine.mouse_location
            dest_x, dest_y = MOVE_KEYS[key]
            x += dest_x * modifier
            y += dest_y * modifier
            # Clamp the cursor index to the map size.
            x = max(0, min(x, self.engine.game_map.width - 1))
            y = max(0, min(y, self.engine.game_map.height - 1))
            self.engine.mouse_location = x, y
            return None
        elif key in CONFIRM_KEYS:
            return self.on_index_selected(*self.engine.mouse_location)
        return super().ev_keydown(event)

    def ev_mousebuttondown(
        self, event: libtcodpy.tcod.event.MouseButtonDown
    ) -> Optional[ActionOrHandler]:
        """Left click confirms a selection."""
        if self.engine.game_map.in_bounds(int(event.position.x), int(event.position.y)):
            if event.button == 1:
                return self.on_index_selected(int(event.position.x), int(event.position.y))
        return super().ev_mousebuttondown(event)

    def on_index_selected(self, x: int, y: int) -> Optional[ActionOrHandler]:
        """Called when an index is selected."""
        raise NotImplementedError()


class LookHandler(SelectIndexHandler):
    """Lets the player look around using the keyboard."""

    def on_index_selected(self, x: int, y: int) -> MainGameEventHandler:
        """Return to main handler."""
        player = self.engine.player
        x, y = self.engine.mouse_location

        return actions.BumpAction(player, x, y)

class SingleRangedAttackHandler(SelectIndexHandler):
    """Handles targeting a single enemy. Only the enemy selected will be affected."""

    def __init__(
        self, engine: Engine, callback: Callable[[Tuple[int, int]], Optional[actions.Action]]
    ):
        super().__init__(engine)

        self.callback = callback

    def on_index_selected(self, x: int, y: int) -> Optional[actions.Action]:
        return self.callback((x, y))


class AreaRangedAttackHandler(SelectIndexHandler):
    """Handles targeting an area within a given radius. Any entity within the area will be affected."""

    def __init__(
        self,
        engine: Engine,
        radius: int,
        callback: Callable[[Tuple[int, int]], Optional[actions.Action]],
    ):
        super().__init__(engine)

        self.radius = radius
        self.callback = callback

    def on_render(self, console: libtcodpy.tcod.console.Console) -> None:
        """Highlight the tile under the cursor."""
        super().on_render(console)

        x, y = self.engine.mouse_location

        # Draw a rectangle around the targeted area, so the player can see the affected tiles.
        console.draw_frame(
            x=x - self.radius - 1,
            y=y - self.radius - 1,
            width=self.radius ** 2,
            height=self.radius ** 2,
            fg=color.red,
            clear=False,
        )

    def on_index_selected(self, x: int, y: int) -> Optional[actions.Action]:
        return self.callback((x, y))

class MainGameEventHandler(EventHandler):

    def __init__(self, engine: Engine):
        super().__init__(engine)
        self.mouse_motion = False

    def on_render(self, console: libtcodpy.tcod.console.Console) -> None:
        """Highlight the tile under the cursor."""
        super().on_render(console)

        player = self.engine.player
        if self.mouse_motion and player.is_alive:
            mouse_x, mouse_y = self.engine.mouse_location
            path: List[Tuple] = self.engine.get_path_to(player.ai, mouse_x, mouse_y)
            for x, y in path:
                console.rgb["bg"][x, y] = color.white
                console.rgb["fg"][x, y] = color.black

    def ev_mousemotion(self, event: libtcodpy.tcod.event.MouseMotion) -> None:
        super().ev_mousemotion(event)
        self.mouse_motion = True if event else False
        

    def ev_mousebuttondown(self, event: libtcodpy.tcod.event.MouseMotion) -> Optional[ActionOrHandler]:
        if event.button == libtcodpy.tcod.event.MouseButton.LEFT:
            player = self.engine.player
            x, y = self.engine.mouse_location

            return actions.BumpAction(player, x, y)

    def ev_keydown(self, event: libtcodpy.tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        action: Optional[actions.Action] = None

        key = event.sym
        modifier = event.mod

        player = self.engine.player

        # modifier checks if button is held down
        if key == libtcodpy.tcod.event.KeySym.PERIOD and modifier & (
            libtcodpy.tcod.event.Modifier.LSHIFT | libtcodpy.tcod.event.Modifier.RSHIFT
        ):
            pass

        if key in MOVE_KEYS:
            dest_x, dest_y = MOVE_KEYS[key][0] + player.x, MOVE_KEYS[key][1] + player.y
            action = actions.BumpAction(player, dest_x, dest_y)
        elif key in WAIT_KEYS:
            action = actions.WaitAction(player)

        elif key == libtcodpy.tcod.event.KeySym.ESCAPE:
            raise SystemExit()

        elif key == libtcodpy.tcod.event.KeySym.L:
            return actions.TakeStairsAction(player)

        elif key == libtcodpy.tcod.event.KeySym.V:
            return HistoryViewer(self.engine)

        elif key == libtcodpy.tcod.event.KeySym.G:
            return PickupHandler(self.engine)
        elif key == libtcodpy.tcod.event.KeySym.I:
            return InventoryActivateHandler(self.engine, player.inventory)
        elif key == libtcodpy.tcod.event.KeySym.D:
            return InventoryDropHandler(self.engine, player.inventory)

        elif key == libtcodpy.tcod.event.KeySym.C:
            return CharacterScreenEventHandler(self.engine)

        elif key == libtcodpy.tcod.event.KeySym.PERIOD:
            return LookHandler(self.engine)

        # No valid key was pressed
        return action

    def get_action_or_event(self, unit: Unit):
        entities = self.engine.game_map.get_entities_at_location(unit.x, unit.y)
        for entity in entities:
            if not entity:
                continue
            if not (unit.x == entity.x and unit.y == entity.y):
                continue
            if entity == unit or entity == self.engine.player:
                continue
            if isinstance(entity, Item):
                item: Item = entity
                return actions.PickupAction(unit, item)
                
            return InventoryLootHandler(self.engine, unit, entities=entities)

class GameOverEventHandler(EventHandler):
    def on_quit(self) -> None:
        """Handle exiting out of a finished game."""
        if os.path.exists("savegame.sav"):
            os.remove("savegame.sav")  # Deletes the active save file.
        raise exceptions.QuitWithoutSaving()  # Avoid saving a finished game.

    def ev_quit(self, event: libtcodpy.tcod.event.Quit) -> None:
        self.on_quit()

    def ev_keydown(self, event: libtcodpy.tcod.event.KeyDown) -> None:
        if event.sym == libtcodpy.tcod.event.KeySym.ESCAPE:
            self.on_quit()

CURSOR_Y_KEYS = {
    libtcodpy.tcod.event.KeySym.UP: -1,
    libtcodpy.tcod.event.KeySym.DOWN: 1,
    libtcodpy.tcod.event.KeySym.PAGEUP: -10,
    libtcodpy.tcod.event.KeySym.PAGEDOWN: 10,
}

class HistoryViewer(EventHandler):
    """Print the history on a larger window which can be navigated."""

    def __init__(self, engine: Engine):
        super().__init__(engine)
        self.log_length = len(engine.message_log.messages)
        self.cursor = self.log_length - 1

    def on_render(self, console: libtcodpy.tcod.console.Console) -> None:
        super().on_render(console)  # Draw the main state as the background.

        log_console = libtcodpy.tcod.console.Console(console.width - 6, console.height - 6)

        # Draw a frame with a custom banner title.
        log_console.draw_frame(0, 0, log_console.width, log_console.height)
        log_console.print(
            x=0, y=0, text="┤Message history├",
            width=log_console.width, height=1,
            alignment=libtcodpy.tcod.CENTER,
        )

        # Render the message log using the cursor parameter.
        self.engine.message_log.render_messages(
            log_console,
            1,
            1,
            log_console.width - 2,
            log_console.height - 2,
            self.engine.message_log.messages[: self.cursor + 1],
        )
        log_console.blit(console, 3, 3)

    def ev_keydown(self, event: libtcodpy.tcod.event.KeyDown) -> Optional[MainGameEventHandler]:
        # Fancy conditional movement to make it feel right.
        if event.sym in CURSOR_Y_KEYS:
            adjust = CURSOR_Y_KEYS[event.sym]
            if adjust < 0 and self.cursor == 0:
                # Only move from the top to the bottom when you're on the edge.
                self.cursor = self.log_length - 1
            elif adjust > 0 and self.cursor == self.log_length - 1:
                # Same with bottom to top movement.
                self.cursor = 0
            else:
                # Otherwise move while staying clamped to the bounds of the history log.
                self.cursor = max(0, min(self.cursor + adjust, self.log_length - 1))
        elif event.sym == libtcodpy.tcod.event.KeySym.HOME:
            self.cursor = 0  # Move directly to the top message.
        elif event.sym == libtcodpy.tcod.event.KeySym.END:
            self.cursor = self.log_length - 1  # Move directly to the last message.
        else:  # Any other key moves back to the main game state.
            self.reset_to_handler(MainGameEventHandler(self.engine))
        return None