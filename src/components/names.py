color_names = {
    "Red": ['Red', 'Ruby', 'Crab', 'Maroon', 'Scorpion', 'Blood', 'Hot', 'Rot', 'Crimson', 'Scarlet', 'Dragon', 'Flame', 'Fire', 'Flare', 'Burgundy', 'Ribbon', 'Cardinal', 'Torch'],
    "Orange": ['Atom', 'Saffron', 'Tiger', 'Tabby', 'Fox', 'Scotch', 'Hunyadi', 'Xanthic', 'Ochre', 'Soda', 'Honey', 'Copper', 'Calico', 'Rust', 'Coral', 'Sunset'],
    "Yellow": ['Amber', 'Sulfur', 'Royal', 'Duck', 'Finch', 'Yolk', 'Blonde', 'Bee', 'Yellow', 'Sunny', 'Sunlight', 'Sunshine', 'Gold', 'Golden', 'Peridot', 'Citrine', 'Butter', 'Mustard'],
    "Green": ['Viper', 'Poison', 'Frog', 'Parrot', 'Venom', 'Lush', 'Slime', 'Green', 'Evergreen', 'Emerald', 'Druid', 'Malachite', 'Forest', 'Jungle', 'Sage', 'Moss'],
    "Blue": ['Periwinkle', 'Savoy', 'Neon', 'Peacock', 'Lizard', 'Jean', 'Marine',  'Navy', 'Fish', 'Azure', 'Water', 'Vermeer', 'Mystic', 'Sapphire', 'Ocean', 'Seashore', 'Blue'],
    "Violet": ['Vivid', 'Violet', 'Beetle', 'Amethyst', 'Rose', 'Bordeaux', 'Velvet', 'Fuschia', 'Candy', 'Orchid', 'Lilac', 'Wisteria', 'Hyacinth'],
    "Brown": ['Auburn', 'Burnt', 'Brown', 'Coffee', 'Caramel', 'Muffin', 'Chocolate', 'Oak', 'Bark', 'Chestnut', 'Mocha', 'Toffee', 'Cocoa', 'Timber'],
    "White": ['White', 'Quartz', 'Angel', 'Snow', 'Ivory', 'Light', 'Milk', 'Paper', 'Bone', 'Cloud', 'Cream', 'Shell', 'Steam', 'Ghost', 'Aether'],
    "Black": ['Black', 'Obsidian', 'Night', 'Black', 'Midnight', 'Oil', 'Ebony', 'Onyx', 'Darkness', 'Nebula', 'Chaos', 'Angst', 'Slate', 'Dark', 'Coal', 'Asphalt', 'Space', 'Soot'],
    "Gray": ['Gray', 'Silver', 'Metal', 'Rock', 'Stone', 'Fog', 'Rat', 'Mouse', 'Ash', 'Cloud', 'Storm', 'Steel', 'Lead', 'Smoke', 'Platinum', 'Flint', 'Sepia', 'Ashen'],
    "Cyan": ['Prisma', 'Celeste', 'Keppel', 'Myrtle', 'Turquoise', 'Verdigris', 'Robin', 'Chroma', 'Cyan', 'Teal', 'Cerulean', 'Azure', 'Ice', 'Aqua', 'Frost', 'Sky'],
    "Magenta": ['Magenta', 'Amaranth', 'Fuchsia', 'Violet', 'Purple', 'Pansy', 'Lavender', 'Purple', 'Indigo', 'Razzle', 'Finn', 'Axolotl'],
    "Rose": ['Rose', 'Coral', 'Salmon', 'Sunset', 'Flamingo', 'Peach', 'Apricot', 'Mauve', 'Lily', 'Carnation', 'Pale', 'Galah', 'Sakura', 'Pig']
}
# TODO: Separate "Vegetables" from "Fruits"
fruit_pos_names = {
    (0, 5): ["flower", "blossom", "bud"],
    (0, 16): ["shroom", "broccoli"],
    (2, 16): ["carrot"],
    (3, 16): ["apple", "peach", "mango", "apricot", "fruit", "plum"],
    (4, 16): ["chili", "licorice", "currant", "spice", "pepper", "pea", "cinnamon", "vine", "stalk"],
    (6, 16): ["cherry"],
    (8, 16): ["pear", "seeds", "durian", "nut", "mellow", "lychee"],
    (9, 16): ["leaf", "grass", "nettle", "petal", "lichen"],
    (10, 16): ["pumpkin", "tomato"],
    (12, 16): ["grapes", "pea", "raisin", "cocoa"],
    (13, 16): ["acorn"],
    (15, 16): ["orange", "lemon", "citrus", "lime"],
    (16, 16): ["potato"],
    (17, 16): ["beans", "peanut", "date"],
    (18, 16): ["berry"],
    (19, 16): ["banana"],
    (20, 16): ["sugar", "corn", "maize"],                        
    (21, 16): ["turnip", "beet", "root"],
    (22, 16): ["herb", "algae", "leek", "onion"],
    (23, 16): ["turnip", "beet", "root"],
    (24, 16): ["physalis"]
}
tree_pos_names = {
    (0, 4): ["Oak", "Maple", "Beech", "Sycamore"],
    (1, 4): ["Elm", "Birch", "Hickory", "Plumeria", "Poplar"],
    (2, 4): ["Willow", "Acacia", "Jacaranda"],
    (3, 4): ["Pine", "Fir", "Larch", "Spruce", "Hemlock"],
    (4, 4): ["Cypress", "Linden", "Cedar", "Juniper"],
    (5, 4): ["Fungi", "Morel", "Chanterelle", "Portabello"],
    (9, 4): ["Cactus", "Succulent", "Cereus"],
    (10, 4): ["Cactus", "Succulent", "Cereus"],
    (11, 4): ["Palm", "Longtree"]
}
shrub_pos_names = {
    (17, 4): ["Reeds", "Canes", "Grass", "Weeds"],
    (18, 4): ["Bush", "Shrub", "Hedge"],
    (19, 4): ["Thorns", "Thistle", "Fern"],
}