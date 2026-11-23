# Halox Smart for Home Assistant

An unofficial [Home Assistant](https://www.home-assistant.io/) integration for
**Halox Smart** Wi-Fi switches and plugs (the devices controlled by the
*Halox Smart* Android/iOS app, vendor package `com.livsmartautomation.livsmart`,
also sold under the LivSmart name).

It talks to the same cloud backend the official app uses, so there is **nothing
to flash and no hardware to open** — you just sign in with your Halox account.

## Features

- Automatic discovery of every switch/plug across all your homes and rooms.
- On/off control and live state, device online status, and firmware version.
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
- REST backend (AWS) for discovery, state and control
  (`/home/all`, `/board/all`, `POST /device/update_state`).
- A Socket.IO channel pushes realtime state changes (this integration polls
  instead — simpler, and just as fresh).

One vendor quirk worth knowing: the control payload must be **flat** —
`{"device_id": ..., "on": true}`. The backend also accepts a nested
`{"device_id": ..., "state": {"on": ...}}` form with HTTP 201 but silently
ignores it, which is easy to trip over when reverse-engineering the API.

Commands are relayed through the vendor's cloud, so a change needs the vendor
backend (and the device's connection to it) to be healthy — the same
dependency the official app has.

## Disclaimer

Not affiliated with or endorsed by the vendor. Uses an undocumented API that may
change at any time. Use at your own risk.

## License

[MIT](LICENSE)
