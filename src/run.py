"""State of one playthrough that is not terrain: mode, reputation, contracts, discoveries, escape progress.

Plain data (dicts, lists, small dataclasses) so a save never pickles live objects. Lives on `GameWorld.run` and is written
into the save manifest (save version 8).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from knowledge import Knowledge

ROGUELIKE = "roguelike"
CASUAL = "casual"
MODES = (ROGUELIKE, CASUAL)
MODE_TEXT = {
    ROGUELIKE: "Roguelike: one life. Death ends the run and deletes the save.",
    CASUAL: "Casual: sleep in a bed to save; on death you wake at your last bed.",
}


@dataclass
class RunState:
    mode: str = ROGUELIKE
    seed: int = 0
    sponsor: Optional[str] = None
    credits: int = 0
    reputation: Dict[str, int] = field(default_factory=dict)
    delivered: Dict[str, Dict[str, int]] = field(default_factory=dict)   # sponsor -> category -> count (market saturation)
    contracts: list = field(default_factory=list)
    completed: List[str] = field(default_factory=list)
    knowledge: Knowledge = field(default_factory=Knowledge)
    knowledge_spent: int = 0
    pod: Optional[Tuple[int, int]] = None                                  # the cargo pod beside the wreck
    wreck: Optional[Tuple[int, int]] = None
    flags: Dict[str, object] = field(default_factory=dict)                  # escape progress, found sites, beacon ...
    ending: Optional[str] = None
    bed: Optional[Tuple[int, int, int]] = None                              # casual mode: (x, y, z) of the last bed slept in
    deaths: int = 0
    kills: Dict[str, int] = field(default_factory=dict)                   # species key -> creatures the player killed
    hunt_targets: list = field(default_factory=list)                        # (species key, name, danger) a sponsor may ask for
    tracker_charge: Tuple[int, int] = (5, 0)                                # (charges stored, game time they were counted)
