# Biomes

How the surface of a planet is divided into regions, what each region is, and how caves and points of interest follow it.
Code: `src/biomes.py` (the catalogue), `src/regions.py` (where regions are), `src/worldgen.py` (`environment_for`, ground, vegetation),
`src/urban.py` (cities), `src/underground.py` (cave biomes), `src/pois.py` (points of interest). Decisions: `DECISIONS.md`.

## 1. Architecture

* **A region is a Voronoi cell.** The world is cut into 150-tile cells; each holds one jittered site, warped by two noise fields, so regions are
  large (median about 15,000 tiles, roughly 120 x 120), irregular and a pure function of `(seed, x, y)`. Nothing depends on which chunk is loaded.
* **The biome of a region is drawn once, at world level** from the climate at its site (temperature, moisture, elevation) times each biome's
  `rarity`, never per tile. Near the landing site only mild, non-hostile biomes are allowed (`regions.mild`, `SPAWN_SAFE` = 300 tiles).
* **Borders blend.** Every tile knows its biome, the neighbouring region's biome (`other`) and an `edge` share from 0 to 0.5. Ground colour, plant weights,
  scenery weights, fauna suitability and music all blend by `edge` over `BORDER` = 34 tiles (cells are 300 tiles, three to a province), so there are no hard lines.
