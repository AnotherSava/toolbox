from overlay_grid.grid import GridColors, GridSpec, render_grid


def _default_spec(width: int = 200, height: int = 100) -> GridSpec:
    colors = GridColors(
        background=(0, 0, 0),
        minor=(10, 10, 10),
        major=(20, 20, 20),
        super=(30, 30, 30),
        axis=(40, 40, 40),
        text=(255, 255, 255),
        text_shadow=(0, 0, 0),
    )
    return GridSpec(
        width=width,
        height=height,
        minor_step=10,
        major_step=50,
        super_step=100,
        font_name="arial.ttf",
        font_size=12,
        colors=colors,
    )


def test_render_returns_image_with_expected_size():
    spec = _default_spec(width=200, height=100)
    img = render_grid(spec)
    assert img.size == (200, 100)
    assert img.mode == "RGB"


def test_background_color_applied_off_grid():
    spec = _default_spec(width=200, height=100)
    img = render_grid(spec)
    # Pixel not on any grid line or axis should retain background color
    assert img.getpixel((5, 5)) == (0, 0, 0)


def test_axis_drawn_on_first_row_and_column():
    spec = _default_spec(width=200, height=100)
    img = render_grid(spec)
    # Axis color should appear along y=0 away from origin text
    assert img.getpixel((150, 0)) == (40, 40, 40)
    assert img.getpixel((0, 80)) == (40, 40, 40)
