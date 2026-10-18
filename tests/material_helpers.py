"""Representative materials for tests (not game content)."""
from materials import Family, Material

OAKISH = Material("t:oak", "Oakish", Family.WOOD, (120, 90, 50), hardness=4, toughness=7, tenacity=5, density=5, elasticity=4,
                  insulation=5, thermal_conductivity=2, flammability=6, combustibility=7, burn_yield=40, burn_duration=8)
FLINT = Material("t:flint", "Flint", Family.STONE, (60, 60, 70), hardness=8, toughness=3, tenacity=2, abrasivity=7, density=6,
                 insulation=2, thermal_conductivity=4)
GRASS = Material("t:grass", "Dry grass", Family.FIBER, (200, 190, 90), hardness=1, toughness=1, tenacity=4, density=1,
                 flammability=9, combustibility=2, burn_yield=3, burn_duration=1)
COAL = Material("t:coal", "Coal", Family.FUEL, (20, 20, 20), hardness=3, toughness=2, density=4, flammability=4,
                combustibility=9, burn_yield=120, burn_duration=20)
SAND = Material("t:sand", "Quartz sand", Family.SAND, (230, 220, 180), hardness=6, toughness=1, density=4, abrasivity=6,
                transparency=3, is_amorphous=True, melting_point=1700)
COPPER = Material("t:copper", "Copper", Family.METAL, (190, 110, 60), hardness=4, toughness=7, tenacity=8, density=8,
                  electrical_conductivity=9, thermal_conductivity=9, melting_point=1080)
VINE = Material("t:vine", "Vine", Family.FIBER, (60, 120, 50), toughness=3, tenacity=8, elasticity=5, flammability=6,
                combustibility=3, burn_yield=5, burn_duration=2)


def make_material(name: str, family: Family, **props) -> Material:
    """A throwaway material for a test (id `t:<name>`, grey)."""
    return Material(f"t:{name}", name.capitalize(), family, (128, 128, 128), **props)
