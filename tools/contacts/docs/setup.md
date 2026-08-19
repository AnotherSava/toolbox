# Contacts tool setup

One-time work to give the tool read-only access to your Google Contacts. Creating an
OAuth client is Console-only — Google exposes no API for minting client IDs — so this
part cannot be scripted. Everything after it can.

## 1. Create the OAuth client

1. **Enable the People API** for a Google Cloud project (create one if you have none):
   <https://console.cloud.google.com/apis/library/people.googleapis.com>
2. **Configure the consent screen** at <https://console.developers.google.com/auth/branding>.
   If you see "Google Auth platform not configured yet", click **Get Started**. Fill in an
   app name and your support email.
3. Under **Google Auth platform → Audience**, choose **External**. The quickstart says
   *Internal*, but that option only exists for Workspace organisations — a personal
   `@gmail.com` account has no organisation and must use External.
4. Still under **Audience**, set the publishing status to **In production**. See
   [Why "In production"](#why-in-production) below — leaving it on *Testing* expires your
   refresh token every 7 days. Unverified is fine; you will click through a warning screen
   once during step 6.
5. **Create the client** at <https://console.developers.google.com/auth/clients> →
   **Create Client** → application type **Desktop app**. Download the JSON.

## 2. Store the client JSON in Doppler

Run this in a terminal, from wherever you saved the download. Piping over stdin keeps the
value out of your shell history:

```
printf '%s' "$(cat {{path-to-downloaded-client.json}})" | doppler secrets set GOOGLE_OAUTH_CLIENT_JSON --silent
```

Then delete the downloaded file — Doppler is the only copy that should exist.

## 3. Consent once

```
doppler run -- contacts authorize
```

This opens a browser, asks you to grant read-only Contacts access, and writes the resulting
refresh token straight to Doppler as `GOOGLE_CONTACTS_REFRESH_TOKEN`. The token is never
printed and never passed as a command-line argument.

On the "Google hasn't verified this app" screen, choose **Advanced → Go to \<app name\>**.
That warning is expected for a personal app and does not affect how the tool works.

## Usage

```
doppler run -- contacts labels        # contact count per label
doppler run -- contacts unlabeled     # contacts carrying no label
doppler run -- contacts show          # every contact with its labels
doppler run -- contacts other         # auto-collected "Other contacts"
```

Every subcommand takes `--json` for machine-readable output.

## Scopes

| Scope | Why |
|---|---|
| `contacts.readonly` | the contact list and its label memberships |
| `contacts.other.readonly` | the "Other contacts" bucket, which the web UI will not export |

Both are read-only. The tool never requests write access, so it cannot modify or delete a
contact even if asked to.

## Why "In production"

`contacts.readonly` is a *sensitive* scope. Google's OAuth documentation ties the 7-day
refresh-token expiry specifically to projects whose publishing status is **Testing** *and*
whose user type is **External** — exactly the combination a personal script falls into if
you accept the defaults. The symptom is an `invalid_grant` error a week after setup, which
reads like a broken tool rather than an expired grant.

Switching the publishing status to **In production** removes that expiry. Verification is a
separate thing and is not required: an unverified production app shows a warning screen on
first consent and is capped at 100 users, neither of which matters for a personal tool.

## Notes

- The refresh token still dies if you revoke access at
  <https://myaccount.google.com/permissions>, or if it goes unused for six months. Re-run
  `contacts authorize` to mint a new one.
- "Other contacts" are read-only at Google's end and expose only names, email addresses and
  phone numbers. That is an API restriction, not a limitation of this tool.
