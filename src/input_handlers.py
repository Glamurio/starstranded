from __future__ import annotations

import os

from typing import Callable, List, Optional, Tuple, TYPE_CHECKING, Union

import layout
import events
from events import Key, Mod, MouseButton, Point
from ui import CENTER

import actions
import color
import exceptions
from utilities import is_mouse_in_rectangle
from entity import Item, Entity
from components.equippable import Equippable

if TYPE_CHECKING:
    from ui import Canvas
    from engine import Engine
    from session import Session
    from components.unit import Unit
    from components.inventory import Inventory
    from crafting import Recipe

MOVE_KEYS = {
    # Arrow keys.
    Key.UP: (0, -1),
    Key.DOWN: (0, 1),
    Key.LEFT: (-1, 0),
    Key.RIGHT: (1, 0),
    Key.HOME: (-1, -1),
    Key.END: (-1, 1),
    Key.PAGEUP: (1, -1),
    Key.PAGEDOWN: (1, 1),
    # Numpad keys.
    Key.KP_1: (-1, 1),
    Key.KP_2: (0, 1),
    Key.KP_3: (1, 1),
    Key.KP_4: (-1, 0),
    Key.KP_6: (1, 0),
    Key.KP_7: (-1, -1),
    Key.KP_8: (0, -1),
    Key.KP_9: (1, -1),
    # Vi keys.
    # Key.h: (-1, 0),
    # Key.j: (0, 1),
    # Key.k: (0, -1),
    # Key.l: (1, 0),
    # Key.y: (-1, -1),
    # Key.u: (1, -1),
    # Key.b: (-1, 1),
    # Key.n: (1, 1),
}

CONFIRM_KEYS = {
    Key.RETURN,
    Key.KP_ENTER,
}

WAIT_KEYS = {
    Key.SPACE,
    Key.KP_5,
    Key.CLEAR,
}

def screen_to_world(engine: Engine, position) -> Optional[Tuple[int, int]]:
    """World tile under screen cell `position`, or None outside the map viewport."""
    camera = engine.camera
    sx, sy = int(position[0]), int(position[1])
    if not camera.on_screen(sx, sy):
        return None
    return camera.to_world(sx, sy)


def highlight_world(engine: Engine, canvas: Canvas, x: int, y: int, wash=color.white) -> None:
    """Highlight world tile (x, y) if it is in the map viewport."""
    camera = engine.camera
    sx, sy = camera.to_screen(x, y)
    if camera.on_screen(sx, sy):
        canvas.highlight(sx, sy, wash)


def draw_entity_icon(canvas: Canvas, x: int, y: int, entity: Entity) -> None:
    """Draw the entity's sprite, tinted with its own colour, into cell (x, y) (menus use this as a list icon)."""
    canvas.sprite(x, y, entity.sprite_id, entity.color, entity.flipped)


ActionOrHandler = Union[actions.Action, "BaseEventHandler"]
"""An event handler return value which can trigger an action or switch active handlers.

If a handler is returned then it will become the active handler for future events.
If an action is returned it will be attempted and if it's valid then
MainGameEventHandler will become the active handler.
"""


class BaseEventHandler(events.EventDispatch):

    def __init__(self, session: Optional[Session] = None) -> None:
        super().__init__()
        import session as session_module
        self._session = session or session_module.detached()
        self.on_init()

    @property
    def session(self) -> Session:
        """The UI session (window, canvas, handler stack); engine handlers use their engine's."""
        return self._session

    def on_init(self):
        """Function that runs after init"""
        pass

    def handle_events(self, event: events.Event) -> BaseEventHandler:
        """Handle an event and return the next active event handler."""
        state = self.dispatch(event)
        if isinstance(state, BaseEventHandler):
            return state
        assert not isinstance(state, actions.Action), f"{self!r} can not handle actions."
        return self

    def on_render(self, canvas: Canvas) -> None:
        raise NotImplementedError()

    def ev_quit(self, event: events.Quit) -> Optional[actions.Action]:
        raise SystemExit()

