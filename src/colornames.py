"""Everyday names for RGB colours: the nearest entry of a table of web colour names (perceptual distance, CIE Lab), so a thing
drawn in (110, 140, 60) is called "olive drab" and not by a fixed hue class. Ordinary English words only: names of web colours
that are compounds of "light/dark/medium" are left out, because the nearest plain name reads better in a creature or plant name."""
from typing import Dict, List, Sequence, Tuple

RGB = Tuple[int, int, int]

_HEX = """
black 000000;navy 000080;blue 0000ff;green 008000;teal 008080;lime 00ff00;aqua 00ffff;indigo 4b0082;maroon 800000;purple 800080;
olive 808000;grey 808080;silver c0c0c0;red ff0000;magenta ff00ff;orange ffa500;yellow ffff00;white ffffff;fuchsia ff00ff;
aquamarine 7fffd4;azure f0ffff;beige f5f5dc;bisque ffe4c4;brown a52a2a;burlywood deb887;cadet 5f9ea0;chartreuse 7fff00;
chocolate d2691e;coral ff7f50;cornflower 6495ed;cornsilk fff8dc;crimson dc143c;cyan 00ffff;firebrick b22222;forest 228b22;
gainsboro dcdcdc;gold ffd700;goldenrod daa520;honeydew f0fff0;hotpink ff69b4;ivory fffff0;khaki f0e68c;lavender e6e6fa;
lemon fffacd;limegreen 32cd32;linen faf0e6;mint 98ff98;moccasin ffe4b5;olivedrab 6b8e23;orchid da70d6;peach ffdab9;peru cd853f;
pink ffc0cb;plum dda0dd;rose ff007f;royal 4169e1;saddle 8b4513;salmon fa8072;sand f4a460;sea 2e8b57;shell fff5ee;sienna a0522d;
sky 87ceeb;slate 708090;snow fffafa;spring 00ff7f;steel 4682b4;tan d2b48c;thistle d8bfd8;tomato ff6347;turquoise 40e0d0;
violet ee82ee;wheat f5deb3;amber ffbf00;apricot fbceb1;bronze cd7f32;cardinal c41e3a;cerulean 2a52be;cobalt 0047ab;copper b87333;
cream fffdd0;emerald 50c878;jade 00a86b;lilac c8a2c8;mauve e0b0ff;mustard e1ad01;ochre cc7722;periwinkle ccccff;pewter 8e9196;
ruby e0115f;russet 80461b;rust b7410e;saffron f4c430;sage 9caf88;sapphire 0f52ba;scarlet ff2400;sepia 704214;straw e4d96f;
umber 635147;verdigris 43b3ae;viridian 40826d;lichen 9aa98a;moss 8a9a5b;ash b2beb5;dun 9f8e74;ink 1c1c2b;midnight 191970;
mulberry c54b8c;clay b66a50;charcoal 36454f;fern 4f7942;pine 01796f;ebony 3b3a30;cinnamon d2691e;fawn e5aa70;taupe 8b7765;
blush de5d83;wine 722f37;terracotta e2725b;marigold eaa221;lagoon 3a9ba0;denim 1560bd;heather 9e82b4;orchid2 b565a7
"""

NAMES: List[Tuple[str, RGB]] = []
for _item in _HEX.replace("\n", "").split(";"):
    _name, _hex = _item.strip().split(" ")
    if _name.endswith("2"):
        _name = _name[:-1]
    NAMES.append((_name.replace("hotpink", "hot pink").replace("limegreen", "lime green").replace("olivedrab", "olive drab"),
                  (int(_hex[0:2], 16), int(_hex[2:4], 16), int(_hex[4:6], 16))))
_NAMES_FIX = {"cadet": "cadet blue", "cornflower": "cornflower blue", "forest": "forest green", "royal": "royal blue", "saddle": "saddle brown",
              "sea": "sea green", "spring": "spring green", "steel": "steel blue", "slate": "slate grey", "sky": "sky blue", "sand": "sandy", "lemon": "lemon"}
NAMES = [(_NAMES_FIX.get(n, n), c) for n, c in NAMES]


def _lab(rgb: Sequence[float]) -> Tuple[float, float, float]:
    def lin(c: float) -> float:
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb)
    x, y, z = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047, 0.2126 * r + 0.7152 * g + 0.0722 * b, (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


_LAB = [(name, _lab(c)) for name, c in NAMES]


def nearest(color: Sequence[float], count: int = 1) -> List[str]:
    """The `count` names closest to `color`, best first (grey names are for colours with almost no hue)."""
    lab = _lab(color)
    ranked = sorted(_LAB, key=lambda item: sum((a - b) ** 2 for a, b in zip(item[1], lab)))
    return [name for name, _ in ranked[:count]]


def name_of(color: Sequence[float]) -> str:
    return nearest(color)[0]
