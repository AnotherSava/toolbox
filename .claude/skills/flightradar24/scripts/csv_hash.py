"""Fingerprint the local flights CSV so it can be compared against a live FR24 export.

The local CSV is the mirror that the sync diff and ``reconcile.py`` both trust, so
it has to be provably identical to what Flightradar24 holds. This prints the row
count, a djb2 hash of the data rows and their character count; the matching
JavaScript — which must produce the same numbers — is in
``references/fr24-export.md``.

Character count, not byte count: a JS string length counts UTF-16 code units
while the file is UTF-8, and the Cyrillic notes in this logbook make those differ.

    python .../csv_hash.py                # whole file
    python .../csv_hash.py --rows 189     # just the first N rows, for a prefix check
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CSV = REPO_ROOT / "tools" / "flightradar" / "data" / "flights.csv"


def data_rows(csv_path: Path) -> list[str]:
    """Return the CSV's data rows, dropping the leading blank line and the header."""
    text = csv_path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    return [line for line in text.split("\n") if line.strip()][1:]


def djb2(text: str) -> int:
    """djb2 hash, kept byte-for-byte compatible with the JS in references/fr24-export.md."""
    value = 5381
    for char in text:
        value = ((value * 33) ^ ord(char)) & 0xFFFFFFFF
    return value


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Fingerprint the local FR24 CSV.")
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help=f"CSV to hash (default: {DEFAULT_CSV}).")
    parser.add_argument("--rows", type=int, help="Hash only the first N data rows.")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")
    rows = data_rows(csv_path)
    if args.rows is not None:
        if args.rows > len(rows):
            raise SystemExit(f"Asked for {args.rows} rows but the CSV only has {len(rows)}.")
        rows = rows[:args.rows]
    joined = "\n".join(rows)
    print(f"rows={len(rows)} hash={djb2(joined)} chars={len(joined)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
