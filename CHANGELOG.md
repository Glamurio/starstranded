# Changelog

Behavior changes made by the modernization project (branch `modernize`). Pure refactors are not listed.

## Cooking, water and sleep round, 21 Oct 2026
- Fixed: the world map no longer zooms with the cursor. It keeps a fixed block size and scrolls by whole chunks when the cursor reaches the edge (Home recentres).
- Changed: inventory, character, codex, recipe and cooking screens cover the full height of the left side.
- Changed: healing is 1 point per 15 turns (not while poisoned).
- Changed: a body of water takes its colour and kind once, from the biome of its source; rivers keep it all the way down. Shores fade with a depth gradient; lily pads take the chunk's plant colours. Lava stays orange.
- New: bedroll (many fibres). It wears out after a few nights. Sleeping asks how long to sleep.
- New: heat and cold build up in a body-heat meter shown in the HUD (Hypothermia / Hyperthermia). At the maximum you die.
- New: cooking. Food has some of six flavours (sweet, spicy, salty, sour, savory, bitter), never all. Raw food gives only a fraction of its value; cooking gives far more. Meat restores more than other food. Some food is toxic raw or always. Humans must cook meat or it poisons them.
- New: stews (meat + liquid), soups (liquid + fruit), skewers (meat or fruit + branch), with optional herbs or flowers for seasoning; each comes in flavour variants. Cook by using a lit campfire. Ovens and fish are not in yet.

## Survival, map and polish round, 20 Oct 2026
- Changed: thirst empties in about 3 days and hunger in about 7. Neither costs health any more: at 0 you die. Heat and cold no longer drain through hit points either.
- New: the death message and the ending name the cause: the killer and the damage type, or starvation, thirst, poison, cold, suffocation.
- Fixed: toxic fruit and blooms really poison whoever eats them (toxicity was never applied). Fruit called "rot spore" is always toxic.
- Fixed: a bloom shares the sprite of its flower; the flower text reads "Its bud is poisonous" instead of "It bears ...".
- Changed: grey is judged more strictly in colour names; mushrooms and other plants unknown to the provisional-name table are named for what they look like ("glowing mushroom", "tall grass").
- New: once a fruit is known to come from a plant (picked from it or scanned), the plant lists "fruit: ???" and fills it in with what you learn about the fruit.
- Changed: inventory, character, codex and recipe screens open at the left edge (58 wide) so the log on the right stays visible.
- New: hovering a skill on the character sheet shows what it does, how to raise it and the practice progress.
- Changed: the world map draws a picture for every seen block (10x10 tiles) of a chunk: water, the commonest tree, settlement, rock, thicket or ground, instead of one colour square per chunk. Places and your own mark sit on their real tile. Older saves keep colour squares until the chunk is seen again.


## Flower cap, 20 Oct 2026
- Changed: each chunk remembers how many flowers its ground grew with; picked flowers come back one at a time (a 4% chance per chunk every 20 turns, out of sight) but never beyond that number.

## Variants removed, 20 Oct 2026
- Removed: hot/cold/wet/dry variants of a biome (their ground tint, vegetation change and temperature offset, and the code behind them). A biome is only its biome.

## Usability round, 20 Oct 2026
- Fixed: a fruit inside a plant can be scanned from the scanner's range (it was measured from the wrong place); unscanned blooms read "bud" or "blossom" again.
- Changed: a flower is gone once its bloom is picked; new flowers sprout now and then (out of sight) where their species grow.
- Fixed: grabbing a stack takes the whole stack and only reports what really went into the pack; the inventory title shows how full it is.
- Fixed: scattered bones, skulls and pebbles that were picked up can be dropped; "wire of drawn wire" reads "drawn wire".
- New: right click on the map opens a menu of what can be done there (attack, grab, scan, look inside, walk). The keys are unchanged.
- Changed: a key press or a click stops a walk (click to walk, or a long path).
- Changed: biome names stay plain ("Savanna").
- Changed: crafting icons are white until a material is chosen, then take the colour of the material that colours the tool.
- Changed: a scan lists every property of a material (also low ones); when a skill rises from scanning, the log says so (that is why a rescan can suddenly read more).
- Changed: creatures get real names ("smoke scuttler", "dread prowler") instead of "<colour> <animal>"; colour words are for the unscanned name.

