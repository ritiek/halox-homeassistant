# Halox Smart for Home Assistant

An unofficial [Home Assistant](https://www.home-assistant.io/) integration for
**Halox Smart** Wi-Fi switches and plugs (the devices controlled by the
*Halox Smart* Android/iOS app, vendor package `com.livsmartautomation.livsmart`,
also sold under the LivSmart name).

It talks to the same cloud backend the official app uses, so there is **nothing
to flash and no hardware to open** — you just sign in with your Halox account.

> Status: **work in progress.** Device discovery and on/off **state reporting**
> work today. **Power control (turning devices on/off)** is not wired up yet —
> see [Control status](#control-status).

## Features

- Automatic discovery of every switch/plug across all your homes and rooms.
- Live on/off state, device online status, and firmware version.
- Simple email + password setup — no tokens, developer accounts or cloud keys.

## Installation

### HACS (recommended)

1. In HACS, add this repository as a *custom repository* (type: *Integration*).
2. Install **Halox Smart**, then restart Home Assistant.

### Manual

Copy `custom_components/halox` into your Home Assistant `config/custom_components/`
directory and restart.

## Setup

Settings → Devices & Services → **Add Integration** → **Halox Smart**, then enter
the **email and password** you use in the Halox Smart app. That's it.

The integration signs in through Firebase (the vendor's auth provider), stores
only the resulting refresh token in your Home Assistant config entry, and
refreshes the short-lived access token automatically.

## How it works

The Halox app is a thin client over a public cloud API:

- Auth: Firebase email/password sign-in → `Bearer` ID token.
- REST backend (AWS API Gateway) for discovery and state
  (`/home/all`, `/board/all`, …).
- A Socket.IO channel for realtime updates and power control.

This integration polls the REST backend for state (reflected within a couple of
seconds of any change) and will use the Socket.IO channel for control.

## Control status

The official app does **not** change device power via a REST call — the REST
`/device/update_state` endpoint returns `201` but is a no-op. Power changes are
sent over the **Socket.IO** channel (observed events `updateDeviceState` /
`toggleDeviceState`). That channel requires an authentication handshake whose
exact shape is still being finalised, so `switch.turn_on` / `turn_off` currently
raise a clear "not implemented" error. State reading is unaffected.

Contributions welcome — if you can capture the app's Socket.IO handshake, open an
issue.

## Disclaimer

Not affiliated with or endorsed by the vendor. Uses an undocumented API that may
change at any time. Use at your own risk.

## License

[MIT](LICENSE)
