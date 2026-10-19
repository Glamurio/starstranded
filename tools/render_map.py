"""Developer tool: paint the generated terrain of a seed as one PNG (1 pixel per tile) to look at continents, ranges, rivers
and landmarks. Usage: python tools/render_map.py SEED OUT.png [X0 Y0 WIDTH HEIGHT]   (run from the repository root)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np

import biomes
import landmarks
import worldgen


def paint(seed: int, x0: int, y0: int, width: int, height: int) -> np.ndarray:
    noise = worldgen.TerrainNoise(seed)
    kinds = worldgen.base_terrain(noise, x0, y0, width, height)
    env = worldgen.environment_for(noise, x0, y0, width, height, kinds)
    ground = landmarks.blend_ground(biomes.ground_colors(env["biome"]), env["landmark"], env["landmark_strength"]).astype(float)
    shade = 0.75 + 0.25 * np.clip(env["elevation"], 0, 1.2)[..., None]
    image = ground * shade
    image[kinds == 2] = np.array([95, 90, 95]) * (0.7 + 0.3 * np.clip(env["elevation"], 0, 1.5))[kinds == 2][:, None]
    volcanic = (env["landmark"] == landmarks.LANDMARK_INDEX["volcanic_mountains"]) * env["landmark_strength"]
    snow = (worldgen.relief.smooth((env["elevation"] - worldgen.SNOW_FROM) / worldgen.SNOW_SPAN) * (1.0 - np.clip(volcanic * 1.5, 0, 1)))[..., None]
    ash = np.clip(volcanic * 1.2, 0, 0.85)[..., None]
    rock = kinds == 2
    image = np.where(rock[..., None], image * (1 - ash) + np.array(worldgen.ASH_COLOR) * ash, image)
    image = np.where(rock[..., None], image * (1 - snow) + np.array(worldgen.SNOW_COLOR) * snow, image)
    shallow, deep = worldgen.liquid_palette(noise, np.full(kinds.shape, 1), x0, y0, width, height)   # (the kind tint is left out here)
    image[kinds == 0] = shallow[kinds == 0]
    sx, sy = 35 - x0, 20 - y0
    if 4 <= sx < width - 4 and 4 <= sy < height - 4:
        image[sx - 4:sx + 5, sy] = (255, 0, 0)
        image[sx, sy - 4:sy + 5] = (255, 0, 0)
    return np.clip(image, 0, 255).astype(np.uint8)


if __name__ == "__main__":
    seed, out = int(sys.argv[1]), sys.argv[2]
    x0, y0, width, height = (int(v) for v in sys.argv[3:7]) if len(sys.argv) >= 7 else (-600, -350, 1200, 700)
    image = paint(seed, x0, y0, width, height)
    import pygame
    surface = pygame.surfarray.make_surface(image)
    pygame.image.save(surface, out)
    print("saved", out, image.shape)