* **Inside a region** the ground shade, an alternate ground patch, vegetation patches, flooding and city density come from their own noise fields, so a region is never flat.
* **Variants** (hot, cold, wet, dry) are climate flags on a tile (how far its climate is from the middle of the biome's range). They change ground tint,
  vegetation density, ambient temperature and the name shown; they never change the identity of the biome. They are not combined automatically (see section 3).
* **Traits drive life.** A biome's family (and the biome) lists traits (hot, cold, wet, dry, fungal...). A trait is a delta applied to the native plants'
  materials (a hot biome's plants get more insulation and less conductivity and flammability) and to the family's fauna (a hot biome's creatures get scales or thin fur, and so on).
  `Biome.plants` lists native plants; `plants_only` forbids the others.
* **Cities are laid out from world coordinates** (`urban.layout`): a street grid, blocks, rings of wall entities for low buildings, solid towers, wrecks, lamp posts and signposts. No settlers, no NPCs.
  Farms and hamlets (`settlements.py`) are abandoned and never placed in a city, volcanic or crystal region.
* **Points of interest** (`pois.py`) are the second layer, below.

Old saves are incompatible (the planet's random stream changed).

## 2. Catalogue (72 biomes)

Columns: key, name, family, ambient temperature, ground colour, scenery/features, support level. **Full** biomes have their own ground, native plants or
scenery, fauna adaptation and music; **basic** biomes are defined and generated but lean on their family's look (they are listed honestly in section 8).

| key | name | family | ambient | ground | what is distinctive | support |
|---|---|---|---|---|---|---|
| plains | Plains | grass | 16 | (105, 140, 70) | scenery: pebbles, small_rocks | full |
| flowering_meadow | Flowering meadow | grass | 16 | (150, 190, 120) | plants: meadow_bloom, meadow_flower, bush; scenery: pebbles, small_rocks, bones | full |
| tallgrass_expanse | Tallgrass expanse | grass | 22 | (160, 150, 80) | plants: tallgrass, golden_grass, acacia; scenery: bones, pebbles | full |
| ancient_grassland | Ancient grassland | grass | 13 | (125, 140, 95) | plants: ancient_oak, bush, meadow_flower; scenery: monolith, bones, skull; poi: standing_stones | full |
| overgrown_pasture | Overgrown pasture | grass | 15 | (125, 140, 75) | plants: crop_wild, thorns, bush; scenery: stump, pebbles, rubble; poi: abandoned_farm, ruined_cabin | full |
| steppe | Steppe | grass | 8 | (150, 140, 90) | scenery: bones, pebbles | full |
| savanna | Savanna | grass | 30 | (170, 150, 75) | plants: acacia, golden_grass, thorns; scenery: bones, skull | full |
| shrubland | Shrubland | grass | 22 | (130, 125, 80) | plants: bush, thorns; scenery: small_rocks, bones | full |
| cactus_desert | Cactus desert | arid | 40 | (222, 156, 84) | plants: cactus, barrel_cactus, agave; scenery: bones, skull, small_rocks | full |
| red_dunes | Red dunes | arid | 42 | (196, 108, 70) | plants: agave, thorns; scenery: bones, small_rocks | full |
| salt_flats | Salt flats | arid | 36 | (228, 226, 222) | plants: saltbush; scenery: salt_crust, bones | full |
| glass_desert | Glass desert | arid | 44 | (160, 205, 190) | plants: glass_cactus; scenery: glass_shards, crystal_cluster, bones | full |
| bone_desert | Bone desert | arid | 38 | (214, 200, 170) | plants: saltbush, bone_thorn, cactus; scenery: bones, skull; poi: bone_pile, graveyard | full |
| desert_badlands | Desert badlands | arid | 36 | (170, 105, 70) | plants: thorns, agave, barrel_cactus; scenery: small_rocks, pebbles, bones | full |
| desert | Desert | arid | 38 | (205, 180, 120) | plants: cactus, barrel_cactus, dry_flower; scenery: bones, pebbles, skull | full |
| temperate_woodland | Temperate woodland | forest | 14 | (60, 100, 55) | plants: broadleaf, willow, bush; scenery: stump, pebbles | full |
| dense_forest | Dense forest | forest | 12 | (40, 80, 45) | plants: broadleaf, conifer, cypress; scenery: stump, pebbles | full |
| ancient_canopy | Ancient canopy | forest | 11 | (35, 70, 50) | plants: ancient_giant, broadleaf, fern; scenery: stump, mushroom_ring; poi: ruined_cabin, standing_stones | full |
| amberwood | Amberwood | forest | 10 | (130, 85, 45) | plants: amber_tree, broadleaf, bush; scenery: stump | full |
| jungle | Jungle | forest | 29 | (35, 110, 55) | plants: palm, broadleaf, jungle_giant; scenery: stump, mushroom_ring | full |
| thornwood | Thornwood | forest | 20 | (70, 62, 55) | plants: thorn_tree, thorns, bush; scenery: bones, stump | full |
| petrified_forest | Petrified forest | forest | 22 | (150, 142, 130) | plants: petrified_tree; scenery: stump, small_rocks; poi: bone_pile | full |
| taiga | Taiga | cold | -2 | (70, 90, 70) | plants: conifer, bush; scenery: stump, small_rocks | full |
| fungal_forest | Fungal forest | fungal | 13 | (120, 66, 128) | plants: fungal_tree, spore_bush, glowcap; scenery: mushroom_ring, pebbles, small_rocks | full |
| giant_mushroom_grove | Giant mushroom grove | fungal | 15 | (140, 96, 140) | plants: giant_cap, fungal_tree, glowcap; scenery: mushroom_ring | full |
| spore_marsh | Spore marsh | fungal | 17 | (100, 90, 120) | plants: spore_bush, glowcap, reeds; scenery: mushroom_ring; floods 0.1 | full |
| mycelial_expanse | Mycelial expanse | fungal | 11 | (190, 182, 196) | plants: glowcap, spore_bush, spore_flower; scenery: mushroom_ring, tendrils | full |
| luminous_fungal_basin | Luminous fungal basin | fungal | 12 | (40, 120, 140) | plants: glowcap, fungal_tree, spore_flower; scenery: mushroom_ring, crystal_cluster | full |
| deep_fungal_growth | Deep fungal growth | fungal | 9 | (70, 40, 86) | plants: fungal_tree, spore_bush, glowcap; scenery: tendrils, mushroom_ring | full |
| crystal_fields | Crystal fields | crystal | 5 | (112, 132, 190) | plants: shard_bush, crystal_bloom, crystal_tree; scenery: crystal_cluster, small_rocks | full |
| crystalline_badlands | Crystalline badlands | crystal | 4 | (130, 138, 175) | plants: shard_bush, crystal_bloom; scenery: crystal_cluster, small_rocks, pebbles | full |
| luminous_crystal_forest | Luminous crystal forest | crystal | 7 | (96, 110, 170) | plants: crystal_tree, shard_bush, crystal_bloom; scenery: crystal_cluster | full |
| crystal_desert | Crystal desert | crystal | 36 | (225, 190, 190) | plants: shard_bush, glass_cactus; scenery: crystal_cluster, glass_shards, bones | full |
| mineral_labyrinth | Mineral labyrinth | crystal | 12 | (120, 112, 118) | plants: shard_bush; scenery: small_rocks, pebbles | basic |
| geode_basin | Geode basin | crystal | 10 | (120, 90, 150) | plants: crystal_bloom, shard_bush; scenery: crystal_cluster, small_rocks | full |
| volcanic_wastes | Volcanic wastes | volcanic | 40 | (58, 38, 40) | plants: ash_shrub, cinder_tree, ember_bloom; scenery: ash_pile, obsidian, small_rocks; hot springs 1.0 | full |
| lava_highlands | Lava highlands | volcanic | 46 | (70, 36, 30) | plants: ash_shrub, ember_bloom; scenery: ash_pile, obsidian, small_rocks; hot springs 2.0 | full |
| geothermal_basin | Geothermal basin | volcanic | 28 | (200, 170, 110) | plants: ash_shrub, saltbush, reeds; scenery: salt_crust, small_rocks; hot springs 5.0 | full |
| obsidian_fields | Obsidian fields | volcanic | 34 | (36, 34, 46) | plants: ash_shrub; scenery: obsidian, glass_shards, ash_pile | full |
| ashen_caldera | Ashen caldera | volcanic | 32 | (112, 106, 106) | plants: ash_shrub, cinder_tree, dead_tree; scenery: ash_pile, small_rocks, bones; hot springs 1.5 | full |
| scalded_mountains | Scalded mountains | volcanic | 44 | (150, 120, 60) | plants: ash_shrub; scenery: small_rocks, salt_crust, ash_pile; hot springs 1.5 | basic |
| decaying_lands | Decaying lands | decay | 14 | (78, 66, 84) | plants: dead_tree, bone_thorn, rot_cap; scenery: bones, skull, rubble; poi: graveyard, bone_pile | full |
| deadwood_expanse | Deadwood expanse | decay | 18 | (100, 90, 80) | plants: dead_tree, bone_thorn; scenery: stump, bones, skull | full |
| bone_fields | Bone fields | decay | 15 | (176, 172, 150) | plants: bone_thorn, dead_tree; scenery: bones, skull, gravestone; poi: bone_pile, graveyard | full |
| corrupted_growth | Corrupted growth | decay | 17 | (54, 34, 66) | plants: rot_cap, tendril_tree, bone_thorn; scenery: tendrils, bones, skull | full |
| ruptured_wastes | Ruptured wastes | decay | 24 | (130, 112, 100) | plants: thorns, bone_thorn; scenery: rubble, small_rocks, bones; poi: wreck_field | full |
| abandoned_industrial_ground | Abandoned industrial ground | decay | 18 | (116, 96, 82) | plants: thorns, bush, weed; scenery: wreck_car, wreck_truck, rubble; poi: wreck_field, research_outpost | full |
| visceral_heap | Visceral heap | alien | 33 | (150, 60, 76) | plants: tendril_tree, flesh_pod, creeper; scenery: tendrils, bones | full |
| undergrowth | Undergrowth | alien | 22 | (60, 86, 50) | plants: creeper, vine_creeper, fern; scenery: tendrils, stump | full |
| bioluminescent_expanse | Bioluminescent expanse | alien | 12 | (24, 36, 56) | plants: lumen_frond, iris_bloom, glowcap; scenery: mushroom_ring, crystal_cluster | full |
| spore_drift_fields | Spore drift fields | alien | 20 | (190, 160, 90) | plants: spore_bush, spore_flower, glowcap; scenery: mushroom_ring | basic |
| iridescent_flats | Iridescent flats | alien | 22 | (168, 140, 210) | plants: iris_bloom, shard_bush; scenery: glass_shards, crystal_cluster | full |
| organic_wastes | Organic wastes | alien | 26 | (108, 98, 48) | plants: rot_cap, flesh_pod, weed; scenery: bones, tendrils | basic |
| swamp | Swamp | wet | 24 | (70, 90, 50) | plants: mangrove, willow, reeds; scenery: stump, bones; floods 0.1 | full |
| bog | Bog | wet | 5 | (85, 80, 55) | plants: reeds, conifer, bush; scenery: stump; floods 0.1 | full |
| toxic_wetlands | Toxic wetlands | wet | 26 | (120, 130, 50) | plants: reeds, toxic_bloom, rot_cap; scenery: bones, skull; floods 0.2 | full |
| luminous_marsh | Luminous marsh | wet | 18 | (40, 90, 84) | plants: glow_reed, lumen_frond, marsh_flower; floods 0.1 | full |
| mineral_pools | Mineral pools | wet | 25 | (190, 160, 120) | plants: saltbush, reeds; scenery: salt_crust; hot springs 2.0; floods 0.1 | full |
| flooded_forest | Flooded forest | wet | 23 | (60, 100, 72) | plants: mangrove, willow, cypress; scenery: stump; floods 0.3 | full |
| algal_basin | Algal basin | wet | 19 | (80, 150, 80) | plants: algae_mat, reeds; floods 0.2 | full |
| thermal_wetlands | Thermal wetlands | wet | 30 | (100, 130, 70) | plants: reeds, mangrove, marsh_flower; hot springs 3.0; floods 0.1 | full |
| glacial_plain | Glacial plain | cold | -25 | (200, 215, 230) | plants: rime_shrub; scenery: small_rocks, bones | full |
| tundra | Tundra | cold | -10 | (150, 150, 130) | plants: rime_shrub, bush, frost_bloom; scenery: small_rocks, pebbles, bones | full |
| frost_grove | Frost grove | cold | -14 | (176, 200, 226) | plants: frost_tree, rime_shrub, frost_bloom; scenery: small_rocks | full |
| snow_fields | Snow fields | cold | -18 | (232, 240, 248) | plants: frost_tree, rime_shrub; scenery: stump | full |
| ice_spires | Ice spires | cold | -22 | (160, 196, 230) | plants: rime_shrub; scenery: crystal_cluster, small_rocks | basic |
| beach | Beach | coast | 22 | (232, 214, 160) | plants: coast_palm, beach_grass; scenery: pebbles, bones, shell | full |
| abandoned_district | Abandoned urban district | urban | 14 | (92, 92, 98) | plants: weed, bush, thorns; scenery: rubble, pebbles, lamp_post; city; poi: research_outpost | full |
| overgrown_city | Overgrown city | urban | 19 | (70, 94, 66) | plants: broadleaf, creeper, ivy; scenery: rubble, tendrils; city | full |
| industrial_ruins | Industrial ruins | urban | 18 | (110, 90, 82) | plants: weed, thorns; scenery: pipe, drum, rubble; city | full |
| flooded_ruins | Flooded ruins | urban | 21 | (70, 100, 100) | plants: reeds, mangrove, ivy; scenery: rubble; floods 0.3; city | basic |
| ancient_settlement_remains | Ancient settlement remains | urban | 14 | (128, 124, 98) | plants: ancient_oak, bush, thorns; scenery: monolith, bones, rubble; city; poi: standing_stones | full |

66 biomes are marked full, 6 basic.

## 3. Variants and compatibility rules

A variant is a modifier of a biome, not a biome. Flags: `hot`, `cold` (temperature beyond the edge of the biome's range), `wet`, `dry` (moisture likewise);
hot and cold, wet and dry exclude each other. Effects (`biomes.VARIANTS`): ground tint, vegetation density (hot 0.85, cold 0.8, wet 1.2, dry 0.75) and ambient temperature
(+8, -10, -2, +2). The displayed name is `variant_name` (for example "Hot Plains"). Rules: a variant never changes the biome key, its plants (only their density), its music or its underground biome;
`wet_twin` names the biome a very wet region of a biome becomes (for instance a woodland that floods) where the catalogue defines one.

**Suggested named combinations (not implemented; choose which, if any, you want promoted to biomes or kept as names):**

| combination | name idea | reads as |
|---|---|---|
| plains + hot + dry | Scorched Plains | yellowed grass, sparse trees |
| plains + cold | Frostbitten Plains | pale grass, snow patches |
| plains + wet | Water Meadows | lush, standing pools |
| temperate_woodland + cold | Winter Wood | bare trees, frost |
| temperate_woodland + hot + dry | Tinderwood | dry wood that burns easily |
| dense_forest + wet | Drowned Forest | roots in water (cf. flooded_forest) |
| jungle + hot + wet | Steam Jungle | the thickest, hottest growth |
| desert + cold | Cold Desert | stony, frozen dunes |
| cactus_desert + wet | Bloom Desert | brief flowering after rain |
| fungal_forest + wet | Spore Fen | dripping caps, low mist |
| fungal_forest + dry | Withered Caps | shrivelled, pale mushrooms |
| crystal_fields + cold | Rime Crystals | frosted spires |
| crystal_fields + hot | Glass Heath | heat-fused, glassy crystal |
| volcanic_wastes + wet | Steam Vents | geysers and mud |
| volcanic_wastes + cold | Ash Barrens | cooled, grey, no lava |
| swamp + cold | Frozen Fen | ice over the water |
| swamp + hot | Miasma Marsh | rot and gas |
| taiga + dry | Needle Barrens | thin, brittle pines |
| decaying_lands + wet | Rot Marsh | slime and spores |
| abandoned_district + wet | Drowned District | flooded streets (needs water tiles) |
| abandoned_district + cold | Frozen City | snow on roofs |
| steppe + dry | Dust Steppe | dust and bone |
| savanna + wet | Rain Savanna | the green season |
| visceral_heap + hot | Fever Heap | warmest and rawest |

## 4. Surface to underground mapping

Each family names an underground biome (`Family.under`, overridable per biome with `Biome.under`). Underground biomes (`underground.UBIOMES`) are picked per cave tile by a deterministic world field
whose pull towards the surface biome's cave is `SURFACE_INFLUENCE` near the surface and falls to `DEEP_INFLUENCE` with depth, so deeper layers diverge (influence, not an absolute rule). Selenite visitors are rare, empty caverns are avoided (the barren share is about 20 to 35 percent), and precursor ruins are about 3 percent.

| surface family | underground biome |
|---|---|
| grass | barren |
| arid | salt |
| forest | rootbound |
| fungal | mycelial |
| crystal | crystal |
| volcanic | volcanic |
| decay | bone_vault |
| alien | warren |
| wet | wet |
| cold | ice |
| coast | wet |
| urban | infrastructure |

Underground keys: barren, volcanic, ice, crystal, fungal, wet, salt, rootbound, mycelial, bone_vault, warren, infrastructure, ruins.

Concepts that would need height maps (not implemented): ravines and plateaus that follow a surface ridge, caves that open under real mountains, lava tubes that follow a slope,
rivers that cut canyons, glaciers that flow downhill, and flooded caves that follow the surface water table. The generator has elevation noise but no persistent height map shared with the cave layers.

## 5. Points of interest

`pois.py` is the foundation for sites: `NoiseWorldSource._place_sites` still places the crash site and precursor ruins, then calls `pois.place`. Per chunk, a seeded roll (`CHANCE` 0.4,
a second with `SECOND` 0.25) picks kinds weighted by the biome at the chunk centre (`Biome.pois`; unlisted kinds use their default, a city lists its own only). The landing chunk, ruin chunks,
settlements and buildings never hold one. A POI inherits its biome: stone from the biome's rocks (`resources.surface_stone`), timber from the planet's trees, scenery from the biome.
Kinds: standing stones, bone pile, graveyard, wreck field, ruined cabin, research outpost, abandoned farm plot. All are uninhabited. A kind is one builder function and one registry line.

## 6. Verification summary

* **Regions, 8 seeds, 1200 x 700 tiles each:** 45 to 52 regions, 28 to 35 distinct biomes in view, median region area 14,900 to 18,000 tiles,
  and only 2 to 5 of about 58 connected pieces are under 400 tiles (border slivers). Generating a 1200 x 700 field takes about 1 s; a chunk loads in about 80 ms with points of interest.
* **Determinism:** regions, urban layouts and POI rolls are pure functions of seed and world coordinates; tests compare the same area asked for through different rectangles.
* **Blind theme review** (an agent that saw only the screenshots, seed 7, 66 biomes ranked, 6 excluded as placeholders): best were visceral_heap, deep_fungal_growth and frost_grove (5);
  dense_forest, ancient_canopy, corrupted_growth, iridescent_flats, algal_basin, salt_flat and the three street-grid cities scored 4; most others 2 to 3. Lowest (1): red_dunes, snow_fields,
  ashen_caldera, luminous_marsh, giant_mushroom_grove. The cause is mostly systemic: open ground is drawn as a dim backdrop (a dot at 80 percent of the biome colour on a background at 10 percent),
  so a biome's colour is carried by its dots, cover and scenery rather than by a wash of colour. Grass biomes (plains, tallgrass_expanse, steppe, savanna) look alike for the same reason.
  Cheap follow-ups: raise the background share, add tall-mushroom and dune scenery, and give ash and snow a drift scenery kind.
* Tests: `tests/test_regions.py`, `test_biomes.py`, `test_biome_life.py`, `test_urban.py`, `test_pois.py`. Screenshots: `tools/world_shots.py SEED biome:KEY ...` and `tools/render_map.py`.

## 7. Limitations
: `tests/test_regions.py`, `test_biomes.py`, `test_biome_life.py`, `test_urban.py`, `test_pois.py`. Screenshots are made with `tools/world_shots.py` and `tools/render_map.py`.

## 7. Limitations

* Basic-support biomes: mineral_labyrinth, scalded_mountains, spore_drift_fields, organic_wastes, ice_spires, flooded_ruins.
* Water in wet biomes does not yet flood (`Biome.flood` is read but unused); `flooded_ruins` has no water.
* City sprites (roads, wrecks, towers, lamp posts, drums, pipes) are guesses from the tileset; towers read as plain blocks.
* Variants change tint, density, temperature and name only.
* No height maps: no ridges, canyons or watersheds tied to the biome.
* A region may touch the same biome as its neighbour, which then looks like one larger region.
