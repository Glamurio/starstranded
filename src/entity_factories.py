from components.ai import HostileEnemy
from components import consumable, equippable
from components.equipment import Equipment
from components.unit import Unit
from components.inventory import Inventory
from components.level import Level
from entity import Actor, Item

import color

# Actors
player = Actor(
    char="@",
    color=(255, 255, 255),
    name="Ardan",
    type="Player",
    ai_cls=HostileEnemy,
    equipment=Equipment(),
    unit=Unit(hp=30, base_defense=1, base_power=2),
    inventory=Inventory(capacity=26),
    level=Level(level_up_base=100, xp_given=50),
)
orc = Actor(
    char="o",
    color=(63, 127, 63),
    name="Grugg",
    type="Orc",
    ai_cls=HostileEnemy,
    equipment=Equipment(),
    unit=Unit(hp=10, base_defense=0, base_power=3),
    inventory=Inventory(capacity=0),
    level=Level(level_up_base=100, xp_given=35),
)
troll = Actor(
    char="T",
    color=(0, 127, 0),
    type="Troll",
    ai_cls=HostileEnemy,
    equipment=Equipment(),
    unit=Unit(hp=16, base_defense=1, base_power=4),
    inventory=Inventory(capacity=0),
    level=Level(level_up_base=100, xp_given=35),
)

# Items
meat = Item(
    char="d",
    color=color.red,
    type="Meat",
    consumable=consumable.FoodConsumable(hunger_amount=10),
)
confusion_scroll = Item(
    char="~",
    color=(207, 63, 255),
    type="Confusion Scroll",
    consumable=consumable.ConfusionConsumable(number_of_turns=10),
)
fireball_scroll = Item(
    char="~",
    color=(255, 0, 0),
    type="Fireball Scroll",
    consumable=consumable.FireballDamageConsumable(damage=12, radius=3),
)
health_potion = Item(
    char="!",
    color=(127, 0, 255),
    type="Health Potion",
    consumable=consumable.HealingConsumable(amount=4),
)
lightning_scroll = Item(
    char="~",
    color=(255, 255, 0),
    type="Lightning Scroll",
    consumable=consumable.LightningDamageConsumable(damage=20, maximum_range=5),
)

dagger = Item(
    char="/",
    color=(0, 191, 255),
    material="Bronze",
    type="Dagger",
    equippable=equippable.Dagger()
)

sword = Item(
    char="/",
    color=(0, 191, 255),
    material="Iron",
    type="Sword",
    equippable=equippable.Sword()
)

leather_armor = Item(
    char="[",
    color=color.brown,
    material="Leather",
    type="Armor",
    equippable=equippable.LeatherArmor(),
)

chain_mail = Item(
    char="[", color=(139, 69, 19),
    material="Iron",
    type="Chain Mail",
    equippable=equippable.ChainMail()
)