class PopupMessage(BaseEventHandler):
    """Display a popup text window."""

    def __init__(self, parent_handler: BaseEventHandler, text: str):
        self.parent = parent_handler
        self.text = text

    def on_render(self, canvas: Canvas) -> None:
        """Render the parent and dim the result, then print the message on top."""
        self.parent.on_render(canvas)
        canvas.dim()

        canvas.print(
            canvas.width // 2,
            canvas.height // 2,
            text=self.text,
            fg=color.white,
            bg=color.black,
            alignment=CENTER,
        )

    def ev_keydown(self, event: events.KeyDown) -> Optional[BaseEventHandler]:
        """Any key returns to the parent handler."""
        return self.parent


class EventHandler(BaseEventHandler):
    def __init__(self, engine: Engine):
        self.engine = engine

    @property
    def session(self) -> Session:
        return self.engine.session

    def reset_to_handler(self, handler: EventHandler):
        """Resets active handler to handler provided"""
        self.session.reset(handler)

    def resolve_handler(self) -> EventHandler:
        """Resolves and returns current handler and switches to the next in stack"""
        handler = self.session.handlers.pop()

        if not len(self.session.handlers):
            self.reset_to_handler(MainGameEventHandler(self.engine))

        return handler
            

    def handle_events(self, event: events.Event) -> BaseEventHandler:
        """Handle events for input handlers with an engine."""
        action_or_state = self.dispatch(event)

        if isinstance(action_or_state, BaseEventHandler):
            self.session.push(action_or_state) # Add handler to stack

        if isinstance(action_or_state, actions.Action) and self.handle_action(action_or_state):
            # A valid action was performed.
            if not self.engine.player.is_alive:
                # The player was killed sometime during or after the action.
                return GameOverEventHandler(self.engine)
            elif self.engine.player.level.requires_level_up:
                return LevelUpEventHandler(self.engine)

            if not len(self.session.handlers):
                self.reset_to_handler(MainGameEventHandler(self.engine)) # Return to the main handler.

        if len(self.session.handlers):
            return self.session.handlers[-1] # Switch to most recent handler in stack

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
                self.session.render(self)
        except exceptions.Impossible as exc:
            self.engine.message_log.add_message(exc.args[0], color.impossible)
            return False  # Skip enemy turn on exceptions.

        return True

    def ev_mousemotion(self, event: events.MouseMotion) -> None:
        world_xy = screen_to_world(self.engine, event.position)
        if world_xy is not None and self.engine.game_map.in_bounds(*world_xy):
            self.engine.mouse_location = Point(*world_xy)

    def on_render(self, canvas: Canvas) -> None:
        self.engine.render(canvas)