## Biome regions, second round, 20 Oct 2026
- Changed: regions are much larger (about 300-tile cells, grouped into provinces that favour one family), with soft borders 34 tiles wide, so similar biomes sit together and the odd one out is a thin transition.
- Changed: caves follow the surface region above them, with the same blended borders (colour lerp), instead of their own small noise patches. Hovering a cave tile now describes its contents, not its biome.
- Changed: hot/cold/wet/dry variants and water colours fade in gradually (no stark grid of patches).
- Changed: bridges, roads and floors keep their own material colour; remembered-but-unseen tiles are far darker; every sprite has a 1 pixel black outline.
- New: the HUD shows the current biome under the music line; "Borderless window" setting (and tabbing out no longer minimises the game).
- Fixed: the sprite editor lists the ground textures, cityscape, scenery and cave fauna sprites again.
- Fixed: loose stones no longer land on another stone or on scenery.

## Biome regions round, 20 Oct 2026
- New: the world is divided into large regions (about 120 x 120 tiles) of 72 biomes in 12 families, blended at their borders; landmarks are removed. Ground, plants, scenery, animals, music and caves follow the region.
- New: hot, cold, wet and dry variants of a biome (tint, vegetation, temperature, name).
- New: abandoned cities (street grids, buildings, towers, wrecks, lamp posts) in urban biomes. Removed: settlers and every populated settlement; farms and hamlets are abandoned and never stand in cities.
- New: points of interest in every biome (standing stones, bone piles, graveyards, wreck fields, ruined cabins, research outposts, abandoned farm plots) built from the region's own stone and timber.
- Changed: cave biomes follow the surface biome above them (less so with depth); Selenites stay rare.
- Changed: old saves no longer load.

## World readability round, 19 Oct 2026
- Farms: fences are breakable wooden fence entities, farmhouses have timber walls, and the field rows are real harvestable, regrowing crop plants (never found wild).
- Changed: lakes, rivers and seas come in a wide range of vivid colours again (blue, teal, green, yellow, violet, magenta); a lake keeps its colour and different places differ.
- Changed: ground colours ease into each other over a few tiles at biome borders instead of a hard line.
- Changed: plants, fruit and creatures are named with the real name of their colour; creatures are named for the animal they look like.
- Changed: the grazer is drawn as a deer; hoppers are less common and each biome has different leading animals.
- New: the world map shows ships, pods, ruins and the gate with their own pictures.
- Changed: roads are only laid when they can be walked end to end (no roads that stop at a cliff or lake; bridges only over short clean water).
- New: seven kinds of cave (barren, volcanic, ice, crystal, fungal, flooded, precursor ruins) with their own colours and cave animals; Selenites are now rare visitors.
- New: wildlife recovers where it was hunted out and herds breed, also while you are away.
- New: music follows the biome as well as the landmark, uses more of the tracks, and crossfades between tracks.

## Session, sight and faction round, 19 Oct 2026
- Fixed: Continue after Save & Quit to Main Menu no longer throws you straight back to the menu.
- Fixed: music stops when you leave a game for the menu and starts fresh in the next one.
- Changed: music is half as loud by default; combat music ends one second after the last enemy is out of view.
- New: Settings in the Esc pause menu; "Now Playing" in the HUD.
- New: factions (Wildlife, Federation, Robot); humanoids are the Federation. Hostiles attack the nearest enemy-faction creature they can see (ten tiles, clear line), head for the last seen spot for a while and give up; they no longer home in on you from across the map.
- New: peaceful animals hit back when attacked and cornered, and run otherwise.
- New: settlers, rations and medkits in farms and towns; no wild plants, stones or animals on built ground; D drops a whole stack.

