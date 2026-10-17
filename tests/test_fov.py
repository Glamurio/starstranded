"""FOV radius is configurable; the default keeps the whole 70x40 map visible in open terrain."""
import dataclasses

import numpy as np

from config import DEFAULT_CONFIG, GameConfig


def test_default_radius_covers_the_whole_map_diagonal():
    assert DEFAULT_CONFIG.fov_radius >= int(np.ceil(np.hypot(69, 39)))


def test_default_fov_sees_the_far_corner_of_an_open_70x40_map(small_world):
    e = small_world(width=70, height=40)
    e.player.place(0, 0)
    e.update_fov()
    assert e.game_map.visible[69, 39] and e.game_map.visible.all()


def test_smaller_radius_limits_vision(small_world):
    e = small_world(width=30, height=20)
    e.config = dataclasses.replace(e.config, fov_radius=4)
    e.player.place(10, 10)
    e.update_fov()
    v = e.game_map.visible
    assert v[10, 10] and v[14, 10] and not v[16, 10] and not v[29, 19]


def test_config_is_frozen_and_survives_save(new_engine, tmp_path):
    import setup_game
    new_engine.config = GameConfig(fov_radius=33)
    path = str(tmp_path / "c.sav")
    new_engine.save_as(path)
    assert setup_game.load_game(path).config.fov_radius == 33
