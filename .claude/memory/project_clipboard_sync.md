---
name: project-clipboard-sync
description: How clipboard sync between the Windows desktop, the MacBook and the iPhone is set up (ClipCascade + Universal Clipboard), and the fixes it needed
metadata:
  type: project
---

Clipboard sync across the Windows desktop, the MacBook and the iPhone has been working in every direction since 2026-11-13. Nothing for it lives in this repo; this note is the only record.

**Topology.** ClipCascade syncs the desktop and the Mac. Apple's Universal Clipboard syncs the Mac and the iPhone. The Mac relays between the two systems in both directions. ClipCascade has no iOS client, and iOS lets no background app read the clipboard, so a custom tool would have hit the same iPhone limit.

- **Server**: the ClipCascade Docker image, Peer-to-Server mode, run by `compose.yml` in a `ClipCascade-server` folder under the desktop's Programs folder on C:, next to the client. The user database is the `cc_users/` folder beside it. It is published only on the desktop's tailnet address, on port 3910 (the `clipcascade-server` entry in the ports registry). Its P2P mode still needs this server for sign-in and connection setup, which is why the simpler Peer-to-Server mode was chosen. The `admin` password is the `CLIPCASCADE_ADMIN_PASSWORD` key in Doppler (`local` / `dev_toolbox`). Both the server's web login and its `PUT /update-password` take the SHA3-512 hex of the password, never the plaintext, so a script that posts the raw value gets `/login?error`.
- **Clients**: an MSI install in a `ClipCascade` folder under Programs on the desktop, plus a startup shortcut in the all-users Startup folder. On the Mac it is in `/Applications`. The login form's server URL defaults to `localhost:8080` and has to be replaced with the server's tailnet URL.

**Why the Mac can relay.** Universal Clipboard forwards content another program writes to the Mac clipboard. It only stays local if the writer opts out with `.currentHostOnly`. ClipCascade's macOS client checks NSPasteboard's `changeCount` every 0.3 s and does not filter items marked `com.apple.is-remote-clipboard`, so copies made on the iPhone are forwarded to the desktop.

**Fixes it needed:**
- **Universal Clipboard on macOS 27 (iPhone → Mac broken, Mac → iPhone working).** The hidden default `com.apple.coreservices.useractivityd ClipboardSharingEnabled` was missing. The fix was `defaults write … -bool true`, then `killall useractivityd`, then turning Handoff off and on on the iPhone, restarting it, and copying once Mac → iPhone. Undo with `defaults delete`.
- **Parsec's own clipboard sync** was turned off on the desktop so it does not fight ClipCascade. The setting is `app_copy_paste = false`, added to `%APPDATA%\Parsec\config.txt`. Parsec migrates it into `config.json` on its next start. Parsec runs as a service, so killing the user-session `parsecd` is enough to restart it.

**How to apply:** when clipboard sync breaks, test each hop on its own (desktop ↔ Mac through ClipCascade, Mac ↔ iPhone natively with Cmd+V) before blaming the relay.
