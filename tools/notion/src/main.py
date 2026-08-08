"""CLI entry point for Notion workspace management tools."""

import sys

from .clear_teamspace import main as clear_teamspace_main
from .clear_trash import main as clear_trash_main
from .optimize_images import main as optimize_images_main


COMMANDS = {
    "clear-trash": clear_trash_main,
    "clear-teamspace": clear_teamspace_main,
    "optimize-images": optimize_images_main,
}


def main() -> None:
    """CLI entry point. Dispatches to a subcommand and forwards remaining args to it."""
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        cmds = ", ".join(COMMANDS)
        print(f"usage: notion <command> [args...]\n\ncommands: {cmds}", file=sys.stderr)
        sys.exit(2 if len(sys.argv) >= 2 else 0)
    name = sys.argv[1]
    sys.argv = [f"notion {name}", *sys.argv[2:]]
    sys.exit(COMMANDS[name]())
