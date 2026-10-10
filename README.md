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

## Options

Both are empty by default, and the defaults are the right setting for a
plain install.

| Option | Default | What it does |
| --- | --- | --- |
| `allowed_hosts` | `[]` | Hostname suffixes the worker may be sent to. A request whose `url` is not `https://` on one of these hosts (or a subdomain of one) is refused with a 400 before the browser is touched. Empty keeps the built-in list: `idpcvs.peugeot.com`, `idpcvs.citroen.com`, `idpcvs.driveds.com`, `idpcvs.opel.com` and `idpcvs.vauxhall.co.uk`, the sign-in hosts of the brand apps the integration knows. Set it only if the integration gains a brand this list is missing. |
| `token` | `""` | Shared secret. When set, every `POST /` must carry it in an `X-Worker-Token` header or it is refused with a 401. **The Stellantis Vehicles integration cannot send a header today**, so leave this empty unless a reverse proxy between the two adds one for it. |

The worker is already unreachable from outside Supervisor's network, so the
allowlist is there to limit what any other add-on could make it do: without
it, anything on that network could point a browser holding your password at
a page of its choosing.

## What it exposes

| Method | Path | Headers | Body | Returns |
| --- | --- | --- | --- | --- |
| `POST` | `/` | `X-Worker-Token` when `token` is set | `{url, email, password, timeout_page?, timeout_input?, debug?}` | `{code}` |
| `GET` | `/health` | — | — | `{"status": "ok"}` |

`url` must pass the allowlist above (400 otherwise); `debug` turns on verbose
logging for that one request. It holds no credentials of its own: the only
thing it reads at startup is its add-on options, which `run.sh` hands it in
the `WORKER_OPTIONS` environment variable.

## What differs from upstream

`main.py` is vendored from
[homeassistant-stellantis-vehicles-worker-v2](https://github.com/andreadegiovine/homeassistant-stellantis-vehicles-worker-v2),
with the structure kept so a diff against upstream still reads. The changes
to it:

- **Certificate errors fail the login.** The browser context was created
  with `ignore_https_errors=True` and `bypass_csp=True` — on the page the
  password is typed into. Now it is `ignore_https_errors=False` and the CSP
  is left alone.
- **The host allowlist and the optional token** described under Options.
- **`debug` is per request.** Upstream kept it in a module global, so one
  request's `debug: true` would have stuck for every request after it.
- **The code wait actually waits.** Upstream's
  `asyncio.wait_for(asyncio.to_thread(lambda: captured_code), …)` returned
  at once rather than waiting for the redirect, so the code had to have
  arrived already by the time the authorize click returned. The handler now
  sets an `asyncio.Event` that the request waits on, up to `timeout_page`.
- **FastAPI's `lifespan`** instead of the deprecated `on_event` hooks.

And to the image:

- **It runs as an unprivileged user** (`worker`, uid 1000), not root.
  Chromium still passes `--no-sandbox`, because its own sandbox wants user
  namespaces the add-on does not get, so the user drop is the mitigation for
  anything that gets out of the renderer. The drop happens in `run.sh` rather
  than a `USER` line, because Supervisor writes `/data/options.json`
  root-only and the options have to be read first.

Build changes that were needed to run it on ARM, which the upstream image never
had to do because Render is x86:

- **Playwright 1.42.0 → 1.63.0.** 1.42.0 publishes no `chromium-linux-arm64`
  build, so `playwright install chromium` fails outright on aarch64. 1.49.0
  was the first version checked to publish one, and 1.63.0 still does. Every
  Playwright call the worker makes is long-stable across that range.
- **`playwright install --with-deps`** instead of a hand-listed apt set, so
  Playwright picks the system libraries its own build wants. The upstream list
  names `libasound2`, which Debian renamed to `libasound2t64` in trixie.
- **`--only-shell`**, so the download is `chromium-headless-shell` rather than
  full Chromium. Measured against Playwright's CDN for the revision 1.63.0
  pins, arm64: **116 MB compressed against 208 MB**. It does not shrink the
  apt set: Playwright keeps one dependency list per browser rather than per
  build, so the shell pulls the same packages Chromium would.
- **The base is pinned to `python:3.11-slim-bookworm`.** The floating
  `-slim` tag has moved on to Debian trixie, which Playwright 1.49 did not
  recognise — it fell back to an Ubuntu 20.04 package list naming
  `ttf-ubuntu-font-family` and `ttf-unifont`, which do not exist on Debian,
  and `playwright install --with-deps` exited 100. Playwright 1.63 does list
  `debian13`, but this image has not been built there, so it stays on the
  base it is known to build on.
- **`uvicorn` rather than `uvicorn[standard]`**, dropping uvloop, httptools,
  watchfiles and websockets. This service answers a few plain HTTP requests and
  never opens a socket.

## Size

| Piece | arm64, compressed |
| --- | --- |
| `python:3.11-slim-bookworm` base | 45 MB |
| `chromium-headless-shell` | 116 MB |
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
That restores full Chromium and costs about 90 MB.

## Tests

There is a small offline suite for the request guards; the browser is never
launched.

```sh
python3 -m venv .venv && .venv/bin/pip install fastapi uvicorn pytest httpx
.venv/bin/python -m pytest tests -q
```
