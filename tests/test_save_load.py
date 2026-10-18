"""Save/load round trip: a save directory with a manifest and one file per chunk."""
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
    assert loaded.game_map.chunks.keys() == e.game_map.chunks.keys()
    for key, chunk in e.game_map.chunks.items():
        assert np.array_equal(loaded.game_map.chunks[key].tiles, chunk.tiles)
        assert np.array_equal(loaded.game_map.chunks[key].explored, chunk.explored)
    assert len(loaded.game_map.entities) == len(e.game_map.entities)
    assert loaded.game_map.downstairs_location == e.game_map.downstairs_location
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


def test_save_directory_layout_is_versioned(new_engine, tmp_path):
    import lzma
    import pickle
    from engine import SAVE_VERSION
    path = tmp_path / "v"
    new_engine.save_as(str(path))
    payload = pickle.loads(lzma.decompress((path / "manifest.lzma").read_bytes()))
    assert payload["version"] == SAVE_VERSION == 6 and "engine" not in payload  # no whole-engine pickle
    chunk_files = sorted(p.name for p in (path / "layer0").iterdir())
    assert len(chunk_files) == len(new_engine.game_map.chunks)
    assert all(name.startswith("chunk_") and name.endswith(".1.zlib") for name in chunk_files)
    assert not list(path.rglob("*.tmp"))  # atomic writes cleaned up


def test_old_unversioned_saves_are_rejected_with_a_clear_error(tmp_path):
    import lzma
    import pickle
    import pytest
    import exceptions
    path = tmp_path / "old.sav"
    path.write_bytes(lzma.compress(pickle.dumps(["a pre-Phase-2 save was a bare pickled Engine"])))
    with pytest.raises(exceptions.IncompatibleSave, match="version 1"):
        setup_game.load_game(str(path))
    path.write_bytes(b"garbage")
    with pytest.raises(exceptions.IncompatibleSave):
        setup_game.load_game(str(path))


def test_uids_stay_unique_after_load(new_engine, tmp_path):
    from components.unit import Animal
    path = str(tmp_path / "u.sav")
    new_engine.save_as(path)
    loaded = setup_game.load_game(path)
    existing = {e.uid for e in loaded.game_map.entities}
    assert Animal().uid > max(existing)


def test_static_species_identity_survives_load(new_engine, tmp_path):
    import species
    path = str(tmp_path / "s.sav")
    new_engine.save_as(path)
    loaded = setup_game.load_game(path)
    assert loaded.player.kind is species.HUMAN
    plants = list(loaded.game_map.plants)
    trees = [p for p in plants if p.kind.category is species.PlantCategory.TREE]
    assert len({id(t.kind) for t in trees}) <= 1  # still one shared tree species per floor


def test_main_menu_reports_incompatible_save(tmp_path, monkeypatch):
    import input_handlers
    monkeypatch.chdir(tmp_path)
    (tmp_path / "savegame").write_bytes(b"old")
    menu = setup_game.MainMenu()
    menu.button_highlight = "Continue"
    result = menu.resolve_menu(None)
    assert isinstance(result, input_handlers.PopupMessage) and "Failed to load save" in result.text


def test_version_2_saves_from_the_tcod_era_are_rejected(tmp_path):
    """Tile graphics changed from codepoints to sprite ids in version 3, so older maps cannot be drawn."""
    import lzma
    import pickle
    import pytest
    import exceptions
    path = tmp_path / "v2.sav"
    path.write_bytes(lzma.compress(pickle.dumps({"version": 2, "engine": None})))
    with pytest.raises(exceptions.IncompatibleSave, match="version 2"):
        setup_game.load_game(str(path))
