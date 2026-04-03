"""CLI entry point for Notion workspace management tools."""

import argparse
import sys

from .clear_teamspace import main as clear_teamspace_main
from .clear_trash import main as clear_trash_main
from .md_size_report import main as md_size_report_main


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with subcommands."""
    parser = argparse.ArgumentParser(prog="notion", description="Notion workspace management tools.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("clear-trash", help="Permanently delete all trashed pages")
    sub.add_parser("clear-teamspace", help="Delete all pages from a teamspace")
    sub.add_parser("md-size-report", help="Analyze Evernote markdown exports by size")
    return parser


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    commands = {
        "clear-trash": clear_trash_main,
        "clear-teamspace": clear_teamspace_main,
        "md-size-report": md_size_report_main,
    }
    sys.exit(commands[args.command]())
