"""FOV radius is configurable; the default covers the whole 70x40 viewport around the (centred) player."""
import dataclasses

import numpy as np

from config import DEFAULT_CONFIG, GameConfig


def test_default_radius_covers_the_viewport_half_diagonal():
    assert int(np.ceil(np.hypot(35, 20))) <= DEFAULT_CONFIG.fov_radius <= 45


def test_default_fov_from_the_centre_sees_every_corner_of_an_open_70x40_map(small_world):
    e = small_world(width=70, height=40)
    e.game_world.current_time = 72  # noon
    e.player.place(35, 20)
    e.update_fov()
    v = e.game_map.visible
    assert v[0, 0] and v[69, 0] and v[0, 39] and v[69, 39] and v.all()


def test_smaller_radius_limits_vision(small_world):
    e = small_world(width=30, height=20)
    e.config = dataclasses.replace(e.config, fov_radius=4)
    e.player.place(10, 10)
    e.update_fov()
    v = e.game_map.visible
    assert v[10, 10] and v[13, 10] and not v[16, 10] and not v[29, 19]  # tcod radius is exclusive at r


def test_config_is_frozen_and_survives_save(new_engine, tmp_path):
    import setup_game
    new_engine.config = GameConfig(fov_radius=33)
    path = str(tmp_path / "c.sav")
    new_engine.save_as(path)
    assert setup_game.load_game(path).config.fov_radius == 33
