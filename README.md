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
4. In the Stellantis Vehicles config flow, at the remote-login step, set
   **Login service URL** to `http://local-stellantis-worker:3000`

No published port is needed: Home Assistant reaches the add-on over the internal
network. The port mapping is left unset deliberately — the endpoint accepts a
password in the request body, so it stays off the LAN unless you decide
otherwise in the add-on's Network settings.

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

## Requirements

Chromium is not small. Budget roughly 1.5–2 GB of disk for the built image, and
expect a few hundred MB of RAM while a login is in flight — the worker keeps one
browser process alive between requests.
