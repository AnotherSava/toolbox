"""One-time OAuth consent, storing the resulting refresh token in Doppler.

The token is piped straight into the Doppler CLI over stdin and never printed.
Echoing it would put a live credential in the session transcript, and passing it
as a command-line argument would put it in shell history.
"""

import argparse
import shutil
import subprocess
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

from .client import REFRESH_TOKEN_ENV, SCOPES, load_client_config

DOPPLER_PROJECT = "toolbox"
DOPPLER_CONFIG = "dev"


def _store_in_doppler(refresh_token: str) -> None:
    """Write the refresh token to Doppler over stdin, printing nothing."""
    if not shutil.which("doppler"):
        raise SystemExit("doppler CLI not found on PATH — install it, then re-run 'contacts authorize'.")
    result = subprocess.run(
        ["doppler", "secrets", "set", REFRESH_TOKEN_ENV, "-p", DOPPLER_PROJECT, "-c", DOPPLER_CONFIG, "--silent"],
        input=refresh_token,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"doppler secrets set failed ({result.returncode}): {result.stderr.strip()}")


def main() -> int:
    """Run the installed-app consent flow and persist the refresh token."""
    parser = argparse.ArgumentParser(description="Grant this tool read-only access to your Google Contacts.")
    parser.add_argument("--port", type=int, default=0, help="local port for the OAuth redirect (default: pick a free one)")
    args = parser.parse_args()

    flow = InstalledAppFlow.from_client_config(load_client_config(), scopes=SCOPES)
    # prompt=consent forces a fresh refresh token; without it Google returns none
    # on re-authorisation and the tool silently keeps the old, possibly expired one.
    credentials = flow.run_local_server(port=args.port, prompt="consent")

    if not credentials.refresh_token:
        raise SystemExit("Google returned no refresh token — revoke the app at myaccount.google.com/permissions and retry.")

    _store_in_doppler(credentials.refresh_token)
    print(f"Stored {REFRESH_TOKEN_ENV} in Doppler ({DOPPLER_PROJECT}/{DOPPLER_CONFIG}).", file=sys.stderr)
    print("Try it:  doppler run -- contacts labels", file=sys.stderr)
    return 0
