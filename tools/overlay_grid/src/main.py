"""CLI entry point for overlay grid generator."""

import argparse
import json
from pathlib import Path

from .grid import GridColors, GridSpec, render_grid

TOOL_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = TOOL_DIR / "config" / "config.json"


def _load_spec(cfg: dict) -> GridSpec:
    colors = GridColors(
        background=tuple(cfg["colors"]["background"]),
        minor=tuple(cfg["colors"]["minor"]),
        major=tuple(cfg["colors"]["major"]),
        super=tuple(cfg["colors"]["super"]),
        axis=tuple(cfg["colors"]["axis"]),
        text=tuple(cfg["colors"]["text"]),
        text_shadow=tuple(cfg["colors"]["text_shadow"]),
    )
    return GridSpec(
        width=cfg["width"],
        height=cfg["height"],
        minor_step=cfg["minor_step"],
        major_step=cfg["major_step"],
        super_step=cfg["super_step"],
        font_name=cfg.get("font_name", "arial.ttf"),
        font_size=cfg.get("font_size", 18),
        colors=colors,
    )


def _parse_hex_color(value: str) -> list[int]:
    cleaned = value.lstrip("#")
    if len(cleaned) != 6:
        raise SystemExit(f"Invalid --background value: {value!r} (expected 6-digit hex RRGGBB)")
    try:
        return [int(cleaned[i : i + 2], 16) for i in (0, 2, 4)]
    except ValueError:
        raise SystemExit(f"Invalid --background value: {value!r} (not hex)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="overlay-grid", description="Generate a coordinate grid image for use as a screen overlay or wallpaper.")
    parser.add_argument("output", nargs="?", help="Output path (PNG). Defaults to config.output_path.")
    parser.add_argument("--width", type=int, help="Image width in pixels (overrides config).")
    parser.add_argument("--height", type=int, help="Image height in pixels (overrides config).")
    parser.add_argument("--background", help="Background color as 6-digit hex RRGGBB (overrides config).")
    parser.add_argument("--variant", help="Color variant to apply (key under config.variants).")
    return parser


def _apply_variant(cfg: dict, name: str) -> None:
    variants = cfg.get("variants", {})
    if name not in variants:
        known = ", ".join(sorted(variants)) or "(none defined)"
        raise SystemExit(f"Unknown --variant {name!r}. Known: {known}")
    for key, value in variants[name].get("colors", {}).items():
        cfg["colors"][key] = value


def main() -> None:
    args = build_parser().parse_args()

    if not CONFIG_PATH.exists():
        raise SystemExit(f"Config not found: {CONFIG_PATH}")
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)

    if args.width is not None:
        cfg["width"] = args.width
    if args.height is not None:
        cfg["height"] = args.height
    if args.variant is not None:
        _apply_variant(cfg, args.variant)
    if args.background is not None:
        cfg["colors"]["background"] = _parse_hex_color(args.background)

    if args.output:
        output_path = Path(args.output)
    else:
        template = cfg.get("output_path", "overlay_grid.png")
        configured = Path(template.format(width=cfg["width"], height=cfg["height"]))
        output_path = configured if configured.is_absolute() else TOOL_DIR / configured

    spec = _load_spec(cfg)
    img = render_grid(spec)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    print(f"Saved: {output_path}")
