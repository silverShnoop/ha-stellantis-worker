# Stellantis Login Worker — Home Assistant add-on repository

A Home Assistant add-on that runs the login worker for the
[Stellantis Vehicles](https://github.com/andreadegiovine/homeassistant-stellantis-vehicles)
integration on your own hardware.

## Why

The integration cannot ask Stellantis for a token directly — Stellantis
publishes no OAuth client for third parties. Instead a worker drives a headless
browser against the real sign-in page, submits your credentials, and reads the
OAuth `code` out of the redirect.

By default that worker is a shared instance on Render's free tier, which means
**your Stellantis email and password are posted, in plain text, to a third
party** on every login. Running the same worker here keeps them on your network.
The free tier also cold-starts, which is a common cause of the login timing out.

## Install

1. Settings → Add-ons → Add-on Store → ⋮ → **Repositories**
2. Add this repository's URL
3. Install **Stellantis Login Worker** and start it
4. Open the add-on's page and note its **hostname** (shown under the add-on
   name, and in the page URL). It is this repository's hash, then
   `-stellantis-worker`.
5. In the Stellantis Vehicles config flow, at the remote-login step, set
   **Login service URL** to `http://<that-hostname>:3000`

The hostname cannot be written down in advance: Supervisor prefixes add-on
slugs with a hash of the repository they came from, so it differs per install.
(`local-…` names belong only to add-ons dropped in `/addons` by hand.)

## Reachability

The add-on publishes **no port to the host**. `config.yaml` carries no `ports`
key at all, so Supervisor maps nothing and the add-on's Network tab offers no
way to change that; `host_network` is off. Nothing on your LAN can open it.

Home Assistant reaches it over Supervisor's internal Docker network, which is
also how every other add-on talks to Home Assistant. That network is shared
with your other add-ons, so they could reach it too — there is no way to be
narrower than that without a reverse proxy, and it is the same trust boundary
every add-on already sits inside.

This matters because the endpoint takes your Stellantis password in the body of
a plain HTTP request. Keeping it off the LAN is the point of running it here.

## What it exposes

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| `POST` | `/` | `{url, email, password, timeout_page?, timeout_input?, debug?}` | `{code}` |
| `GET` | `/health` | — | `{"status": "ok"}` |

It reads no environment variables and holds no credentials of its own.

## What differs from upstream

`main.py` is vendored unchanged from
[homeassistant-stellantis-vehicles-worker-v2](https://github.com/andreadegiovine/homeassistant-stellantis-vehicles-worker-v2).

Two build changes were needed to run it on ARM, which the upstream image never
had to do because Render is x86:

- **Playwright 1.42.0 → 1.49.0.** 1.42.0 publishes no `chromium-linux-arm64`
  build, so `playwright install chromium` fails outright on aarch64. 1.49.0
  publishes one. Every Playwright call the worker makes is long-stable across
  that range.
- **`playwright install --with-deps`** instead of a hand-listed apt set, so
  Playwright picks the system libraries its own build wants. The upstream list
  names `libasound2`, which Debian renamed to `libasound2t64` in trixie.
- **`--only-shell`**, so the download is `chromium-headless-shell` rather than
  full Chromium, and the system-library set shrinks with it — the shell needs
  no GTK, X11 or audio stack. Measured against Playwright's CDN for the
  revision 1.49.0 pins, arm64: **103 MB compressed against 165 MB**.
- **`uvicorn` rather than `uvicorn[standard]`**, dropping uvloop, httptools,
  watchfiles and websockets. This service answers a few plain HTTP requests and
  never opens a socket.

## Size

| Piece | arm64, compressed |
| --- | --- |
| `python:3.11-slim` base | 47 MB |
| `chromium-headless-shell` | 103 MB |
| Playwright's system libraries | not measured |
| Python packages | small |

Those first two are read from Docker Hub and Playwright's CDN. The apt set is
the remaining unknown, and it is not small — so treat the total as "a few
hundred MB", not a figure anyone has weighed. The honest number comes from
`docker images` after the first build.

The worker keeps one browser process alive between requests, so expect a few
hundred MB of RAM while a login is in flight.

### If the shell turns out not to be enough

`--only-shell` is the one change here that alters behaviour rather than just
size: the headless shell is a different binary from headed Chromium, and a
login page can in principle behave differently under it. If logins fail with
something like `Executable doesn't exist` or a selector that never appears,
drop `--only-shell` from the Dockerfile's `playwright install` line and rebuild.
That restores full Chromium and costs about 60 MB.
