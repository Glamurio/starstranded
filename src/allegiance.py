"""Which side a creature is on, and who it will attack.

Every creature belongs to one of three factions (the `faction` of its species): **wildlife** (the planet's animals), the
**Federation** (the humanoids: the people you can play, and the Selenites) and **robots**. Only a creature with a hostile AI
attacks; whom it attacks is decided here, from the sides alone:

- wildlife attacks the Federation (predators go for people), not machines or other animals;
- the Federation attacks robots;
- robots attack the Federation and wildlife;
- members of one faction leave each other alone, except a `renegade` species (the exiled cave Selenites), which turns on its own side too.

Hunting for food is a different thing (see `behavior.preys_on`): it follows the diet, not the faction. Alliances and stances between
factions are meant to grow here (trade, truces); for now it is this table."""
from __future__ import annotations

WILDLIFE = "wildlife"
FEDERATION = "federation"
ROBOT = "robot"

FACTIONS = {WILDLIFE: "Wildlife", FEDERATION: "Federation", ROBOT: "Robot"}

ENEMIES = {
    WILDLIFE: frozenset({FEDERATION}),
    FEDERATION: frozenset({ROBOT}),
    ROBOT: frozenset({FEDERATION, WILDLIFE}),
}


def faction_of(entity) -> str:
    """The faction key of a creature (a species without one is wildlife)."""
    return getattr(getattr(entity, "kind", None), "faction", WILDLIFE) or WILDLIFE


def name_of(entity) -> str:
    return FACTIONS.get(faction_of(entity), faction_of(entity).title())


def will_attack(attacker, target) -> bool:
    """Would `attacker` (if its AI is hostile) fight `target`? Sides only: no sight, no distance."""
    from entity import EntityCategory
    if attacker is target or getattr(target, "category", None) is not EntityCategory.UNIT or not getattr(target, "is_alive", False):
        return False
    mine, theirs = faction_of(attacker), faction_of(target)
    if mine == theirs:
        return bool(getattr(getattr(attacker, "kind", None), "renegade", False))
    return theirs in ENEMIES.get(mine, ())


def threatens(unit, target) -> bool:
    """Is `unit` a hostile creature that would attack `target`?"""
    ai = getattr(unit, "ai", None)
    return bool(ai is not None and ai.is_hostile and getattr(unit, "is_alive", False) and will_attack(unit, target))
