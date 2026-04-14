"""Render a coordinate grid image usable as a screen overlay or wallpaper."""

from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class GridColors:
    background: tuple[int, int, int]
    minor: tuple[int, int, int]
    major: tuple[int, int, int]
    super: tuple[int, int, int]
    axis: tuple[int, int, int]
    text: tuple[int, int, int]
    text_shadow: tuple[int, int, int]


@dataclass(frozen=True)
class GridSpec:
    width: int
    height: int
    minor_step: int
    major_step: int
    super_step: int
    font_name: str
    font_size: int
    colors: GridColors


def _load_font(name: str, size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(name, size)
    except OSError:
        return ImageFont.load_default()


def render_grid(spec: GridSpec) -> Image.Image:
    """Render the coordinate grid and return the resulting image."""
    img = Image.new("RGB", (spec.width, spec.height), spec.colors.background)
    draw = ImageDraw.Draw(img)

    for x in range(0, spec.width + 1, spec.minor_step):
        if x % spec.major_step != 0:
            draw.line([(x, 0), (x, spec.height)], fill=spec.colors.minor, width=1)
    for y in range(0, spec.height + 1, spec.minor_step):
        if y % spec.major_step != 0:
            draw.line([(0, y), (spec.width, y)], fill=spec.colors.minor, width=1)

    for x in range(0, spec.width + 1, spec.major_step):
        draw.line([(x, 0), (x, spec.height)], fill=spec.colors.major, width=1)
    for y in range(0, spec.height + 1, spec.major_step):
        draw.line([(0, y), (spec.width, y)], fill=spec.colors.major, width=1)

    for x in range(0, spec.width + 1, spec.super_step):
        draw.line([(x, 0), (x, spec.height)], fill=spec.colors.super, width=2)
    for y in range(0, spec.height + 1, spec.super_step):
        draw.line([(0, y), (spec.width, y)], fill=spec.colors.super, width=2)

    draw.line([(0, 0), (spec.width, 0)], fill=spec.colors.axis, width=2)
    draw.line([(0, 0), (0, spec.height)], fill=spec.colors.axis, width=2)

    font = _load_font(spec.font_name, spec.font_size)
    row_x = 6
    col_y = 6

    def draw_text_with_shadow(x: int, y: int, text: str, anchor: str | None = None) -> None:
        draw.text((x + 1, y + 1), text, fill=spec.colors.text_shadow, font=font, anchor=anchor)
        draw.text((x, y), text, fill=spec.colors.text, font=font, anchor=anchor)

    draw_text_with_shadow(row_x, col_y, "0")
    for x in range(spec.major_step, spec.width + 1, spec.major_step):
        draw_text_with_shadow(x, col_y, str(x), anchor="ma")
    for y in range(spec.major_step, spec.height + 1, spec.major_step):
        draw_text_with_shadow(row_x, y, str(y), anchor="lm")

    return img