class AskUserEventHandler(EventHandler):
    """Handles user input for actions which require special input."""

    def ev_keydown(self, event: events.KeyDown) -> Optional[ActionOrHandler]:
        """By default any key exits this input handler."""
        if event.sym in {  # Ignore specific keys
            Key.LSHIFT,
            Key.RSHIFT,
            Key.LCTRL,
            Key.RCTRL,
            Key.LALT,
            Key.RALT,
            Key.UP,
            Key.DOWN
        }:
            return None
        if event.sym in CONFIRM_KEYS:
            return None
        return self.on_exit()

    def ev_mousebuttondown(
        self, event: events.MouseButtonDown
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
        self.target_location = Point(0, 0)

    def on_render(self, canvas: Canvas) -> None:
        super().on_render(canvas)

        player = self.engine.player
        mouse_x, mouse_y = self.engine.mouse_location
        distance = self.engine.distance((player.x, player.y), (mouse_x, mouse_y))
        path = self.engine.get_path_to(player, mouse_x, mouse_y)
        tile = path.pop(0) if path else (player.x, player.y)
        if distance <= 1:
            self.target_location = Point(mouse_x, mouse_y)
            highlight_world(self.engine, canvas, mouse_x, mouse_y, color.white)
        else:
            self.target_location = Point(tile[0], tile[1])
            highlight_world(self.engine, canvas, tile[0], tile[1], color.white)

    def ev_mousebuttondown(
        self, event: events.MouseButtonDown
    ) -> Optional[ActionOrHandler]:
        """By default any mouse click exits this input handler."""
        if event.button == MouseButton.LEFT:
            targets = self.engine.game_map.stack_at(self.target_location.x, self.target_location.y)
            return self.on_tile_selected(targets)

    def ev_keydown(self, event: events.KeyDown) -> Optional[ActionOrHandler]:
        if event.sym == Key.G or event.sym == Key.RETURN:
            targets = self.engine.game_map.stack_at(self.target_location.x, self.target_location.y)
            return self.on_tile_selected(targets)

    def on_tile_selected(self, targets: List[Entity]) -> Optional[ActionOrHandler]:
        """Called when the user selects a valid item."""

        if self.engine.player in targets:
            targets.remove(self.engine.player)
        if not targets:
            return self.on_exit()
        if len(targets) == 1:
            target = targets[0]
            if isinstance(target, Item):
                return actions.PickupAction(self.engine.player, target)

        self.resolve_handler()
        return InventoryLootHandler(self.engine, self.engine.player, entities=targets)
        


class CharacterScreenEventHandler(AskUserEventHandler):
    TITLE = "Character Information"

    def on_render(self, canvas: Canvas) -> None:
        super().on_render(canvas)

        if self.engine.camera.to_screen(self.engine.player.x, self.engine.player.y)[0] <= 30:
            x = 40
        else:
            x = 0

        y = 0

        width = len(self.TITLE) + 4

        canvas.draw_frame(
            x=x,
            y=y,
            width=width,
            height=7,
            title=self.TITLE,
            clear=True,
            fg=(255, 255, 255),
            bg=(0, 0, 0),
        )

        canvas.print(
            x=x + 1, y=y + 1, text=f"Level: {self.engine.player.level.current_level}"
        )
        canvas.print(
            x=x + 1, y=y + 2, text=f"XP: {self.engine.player.level.current_xp}"
        )
        canvas.print(
            x=x + 1,
            y=y + 3,
            text=f"XP for next Level: {self.engine.player.level.experience_to_next_level}",
        )

        canvas.print(
            x=x + 1, y=y + 4, text=f"Attack: {self.engine.player.power}"
        )
        canvas.print(
            x=x + 1, y=y + 5, text=f"Defense: {self.engine.player.defense}"
        )


class LevelUpEventHandler(AskUserEventHandler):
    TITLE = "Level Up"

    def on_render(self, canvas: Canvas) -> None:
        super().on_render(canvas)

        x = 0
        y = 0

        canvas.draw_frame(
            x=x,
            y=y,
            width=35,
            height=8,
            title=self.TITLE,
            clear=True,
            fg=(255, 255, 255),
            bg=(0, 0, 0),
        )

        canvas.print(x=x + 1, y=1, text="Congratulations! You level up!")
        canvas.print(x=x + 1, y=2, text="Select an attribute to increase.")

        canvas.print(
            x=x + 1,
            y=4,
            text=f"a) Constitution (+20 HP, from {self.engine.player.max_hp})",
        )
        canvas.print(
            x=x + 1,
            y=5,
            text=f"b) Strength (+1 attack, from {self.engine.player.power})",
        )
        canvas.print(
            x=x + 1,
            y=6,
            text=f"c) Agility (+1 defense, from {self.engine.player.defense})",
        )

    def ev_keydown(self, event: events.KeyDown) -> Optional[ActionOrHandler]:
        player = self.engine.player
        key = event.sym
        index = key - Key.A

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
        self, event: events.MouseButtonDown
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
    inventory_entries: List[Item]
    entries_amount: int = 0

    buttons: dict
    button_height: int = 2
    button_highlight: str = None

    def __init__(self, engine: Engine, inventory: Inventory = None, entities: List[Entity] = None, canvas: Canvas = None, offset: int = 0):
        super().__init__(engine)
        self.inventory_entries = []
        self.buttons = {}
        # If there's only one entity at target location, treat it as single inventory
        entity: Entity = entities[0] if entities and len(entities) == 1 else None
        self.inventory = entity.inventory if entity and not inventory else inventory
        
        self.entities = entities
        self.offset = offset
        self.canvas = canvas

    def on_render(self, canvas: Canvas) -> None:
        """
        Render an inventory menu, which displays the items in the inventory.
        """
        is_player = False
        prev_index = self.session.handlers.index(self) - 1
        parent = self.session.handlers[prev_index] if prev_index >= 0 else None

        if parent: 
            parent.on_render(canvas)
        else:
            super().on_render(canvas)
        
        if self.inventory:
            self.TITLE = f"{self.inventory.parent.get_title()}"

        if self.inventory and self.inventory.parent == self.engine.player:
            is_player = True
            self.TITLE = f"Inventory"

        self.console_x = layout.SIDE_PANEL_WIDTH * (1 + self.offset)
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

        canvas.draw_frame(
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
            canvas.print(self.console_x + 1, self.console_y + 2, text="(Empty)")
            return

        if self.entries_amount > 0:
            for i, entity in enumerate(self.inventory_entries):

                button_x = self.console_x + 2
                button_y = self.console_y + (i*2) + 2
                is_equipped = False
                entity_title = f"{entity.get_title()}"
                button_string = entity_title

                if entity.has_inventory:
                    button_string = f"{entity_title} >"
                if isinstance(entity, Equippable):
                    item: Equippable = entity
                    is_equipped = item.equipped
                    button_string = f"{entity_title} (E)" if is_equipped else button_string

                self.buttons[i] = {
                    'x': button_x + self.menu_width // 2 - 2,
                    'y': button_y,
                }

                canvas.fill(button_x, button_y, 1, 1, color.nigh_black)
                draw_entity_icon(canvas, button_x, button_y, entity)
                canvas.print(
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

                canvas.print(
                    button_x,
                    button_y,
                    text="g) Grab All",
                    fg=color.menu_text_inverse if grab_i == self.button_highlight else color.menu_text,
                    bg=color.white if grab_i == self.button_highlight else color.nigh_black,
                )

    def on_entity_selected(self, entity: Entity) -> Optional[ActionOrHandler]:
        if entity.has_inventory:
            return InventoryLootHandler(self.engine, self.engine.player, entity.inventory, canvas=self.canvas, offset=1)

    def ev_keydown(
        self, event: events.KeyDown
    ) -> Optional[BaseEventHandler]:

        if event.sym == Key.UP:
            self.menu_i = 0 if self.menu_i is None else self.menu_i
            self.menu_i = self.menu_i-1 if self.menu_i > 0 else self.entries_amount
        elif event.sym == Key.DOWN:
            self.menu_i = -1 if self.menu_i is None else self.menu_i
            self.menu_i = self.menu_i+1 if not self.menu_i == self.entries_amount else 0

        self.button_highlight = self.menu_i if self.menu_i is not None else self.button_highlight

        if event.sym == Key.G:
            return self.on_items_selected(self.inventory_entries)
        
        if event.sym in CONFIRM_KEYS:
            item: Item = self.inventory_entries[self.menu_i]
            if isinstance(item, Item):
                return self.on_item_selected(item)

            entity: Entity = self.inventory_entries[self.menu_i]
            return self.on_entity_selected(entity)

        return super().ev_keydown(event)

    def on_item_selected(self, item: Item) -> Optional[ActionOrHandler]:
        """Called when the user selects a valid item."""
        raise NotImplementedError()
                

    def ev_mousebuttondown(
        self, event: events.MouseButtonDown
    ) -> Optional[ActionOrHandler]:
        """Left click confirms a selection."""
        if not event.button == MouseButton.LEFT:
            return self.resolve_handler()

        for i, item in enumerate(self.inventory_entries):
            if not self.button_highlight == i:
                continue

            if isinstance(item, Item):
                return self.on_item_selected(item)

            entity: Entity = item
            return self.on_entity_selected(entity)
        return self.resolve_handler()

    def ev_mousemotion(
        self, event: events.MouseMotion
    ) -> Optional[ActionOrHandler]:
        """Tracks mouse movement"""

        for key in self.buttons:
            button_pt = Point(self.buttons[key]['x'], self.buttons[key]['y'])
            in_rect = is_mouse_in_rectangle(event, button_pt, self.menu_width, self.button_height)

            if in_rect:
                self.button_highlight = key


class CraftingMenuHandler(AskUserEventHandler):
    """Display available recipes and let the player craft items."""

    TITLE = "Crafting"

    def __init__(self, engine: Engine):
        super().__init__(engine)
        from crafting import RECIPES
        self.recipes = RECIPES
        self.menu_i: int = 0
        self.button_highlight: int = 0

    def on_render(self, canvas: Canvas) -> None:
        super().on_render(canvas)

        x = layout.SIDE_PANEL_WIDTH
        y = 1
        width = 36
        height = len(self.recipes) * 3 + 4

        canvas.draw_frame(
            x=x, y=y,
            width=width, height=height,
            title=self.TITLE,
            clear=True,
            fg=color.menu_text,
            bg=color.nigh_black,
        )

        player_inv = self.engine.player.inventory

        for i, recipe in enumerate(self.recipes):
            can_craft = recipe.can_craft(player_inv)
            recipe_y = y + 2 + (i * 3)

            name_color = color.menu_text if can_craft else color.impossible
            highlight_bg = color.white if i == self.button_highlight else color.nigh_black
            highlight_fg = color.black if i == self.button_highlight else name_color

            canvas.print(
                x=x + 2, y=recipe_y,
                text=recipe.name,
                fg=highlight_fg,
                bg=highlight_bg,
            )

            parts = []
            for item_type, count in recipe.ingredients.items():
                available = sum(
                    1 for item in player_inv.items
                    if item.object_type == item_type
                )
                parts.append(f"{item_type} x{count} ({available}/{count})")

            ingredient_str = ", ".join(parts)
            canvas.print(
                x=x + 4, y=recipe_y + 1,
                text=ingredient_str,
                fg=color.white if can_craft else color.impossible,
            )

    def ev_keydown(self, event: events.KeyDown) -> Optional[ActionOrHandler]:
        key = event.sym

        if key == Key.UP:
            self.button_highlight = max(0, self.button_highlight - 1)
            return None
        elif key == Key.DOWN:
            self.button_highlight = min(len(self.recipes) - 1, self.button_highlight + 1)
            return None
        elif key in CONFIRM_KEYS:
            recipe = self.recipes[self.button_highlight]
            if recipe.can_craft(self.engine.player.inventory):
                return actions.CraftAction(self.engine.player, recipe)
            else:
                self.engine.message_log.add_message(
                    "You don't have enough materials.", color.impossible
                )
                return None

        return super().ev_keydown(event)

    def ev_mousebuttondown(self, event: events.MouseButtonDown) -> Optional[ActionOrHandler]:
        return None
class InventoryActivateHandler(InventoryEventHandler):
    """Handle using an inventory item."""

    TITLE = "Inventory"

    def on_item_selected(self, item: Item) -> Optional[ActionOrHandler]:
        if isinstance(item, Equippable):
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

    def __init__(self, engine: Engine, looter: Entity, inventory: Inventory = None, entities: Optional[List[Entity]] = None, canvas: Canvas = None, offset: int = 0):
        entities = [] if entities is None else entities
        super().__init__(engine, inventory, entities, canvas, offset)

        self.looter = looter
        self.entities = entities

    def on_render(self, canvas: Canvas) -> None:
        """
        Render an inventory menu, which displays the items in the inventory.
        """
        self.canvas = canvas if not self.canvas else self.canvas
        super().on_render(self.canvas)
    
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

    def ev_keydown(self, event: events.KeyDown) -> Optional[ActionOrHandler]:
        """Check for key movement or confirmation keys."""
        key = event.sym
        if key in MOVE_KEYS:
            modifier = 1  # Holding modifier keys will speed up key movement.
            if event.mod & (Mod.LSHIFT | Mod.RSHIFT):
                 modifier *= 5
            if event.mod & (Mod.LCTRL | Mod.RCTRL):
                 modifier *= 10
            if event.mod & (Mod.LALT | Mod.RALT):
                 modifier *= 20

            x, y = self.engine.mouse_location
            dest_x, dest_y = MOVE_KEYS[key]
            x += dest_x * modifier
            y += dest_y * modifier
            # Clamp the cursor index to the map size.
            camera = self.engine.camera  # the cursor stays on screen
            x = max(camera.x0, min(x, camera.x0 + camera.width - 1))
            y = max(camera.y0, min(y, camera.y0 + camera.height - 1))
            self.engine.mouse_location = x, y
            return None
        elif key in CONFIRM_KEYS:
            return self.on_index_selected(*self.engine.mouse_location)
        return super().ev_keydown(event)

    def ev_mousebuttondown(
        self, event: events.MouseButtonDown
    ) -> Optional[ActionOrHandler]:
        """Left click confirms a selection."""
        world_xy = screen_to_world(self.engine, event.position)
        if world_xy is not None and self.engine.game_map.in_bounds(*world_xy):
            if event.button == 1:
                return self.on_index_selected(*world_xy)
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


def area_frame_rect(x: int, y: int, radius: int) -> Tuple[int, int, int, int]:
    """Return `(x, y, width, height)` of a frame that encloses the area affected around `(x, y)`.

    The affected area spans `2 * radius + 1` tiles per axis (`x - radius` .. `x + radius`); the frame
    is drawn on the ring of tiles just outside it, so it is `2 * radius + 3` wide/high.
    """
    size = 2 * radius + 3
    return x - radius - 1, y - radius - 1, size, size


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

    def on_render(self, canvas: Canvas) -> None:
        """Highlight the tile under the cursor."""
        super().on_render(canvas)

        x, y = self.engine.camera.to_screen(*self.engine.mouse_location)

        # Draw a rectangle around the targeted area, so the player can see the affected tiles.
        frame_x, frame_y, width, height = area_frame_rect(x, y, self.radius)
        canvas.draw_frame(
            x=frame_x,
            y=frame_y,
            width=width,
            height=height,
            fg=color.red,
            clear=False,
        )

    def on_index_selected(self, x: int, y: int) -> Optional[actions.Action]:
        return self.callback((x, y))

class MainGameEventHandler(EventHandler):

    def __init__(self, engine: Engine):
        super().__init__(engine)
        self.mouse_motion = False

    def on_render(self, canvas: Canvas) -> None:
        """Highlight the tile under the cursor."""
        super().on_render(canvas)

        player = self.engine.player
        if self.mouse_motion and player.is_alive:
            mouse_x, mouse_y = self.engine.mouse_location
            path: List[Tuple] = self.engine.get_path_to(player, mouse_x, mouse_y)
            for x, y in path:
                highlight_world(self.engine, canvas, x, y, color.white)

    def ev_mousemotion(self, event: events.MouseMotion) -> None:
        super().ev_mousemotion(event)
        self.mouse_motion = True if event else False
        

    def ev_mousebuttondown(self, event: events.MouseMotion) -> Optional[ActionOrHandler]:
        if event.button == MouseButton.LEFT:
            player = self.engine.player
            x, y = self.engine.mouse_location

            return actions.BumpAction(player, x, y)

    def ev_keydown(self, event: events.KeyDown) -> Optional[ActionOrHandler]:
        action: Optional[actions.Action] = None

        key = event.sym
        modifier = event.mod

        player = self.engine.player

        # modifier checks if button is held down
        if key == Key.PERIOD and modifier & (
            Mod.LSHIFT | Mod.RSHIFT
        ):
            pass

        if key in MOVE_KEYS:
            dest_x, dest_y = MOVE_KEYS[key][0] + player.x, MOVE_KEYS[key][1] + player.y
            action = actions.BumpAction(player, dest_x, dest_y)
        elif key in WAIT_KEYS:
            action = actions.WaitAction(player)

        elif key == Key.ESCAPE:
            raise SystemExit()

        elif key == Key.L:
            return actions.TakeStairsAction(player)
        elif key == Key.PERIOD and modifier & (Mod.LSHIFT | Mod.RSHIFT):
            return actions.TakeStairsAction(player, -1)
        elif key == Key.COMMA and modifier & (Mod.LSHIFT | Mod.RSHIFT):
            return actions.TakeStairsAction(player, 1)
        elif key == Key.LESS:  # the "<" / ">" key of ISO keyboards (Shift gives ">")
            return actions.TakeStairsAction(player, -1 if modifier & (Mod.LSHIFT | Mod.RSHIFT) else 1)

        elif key == Key.V:
            return HistoryViewer(self.engine)

        elif key == Key.G:
            return PickupHandler(self.engine)
        elif key == Key.I:
            return InventoryActivateHandler(self.engine, player.inventory)
        elif key == Key.D:
            return InventoryDropHandler(self.engine, player.inventory)
        elif key == Key.R:
            return CraftingMenuHandler(self.engine)
        elif key == Key.F:
            return actions.InteractAction(player)

        elif key == Key.C:
            return CharacterScreenEventHandler(self.engine)

        elif key == Key.PERIOD:
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
        import shutil
        if os.path.isdir("savegame"):
            shutil.rmtree("savegame")  # Deletes the active save.
        elif os.path.exists("savegame"):
            os.remove("savegame")
        raise exceptions.QuitWithoutSaving()  # Avoid saving a finished game.

    def ev_quit(self, event: events.Quit) -> None:
        self.on_quit()

    def ev_keydown(self, event: events.KeyDown) -> None:
        if event.sym == Key.ESCAPE:
            self.on_quit()

CURSOR_Y_KEYS = {
    Key.UP: -1,
    Key.DOWN: 1,
    Key.PAGEUP: -10,
    Key.PAGEDOWN: 10,
}

class HistoryViewer(EventHandler):
    """Print the history on a larger window which can be navigated."""

    def __init__(self, engine: Engine):
        super().__init__(engine)
        self.log_length = len(engine.message_log.messages)
        self.cursor = self.log_length - 1

    def on_render(self, canvas: Canvas) -> None:
        super().on_render(canvas)  # Draw the main state as the background.

        x, y, width, height = 3, 3, canvas.width - 6, canvas.height - 6

        # Draw a frame with a custom banner title.
        canvas.draw_frame(x, y, width, height, title="Message history", fg=color.white, bg=color.black)

        # Render the message log using the cursor parameter.
        self.engine.message_log.render_messages(
            canvas,
            x + 1,
            y + 1,
            width - 2,
            height - 2,
            self.engine.message_log.messages[: self.cursor + 1],
        )

    def ev_keydown(self, event: events.KeyDown) -> Optional[MainGameEventHandler]:
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
        elif event.sym == Key.HOME:
            self.cursor = 0  # Move directly to the top message.
        elif event.sym == Key.END:
            self.cursor = self.log_length - 1  # Move directly to the last message.
        else:  # Any other key moves back to the main game state.
            self.reset_to_handler(MainGameEventHandler(self.engine))
        return None
    
class PlaceConstructableHandler(SelectIndexHandler):
    """Lets the player pick a tile to place a constructable item."""

    def __init__(self, engine: Engine, item):
        super().__init__(engine)
        self.item = item
        # Start cursor at player position
        self.engine.mouse_location = engine.player.x, engine.player.y

    def on_render(self, canvas: Canvas) -> None:
        super().on_render(canvas)
        # Highlight valid placement tiles (current + adjacent)
        px, py = self.engine.player.x, self.engine.player.y
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                tx, ty = px + dx, py + dy
                if self.engine.game_map.in_bounds(tx, ty):
                    highlight_world(self.engine, canvas, tx, ty, color.menu_text)

    def on_index_selected(self, x: int, y: int) -> Optional[ActionOrHandler]:
        return actions.PlaceConstructableAction(self.engine.player, self.item, x, y)