## Landmark follow-up round, 19 Oct 2026
- Fixed: crash on old saves with `fungal` / `volcanic` / `crystalline` biomes; the music folder resolves to `data/music` again, so music plays.
- New: clicking a tile at the edge of the chunk walks off it, so mouse-only play can leave the chunk.
- New: bridges run horizontally, vertically and several tiles long; farms (fields, fences, crops) and small towns (streets, houses) appear in the world.
- Changed: foliage is less vibrant and partly transparent; rock is always pink to red; wreckage is rotated by random multiples of 45 degrees.
- New: scanning corpses, scan and drop from any inventory (keys `s` / `d` and clickable), stacked items read "grey branch x5", generated names are lower case.
- Changed: trees almost never drop fruit or branches and never into rock.
- New: God Mode shows the whole view and creatures ignore you.
- New: swimming (breath meter on the HUD, Selenites last longer, twice the time, wet for a while afterwards).
- Removed: the skull-and-cross drawn over corpses.
- Changed: animals. Landmark species are generated from the baseline creatures with the landmark's traits (no more hand-written ones); most animals are passive, only hunters, stalkers and serpents attack, and they hit much harder. New Combat skill. Selenites are humanoids; new generic Robot enemy.

## World exploration round, 19 Oct 2026
- New (debug runs only, `--debug`): God Mode on F10 with Ctrl / Alt jumps; see the README.
- New: continents, seas and mountain ranges (every seed's map changes); the landing site is always dry, mild and has a pond nearby; the air is colder on high ground.
- New: rivers (springs and thaw streams that flow downhill, merge, widen and end in the sea or a lake; wade the narrow ones, look for fords), wetlands along water, and beaches.
- New: hot springs in volcanic country (scald waders; boil before drinking) and fjords where rivers meet the sea through mountains.
- New: landmarks, large regions on top of the climate (mushroom forest, cactus desert, crystal badlands, volcanic mountains, decaying landscape, flowering meadow) with their own ground, plant cover, stones and warmth; none near the landing site. The volcanic / crystalline / fungal biomes are removed.
- New: seven plants and seven animals that live only in one landmark (the fungal tree now grows only in mushroom forests).
- Changed: ground cover no longer appears under trees; tree layouts differ from before for the same seed (the roll is now chunk-independent).

## Fixes after the review, 19 Oct 2026
- Fixed: every step logged "That way is blocked."; dying or reaching an ending during a walk is now noticed at once and stops the walk.
- Fixed: dying with a full pack no longer breaks the death (no "You died!", game-over a turn late).
- Changed: hunger, thirst, poison and heat now run for every minute of a long action, so crafting, mining and healing cost hunger and thirst like walking does.
- Changed: eating a food from the pack takes a turn.
- Fixed: the contract board stays at three open contracts; mined ore that does not fit lands at your feet; a wild creature forced into acid no longer crashes.
- Fixed: planet creatures and fruit in caves keep sharing the planet's definitions after saving or unloading (smaller cave chunk files).

## Feedback round, 19 Oct 2026
- New: right-hand HUD panel with the log, 10-segment bars and engraved borders; selectable colour themes (default sci-fi) in Settings.
- New: Esc menu with Save & Quit to Main Menu / Save & Quit Game; menus are clickable; the death screen keeps mouse look; rock walls can be hovered and mined.
- New: foreign-language names show their English name in italics when hovered; Selenite names follow the `voyage_selenite.cfg` syllables.
- New: blood puddles under corpses (species blood colour); animals have fur, feathers, chitin, scales or skin, with matching pieces.
- New: denser grass and leaves, a blended shore gradient, very sparse lily pads, and flowers as named, harvestable plants.
- Removed: ferro rod, wooden spear, Selenite corpse and the rabbit.
- Fixed: scaled and chitinous animals no longer always roll "hard".
- Changed: sprite choices made in the sprite editor (40 items, Selenite) are now the code defaults, so they no longer depend on `sprites.json`.
- Faster: plants stop building discarded items while full; the test suite runs about three times faster.

## Survival game (branch `gameplay-core`, save version 8)
- New: races Human / Selenite / Mau, nine backgrounds, five sponsors with contracts, reputation, supplies and a cargo pod.
- New: a crash site next to the start (ship wreck, sponsor pod), precursor ruins and a gate elsewhere; three ways off the planet
  (repair the ship, corporate rescue with a beacon, ancient gate) and eight endings.
- New: cold, heat and bad air; fire, shelter and beds; sleeping (`Z`); pistol (`P`), bounty tracker (`K`), scanner (`S`), codex (`O`),
  navigation (`M`), help (`H`). Materials and creatures have provisional names until you learn them.
- New: Roguelike (permadeath) and Casual (bed saves) modes; main menu with Settings and Exit; stepped character creation.
- Changed: the player obeys diet and liquid rules; inventory capacity 20; the welcome text.

## New Urizen sheet
- Fix: lake edges drew as human figures. The terrain renderer packed sprite ids into 12 bits (max 4095) and the wider sheet
  goes past that; it now has 14 bits, a guard that fails at import if the sheet outgrows them, and a test over every sprite id.
- Save version 7: saves from before the sheet change store old sprite numbers and are refused (start a new game).
- The game now draws from `src/urizen_white.png`: the updated official Urizen sprites (grid and separators removed, white for tinting)
  plus the project's own sprites. Every sprite the game uses looks exactly as before (a pixel-hash test guards this); only their
  position on the sheet changed. The sheet is 125 columns wide (see `tilesets/README.md`, `scripts/build_tileset.py`).

## Creature movement: hunting, stairs
- Hostile creatures hunt you from up to 45 tiles away (about a chunk), seen or not, across chunk borders, in the full and the
  NEAR tier alike. Closer than 15 tiles (or in view) they come before eating; farther away a hungry hostile feeds first.
- Creatures blocked by a lake or wall plan a real path round it (A*) after two steps without progress.
- Hostile creatures within 8 tiles of you when you take stairs follow you to the other layer, arriving one turn per tile of
  distance after you. Idle creatures standing on a staircase sometimes use it (4 % per turn).
- You can only ever see your own layer (plus the dimmed ground seen through open air); there is no layer scrolling.

## Stumps
- Felling a deciduous tree, evergreen or palm leaves a **Stump** (walkable scenery, nothing to pick up). Fungi and cacti leave
  nothing yet (they will get their own remains later).

## Leather, flask, drinking, poison
- Rabbits drop **Leather**. Craft a **Flask** from 1 leather. Use a flask next to a liquid tile to fill it (3 sips); use a full
  flask to drink (+40 thirst). Use it next to a *lit campfire* first to boil its contents.
- Raw impure liquid poisons you (6 turns of 1 damage); toxic liquid poisons hard (25) even when boiled; boiled impure liquid is
  safe. Filling from acidic liquid destroys the flask. Flasks never tell you what is inside; the HUD shows "Poisoned".
- Thirsty creatures walk to impure liquid and drink it (they avoid toxic and acidic lakes). Meat now only restores 5 thirst (was 15).

## Liquids (lakes have depth and a hidden kind)
- Lakes are now called "liquid" and have two colours, the same everywhere: a lighter shallow (can be waded) and a slightly
  darker deep (depth 2-3, cannot). Deeper liquid is always ringed by shallower liquid. The colours are deliberately close so
  the edge does not clash with the land.
- Each lake has a kind you cannot see: impure (unsafe to drink, boiling makes it safe), toxic (poisonous even when boiled) or acidic
  (burns you and sometimes your armor when you wade through it, and destroys a flask dipped into it). Creatures avoid acid.
- Buildings and the spawn/cave entrance are never placed in a lake.

## Bigger simulated world
- Everything alive within 2 chunks of you (a 350x200 tile area, 5x the screen's width) now eats, hunts and flees by the same
  rules as on screen (before: 1 chunk). Setting `GameConfig.sim_radius` changes it. The first load and crossing a chunk border
  cost a bit more (see BENCHMARKS.md).

## Layers: real stairs, caves, buildings, building your own floors
- The world is now a stack of layers (z): the surface, caves below it, upper floors of buildings above it. Stairs go to the
  same x/y on the next layer (`L` takes whichever staircase you stand on; `<` / `>` pick the direction). The HUD shows
  "Surface", "Cave 2", "Floor 1".
- The start chunk has a cave entrance 8-20 tiles from where you spawn; elsewhere about 3 in 10 chunks have a cave shaft (1-3
  layers deep) and 1 in 5 a building (1-3 floors). Caves are dark and full of Selenites; there is no sun underground.
- Open air (no floor) lets you see the layer below, dimmed, Dwarf-Fortress style: upper floors look down on the ground around
  the building.
- Craft a **Wooden Floor** (2 branches) to build a floor onto open air next to you, and **Wooden Stairs** (4 branches) to
  put a staircase up from any floor tile (the way down appears on the layer above).
- Leaving a layer stores it; coming back replays hunger/growth/etc. like for far-away chunks. Saves keep every layer (save
  version 6; older saves are rejected, as agreed).

## Day and night, light sources
- A day lasts 480 turns (you start in the morning). By day you see the whole screen (radius 41); at night only a small circle
  around you (radius 4), and the map is shaded dark. Underground (floor 2+) it is always night-dark.
- Anything that emits light lights the tiles it has a clear line to, and lit tiles in your line of sight are seen from far away
  (up to `fov_radius` 42): a lit campfire is a beacon at night. Walls block firelight.
- The side panel shows the day and time. Old saves still load; the clock is derived from game time.

## Creature behaviour: hunger-driven hunting
- Every creature now runs the same routine: flee from what hunts it, (hostile ones) chase the player, otherwise when hungry or
  thirsty eat what it carries, else find food, walk to it, eat it or attack it.
- **Diets:** rabbits are herbivores (fruit), Selenites carnivores (meat), the player an omnivore. Meat eaters hunt living herbivores
  (so rabbits now flee from the player at 4 tiles, and Selenites hunt rabbits); rabbits do not eat meat, Selenites do not eat
  fruit. Meat now also quenches 15 thirst (there is no water to drink yet).
- Hungry animals walk to food that is not right next to them (they used to wander aimlessly) and no longer re-pick their wander
  target every turn.
- Creatures in the nearby (not fully simulated) chunks follow the same rules with simpler movement, so hunts and meals happen off
  screen too. Fights and deaths the player cannot see are not logged; creatures killing each other no longer print "You gain
  experience".
- Selenites now spawn (about 8 % of the creatures).

## Combat: damage types, destructible plants
- Attacks have a damage type (blunt, sharp, pierce; elemental types can be added in `damage.py`). Fists/natural attacks are
  blunt (Selenites claw: sharp), the dagger and the new axe are sharp, the spear pierces. Targets scale damage per type
  (`resistances`); trees barely notice blunt/pierce hits.
- Bump into a tree or shrub while wielding a weapon to cut it down (trees: 30 HP, an axe needs ~5 hits, the starting dagger ~8).
  A felled plant opens its tile and drops its fruit plus two branches. Bare hands still just bump.
- New craftable **Axe** (3 branches; placeholder recipe until stone/metal exist).
- Any unit can die at 0 HP now (before, only units with an AI could).

## `g.py` removed
- The module of UI globals is replaced by an explicit `Session` object (`session.py`) reachable as `engine.session`; layout
  constants moved to `layout.py`. `main.run(handler, session)`, `setup_game.MainMenu(session)`, `new_game(player, session)`
  and `load_game(path, session)` take it. Not user-visible.

## Demo leftovers removed
- Health potion, sword, chain mail and the confusion/fireball/lightning scrolls are gone (items, species entries, the
  confusion AI, the tutorial-era `entity_factories.py`). Worlds no longer scatter any ground items; the Selenite, dagger,
  leather armor, wooden spear, meat, fruit, branch and campfire stay. The targeting handlers (`SingleRangedAttackHandler`,
  `AreaRangedAttackHandler`) stay as generic UI for future ranged items.

## Performance pass 1
- Animals walk to their chosen wander spot instead of picking a new one every turn (hungry rabbits used to jitter).
- Plants grow and drop fruit in every loaded chunk (not just the nearby ones), and at the same pace as before; trees no longer
  all fruit on the same turn (staggered start). A full plant whose neighbours are all blocked no longer loses its harvest.
- Chunk files are zlib-compressed; the save format is version 5, so earlier saves do not load (fresh start, as agreed).
- Startup: `main.py` works from any directory and says to install pygame-ce when `pygame` is missing.

## Phase 5 — chunked world
- **The world is endless:** each floor is made of 70x40 chunks generated as you walk; the view follows the player and
  scrolls across chunk borders seamlessly. The side panel shows your position.
- **Creatures off-screen keep living:** the chunk you are in is fully simulated, the 8 around it move every other turn with
  simpler behaviour (they still wander, flee and approach), far chunks are stored and caught up when you return (hunger, thirst,
  plant growth; animals with food nearby are assumed to have foraged).
- **Each floor has a down staircase** a short walk from the start (press `L` on it); it used to be missing. Going down creates a
  new world; there is no way back up.
- Vision radius is 41 tiles (the screen around you) instead of the whole map.
- Wandering and fleeing animals pick destinations near themselves (before: anywhere on the map). Pathfinding searches at most
  40 tiles around the walker.
- **Saves are a folder** (`savegame/` next to the game files) with one file per visited chunk; saving is atomic. Saves from
  earlier versions no longer load. Only visited chunks are stored.
- Plants dropping fruit no longer print "You dropped ..." messages; deaths in chunks far away are silent.

## Phase 4 — sprite layering
- **Everything on a tile is drawn in a fixed stack:** corpses, then items, then shrubs, then creatures, then trees, each with its own colour and facing.
  You can now see the corpse and item you are standing on, or that an animal stands on.
- **Piles are capped:** with more than two corpses/items on one tile only the top two are drawn and a small "+" shows there are more
  (`GameConfig.clutter_safeguard`, on by default; creatures are never hidden).
- Looking at a tile (names under the cursor) and the pick-up list now show the stack **topmost first**; long lists are cut with "...".

## Phase 3 — pygame-ce rendering and input
- **The game window is now drawn with pygame-ce** (tcod is only used for FOV, pathfinding, noise and line drawing). Install
  `pygame-ce` (`pip install -r requirements.txt`). The sprite sheet and font are unchanged.
- **Resizable window with a fixed 1920x1080 logical screen:** scaled by whole-number factors when it fits, smoothly when the window
  is smaller, with black bars; mouse clicks line up with tiles at any size.
- **The status bars, names under the cursor and the message log are now visible** (the log and dungeon level used to sit off
  screen). The level is shown as "Floor: N" in the side panel.
- Potion, sword, chain mail and scroll items now use sprites instead of text characters.
- Hover/target highlights are a translucent wash instead of inverted colours; popups dim the screen behind them.
- **Typing `q` while entering a name no longer returns to the main menu.**
- The game redraws only when something happens and idles at 60 FPS.
- **Saves from earlier versions no longer load** (save format version 3).

## Phase 2 — data/instance split, spatial index, performance
- **Saves from earlier versions no longer load** (save format version 2). The main menu reports "Failed to load save".
- **Monsters and items no longer spawn inside walls or water** (placement now requires a walkable, unoccupied tile).
- **Attacks and lookups target the living unit** when a creature stands on a corpse (it could hit the corpse before);
  rabbits no longer flee from corpses.
- **Each plant has its own growth period** (gaussian around its species' cycle); previously all plants on a floor were
  copies of one prototype and shared it. Plants without fruit no longer run an (empty) AI each turn.
- A fresh player is created for every New Game (a name typed, abandoned and retyped no longer carries over).
- Fleeing animals give up after a bounded number of tries instead of potentially looping forever.
- Ties between equally close food items are resolved in ring order around the animal (previously set order).
- Same `random`/`numpy` seed now generates the same floor (terrain noise used to ignore it). New games still differ.
- FOV radius is configurable (`GameConfig.fov_radius`, default 80 = whole map, unchanged behaviour).
- Faster floor generation (~2.4x), spawning (~4x) and AI turns (1.1–2.5x); see BENCHMARKS.md.

## Phase 1 — bug fixes
- **Starvation and dehydration now work.** At 0 hunger/thirst any unit loses 1 HP per tick (previously nobody did, and the
  player never saw the messages). The player gets one "is starving!" / "is severely dehydrated!" message when the stat first hits 0.
- **HP can no longer exceed max HP** through `handle_health` (it was clamped to `max_hunger`).
- **Level-up no longer crashes**; it now changes the player's stats (+20 max HP / +1 power / +1 defense as the menu says).
- **Opening the inventory with a Health Potion no longer crashes.**
- **Area-targeting frame** is now the correct size and centred on the cursor.
- `Engine.get_path_to` returns `[]` instead of `None` for out-of-bounds destinations.
- `setup_game` uses the game's `exceptions` module (was `asyncio.exceptions`).
- Menus/AIs no longer share mutable class-level state (`buttons`, `inventory_entries`, `BaseAI.path`).
- Name generation is cached and pure Python (`namegen.py`); output format unchanged, but exact names for a given seed differ
  from libtcod's generator.
- `matplotlib` is no longer a dependency; `utilities.text_input` (broken, unused) was deleted.

## Phase 0
- No behavior changes. Added tests, benchmark and notes only.

## Gameplay core (branch gameplay-core)
- Items are made of planet materials; crafting is property-based (`recipes.py`, `crafting.py`, `items.py`), with a requirement-by-
  requirement crafting screen, tools/stations/skills/heat, derived properties, dull-until-sharpened edges, furnaces, fuel and
  sparks, built walls, mining (`X` dig, bump a rock face with a pickaxe, `T` sharpen), hide and fibre drops.

## UI overhaul and fixes (branch gameplay-core)
- **Windows, not walls of glyphs.** TrueType text (DejaVu Sans Mono) in framed windows with tab row and `[key] action` hint bar; every
  screen rebuilt (inventory, character, recipes, codex, log, help, map, pod, ending, main menu, settings, character creation, HUD).
  Tab cycles the five main screens. Hover tooltip for the thing under the mouse. The map scrolls by chunk-aligned pages.
- **Crafting** is contextual: only what you can make here and now is listed (Space shows everything you know); recipes you work out
  from nearby materials are announced. Crafted items take their material's name and colour; names follow what you have learned.
- **Corpses** are the creature lying on its side, with bones. Colour groups shade strictly within their group. Plant background removed.
- **Sprite config + editor:** `src/data/sprites.json` overrides sprite cells; "Sprite editor" in the main menu edits them in-game.
- **Errors never close the game:** every handler/render error is logged, shown in the message log and the game carries on. Fixed the
  wreck-grab crash and the survey-kit error. Targeting screens (place, scan, fire) now close after use instead of staying open.
- Tests: 648 (UI, live names, sprite config/editor, fuzzed clicking, and a keypress-only campfire playthrough on three seeds).

- **Mountains (stage 6):** passes through ridges, snow and volcanic-ash rock colour, surface chasms that look down into the caves, caves at rock faces in mountain country, lava lakes in volcanic cores (a new deadly liquid), waterfalls on steep rivers. Tests: 788.

- **World map (M):** one cell per chunk of what you have actually seen, with your ship, pod and ruins, a chunk info panel, zoom and a cursor.
- **Bridges and paths:** natural plank bridges over narrow rivers, trodden paths between buildings and ruins (bridging short water), and player-built bridges (wooden floor over water from the bank). Tests: 825.

- **Music:** data-driven contextual music (`data/music.json`): landmark pools, ambient elsewhere, combat music by creature category (tags), fades, resume after combat, graceful fallbacks. No music is shipped; point `music_dir` (or `STARSTRANDED_MUSIC`) at a folder and fill the pools.
