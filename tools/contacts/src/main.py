"""CLI entry point for Google Contacts tools."""

import sys

from .authorize import main as authorize_main
from .report import labels_main, other_main, show_main, unlabeled_main


COMMANDS = {
    "authorize": authorize_main,
    "labels": labels_main,
    "unlabeled": unlabeled_main,
    "other": other_main,
    "show": show_main,
}


def main() -> None:
    """CLI entry point. Dispatches to a subcommand and forwards remaining args to it."""
    # Contact names are arbitrary Unicode, but a Windows console defaults to a legacy
    # codepage (cp1251 here) and raises UnicodeEncodeError on the first name outside it.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        cmds = ", ".join(COMMANDS)
        print(f"usage: contacts <command> [args...]\n\ncommands: {cmds}", file=sys.stderr)
        sys.exit(2 if len(sys.argv) >= 2 else 0)
    name = sys.argv[1]
    sys.argv = [f"contacts {name}", *sys.argv[2:]]
    sys.exit(COMMANDS[name]())
