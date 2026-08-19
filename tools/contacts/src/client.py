"""Google People API client.

Credentials come from Doppler (project ``toolbox``, config ``dev``) as two
environment variables, so anything touching Contacts runs under
``doppler run -- …``. As with the Notion client there is deliberately no on-disk
fallback — a second copy in a config file is the per-machine drift Doppler
prevents, and it would put a live refresh token back in plaintext.

``GOOGLE_OAUTH_CLIENT_JSON`` is the Desktop client downloaded from the Google
Cloud Console; ``GOOGLE_CONTACTS_REFRESH_TOKEN`` is minted once by
``contacts authorize``.
"""

import json
import os
from typing import Any, Iterator

from google.auth.transport.requests import AuthorizedSession
from google.oauth2.credentials import Credentials

CLIENT_ENV = "GOOGLE_OAUTH_CLIENT_JSON"
REFRESH_TOKEN_ENV = "GOOGLE_CONTACTS_REFRESH_TOKEN"

TOKEN_URI = "https://oauth2.googleapis.com/token"
API_ROOT = "https://people.googleapis.com/v1"

# contacts.readonly covers the contact list and its labels; contacts.other.readonly
# is a separate grant for the auto-collected "Other contacts" bucket, which Google
# will not let you export from the web UI at all.
SCOPES = [
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/contacts.other.readonly",
]

# People API caps every list endpoint used here at 1000 per page.
PAGE_SIZE = 1000

_SETUP_HINT = (
    "Run the command through Doppler:  doppler run -- <command>\n"
    "First time on this machine:       doppler login && doppler setup\n"
    "No credentials yet:               see tools/contacts/docs/setup.md"
)


def load_client_config() -> dict[str, Any]:
    """Return the OAuth client config from ``GOOGLE_OAUTH_CLIENT_JSON``."""
    raw = os.environ.get(CLIENT_ENV)
    if not raw:
        raise SystemExit(f"{CLIENT_ENV} is not set — Google credentials live in Doppler.\n{_SETUP_HINT}")
    try:
        config = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{CLIENT_ENV} is not valid JSON ({exc}) — store the Console download verbatim.")
    if "installed" not in config and "web" not in config:
        raise SystemExit(f"{CLIENT_ENV} has no 'installed' or 'web' key — download the Desktop app client, not a service account key.")
    return config


class ContactsClient:
    """Read-only Google People API client."""

    def __init__(self, session: AuthorizedSession):
        self.session = session

    def _paginate(self, path: str, params: dict[str, Any], key: str) -> Iterator[dict[str, Any]]:
        """Yield every item under ``key``, following ``nextPageToken`` to the end."""
        page_token = None
        while True:
            query = {**params, "pageSize": PAGE_SIZE}
            if page_token:
                query["pageToken"] = page_token
            response = self.session.get(f"{API_ROOT}/{path}", params=query)
            if not response.ok:
                raise SystemExit(f"People API {path} failed ({response.status_code}): {response.text}")
            payload = response.json()
            yield from payload.get(key, [])
            page_token = payload.get("nextPageToken")
            if not page_token:
                return

    def list_contact_groups(self) -> list[dict[str, Any]]:
        """Return every contact group (label), system and user-created alike."""
        # formattedName is output-only and rejected as a mask path; name carries the
        # label exactly as the user typed it, which is what the reports display.
        params = {"groupFields": "name,groupType,memberCount"}
        return list(self._paginate("contactGroups", params, "contactGroups"))

    def list_connections(self) -> list[dict[str, Any]]:
        """Return every saved contact with its names, emails, phones and label memberships."""
        params = {
            "personFields": "names,emailAddresses,phoneNumbers,organizations,memberships",
            "sortOrder": "FIRST_NAME_ASCENDING",
        }
        return list(self._paginate("people/me/connections", params, "connections"))

    def list_other_contacts(self) -> list[dict[str, Any]]:
        """Return the auto-collected "Other contacts".

        Google restricts this bucket to names, emails and phone numbers — asking
        for anything else is rejected outright, not silently dropped.
        """
        params = {"readMask": "names,emailAddresses,phoneNumbers"}
        return list(self._paginate("otherContacts", params, "otherContacts"))


def create_client() -> ContactsClient:
    """Create a ContactsClient from the Doppler-supplied environment variables."""
    config = load_client_config()
    refresh_token = os.environ.get(REFRESH_TOKEN_ENV)
    if not refresh_token:
        raise SystemExit(
            f"{REFRESH_TOKEN_ENV} is not set — you have an OAuth client but have not consented yet.\n"
            f"Run:  doppler run -- contacts authorize"
        )
    client = config.get("installed") or config["web"]
    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client["client_id"],
        client_secret=client["client_secret"],
        token_uri=client.get("token_uri", TOKEN_URI),
        scopes=SCOPES,
    )
    return ContactsClient(AuthorizedSession(credentials))
