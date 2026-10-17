"""Characterization: save/load round trip (pickle + lzma of the whole Engine)."""
import numpy as np

import setup_game
from engine import Engine


def test_save_load_roundtrip(new_engine, tmp_path):
    e = new_engine
    e.player.hp = 17
    e.message_log.add_message("hello")
    path = str(tmp_path / "t.sav")
    e.save_as(path)
    loaded = setup_game.load_game(path)

    assert isinstance(loaded, Engine)
    assert loaded.player.hp == 17
    assert (loaded.player.x, loaded.player.y) == (e.player.x, e.player.y)
    assert np.array_equal(loaded.game_map.tiles, e.game_map.tiles)
    assert np.array_equal(loaded.game_map.explored, e.game_map.explored)
    assert len(loaded.game_map.entities) == len(e.game_map.entities)
    assert loaded.message_log.messages[-1].plain_text == "hello"
    assert loaded.game_world.current_time == e.game_world.current_time


def test_loaded_game_is_playable(new_engine, tmp_path):
    import actions
    path = str(tmp_path / "t.sav")
    new_engine.save_as(path)
    loaded = setup_game.load_game(path)
    t0 = loaded.game_world.current_time
    actions.WaitAction(loaded.player).perform()
    assert loaded.game_world.current_time == t0 + 1


def test_identity_survives_roundtrip(new_engine, tmp_path):
    path = str(tmp_path / "t.sav")
    new_engine.save_as(path)
    loaded = setup_game.load_game(path)
    assert loaded.player in loaded.game_map.entities
    assert loaded.player.parent is loaded.game_map
    assert loaded.game_map.engine is loaded
