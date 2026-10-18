import pygame
import pytest

import atlas
import ui


@pytest.fixture
def canvas():
    pygame.display.init()
    pygame.display.set_mode((64, 64))
    surface = pygame.Surface((80 * 24, 45 * 24))
    return ui.Canvas(surface, ui.Font.load(), atlas.SpriteAtlas.load("urizen_white.png"))


def lit(canvas, x, y, w=1, h=1):
    """Number of non-black pixels in a cell rectangle."""
    sub = canvas.surface.subsurface(canvas.cell_rect(x, y, w, h))
    arr = pygame.surfarray.array3d(sub)
    return int((arr.sum(axis=2) > 0).sum())


def test_canvas_geometry(canvas):
    assert (canvas.width, canvas.height) == (80, 45)


def test_font_glyph_is_white_mask(canvas):
    glyph = canvas.font.glyph(ord("A"))
    assert glyph.get_size() == (24, 24)
    alpha = pygame.surfarray.array_alpha(glyph)
    assert 10 < (alpha > 0).sum() < 24 * 24 // 2
    assert canvas.font.glyph(ord("A")) is canvas.font.glyph(ord("A"))


def test_print_draws_in_the_right_cells(canvas):
    canvas.print(3, 2, "Hello!", fg=(255, 0, 0))     # 6 characters of 12 px = 3 cells
    assert lit(canvas, 3, 2) and lit(canvas, 4, 2) and lit(canvas, 5, 2)
    assert not lit(canvas, 2, 2) and not lit(canvas, 6, 2) and not lit(canvas, 3, 3)
    arr = pygame.surfarray.array3d(canvas.surface.subsurface(canvas.cell_rect(3, 2, 3, 1)))
    pixels = arr.reshape(-1, 3)
    lit_pixels = pixels[pixels.sum(axis=1) > 0]
    assert len(lit_pixels) and (lit_pixels[:, 1] == 0).all() and (lit_pixels[:, 2] == 0).all()   # red, antialiased


def test_text_is_two_characters_per_cell(canvas):
    assert canvas.font.width("MMMMMMMMMM") == 120 and canvas.text_width("MMMMMMMMMM") == 5
    assert canvas.chars(10) == 20


def test_wrap_fits_the_width(canvas):
    lines = canvas.wrap("one two three four five six seven eight nine ten", 6)   # 12 characters per line
    assert all(len(line) <= 12 for line in lines) and " ".join(lines) == "one two three four five six seven eight nine ten"


def test_print_alignment(canvas):
    canvas.print(40, 5, "abcdefgh", alignment=ui.CENTER)      # 96 px wide, centred on x = 40 * 24
    assert lit(canvas, 38, 5) and lit(canvas, 41, 5) and not lit(canvas, 37, 5) and not lit(canvas, 42, 5)
    canvas.print(10, 7, "wxyz", alignment=ui.RIGHT)           # 48 px, ending at the right edge of cell 10
    assert lit(canvas, 9, 7) and lit(canvas, 10, 7) and not lit(canvas, 8, 7) and not lit(canvas, 11, 7)


def test_print_multiline_and_bg(canvas):
    canvas.print(1, 1, "a\nb", bg=(0, 0, 90))
    assert canvas.surface.get_at((1 * 24 + 2, 1 * 24 + 23))[:3] == (0, 0, 90)
    assert canvas.surface.get_at((1 * 24 + 2, 2 * 24 + 23))[:3] == (0, 0, 90)
    assert lit(canvas, 1, 1) and lit(canvas, 1, 2)


def test_print_clips_to_canvas(canvas):
    canvas.print(78, 0, "abcdef")  # runs off the right edge
    canvas.print(0, 44, "bottom")
    canvas.print(0, 45, "below")  # off the bottom: ignored
    assert lit(canvas, 79, 0)


def test_unknown_characters_become_question_marks(canvas):
    assert ui.cp437_index("é") == 0x82
    assert ui.cp437_index("☃") == ord("?")


def test_frame_has_corners_edges_and_title(canvas):
    canvas.draw_frame(5, 5, 10, 4, title="Hello")
    for cell in [(5, 5), (14, 5), (5, 8), (14, 8), (8, 8), (5, 6), (14, 7)]:
        assert lit(canvas, *cell), cell
    assert canvas.surface.get_at((8 * 24 + 12, 7 * 24 + 12))[:3] == ui.Theme.BG   # the interior is clear glass
    assert lit(canvas, 10, 5)  # title overlays the top edge


def test_frame_clear_fills_interior_unless_disabled(canvas):
    canvas.fill(0, 0, 20, 20, (50, 50, 50))
    canvas.draw_frame(2, 2, 6, 4, clear=False)
    assert canvas.surface.get_at((4 * 24 + 1, 3 * 24 + 1))[:3] == (50, 50, 50)
    canvas.draw_frame(2, 2, 6, 4, clear=True)
    assert canvas.surface.get_at((4 * 24 + 1, 3 * 24 + 1))[:3] == ui.Theme.BG


def test_bar_fill_proportion(canvas):
    canvas.draw_bar(0, 0, 20, 5, 10, (0, 96, 0), (64, 16, 16), (255, 255, 255), "HP")
    assert canvas.surface.get_at((1, 1))[:3] == (0, 96, 0)
    assert canvas.surface.get_at((19 * 24 + 1, 1))[:3] == (64, 16, 16)
    assert canvas.surface.get_at((9 * 24 + 23, 23))[:3] in ((0, 96, 0), (255, 255, 255))
    assert canvas.surface.get_at((10 * 24 + 23, 23))[:3] in ((64, 16, 16), (255, 255, 255))


def test_sprite_blits_at_cell(canvas):
    canvas.sprite(10, 10, atlas.sprite_id(0, 9), (255, 255, 0))
    assert lit(canvas, 10, 10) and not lit(canvas, 9, 10) and not lit(canvas, 11, 10)


def test_highlight_blends_and_keeps_sprite(canvas):
    canvas.fill(3, 3, 1, 1, (100, 0, 0))
    canvas.highlight(3, 3, (255, 255, 255), 100)
    r, g, b = canvas.surface.get_at((3 * 24 + 2, 3 * 24 + 2))[:3]
    assert r > 100 and g > 0 and b > 0


def test_dim_darkens(canvas):
    canvas.fill(0, 0, 4, 4, (200, 200, 200))
    canvas.dim(8)
    assert canvas.surface.get_at((5, 5))[0] <= 200 // 8 + 1


def test_blit_image_covers_canvas(canvas):
    image = pygame.Surface((160, 100))
    image.fill((10, 200, 30))
    canvas.blit_image(image)
    assert canvas.surface.get_at((0, 0))[:3] == (10, 200, 30)
    assert canvas.surface.get_at((canvas.surface.get_width() - 1, canvas.surface.get_height() - 1))[:3] == (10, 200, 30)
