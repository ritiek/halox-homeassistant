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

[![Open your Home Assistant instance and open a repository inside the Marketplace.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ritiek&repository=halox-homeassistant&category=integration)

**One-click path** — the button above opens this repository directly in your
Home Assistant's marketplace page. Just press **Download this repository**, then
restart Home Assistant. The button needs [HACS](https://www.hacs.xyz/docs/use/download/download/)
— the *Home Assistant Community Store*, the standard marketplace for community
integrations — plus My Home Assistant enabled (Settings → My Home Assistant).
If you don't have HACS yet, [the official setup guide](https://www.hacs.xyz/docs/use/download/download/)
takes about ten minutes, or skip it entirely:

1. Download [the integration as a zip](https://github.com/ritiek/halox-homeassistant/archive/refs/heads/main.zip) and unzip it.
2. Copy the `custom_components/halox` folder into the `custom_components`
   folder of your Home Assistant configuration directory (create the folder if
   it doesn't exist).
3. Restart Home Assistant.

## Setup

[![Add Integration to your Home Assistant instance.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=halox)

Or the classic way: **Settings → Devices & Services → Add Integration**, search
for **Halox Smart**, then enter the **email and password** you use in the Halox
Smart app. That's it.

The integration signs in through Firebase (the vendor's auth provider), stores
only the resulting refresh token in your Home Assistant config entry, and
refreshes the short-lived access token automatically.

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

Commands are relayed through the vendor's cloud, so a change needs the vendor
backend (and the device's connection to it) to be healthy — the same
dependency the official app has.

## Disclaimer

Not affiliated with or endorsed by the vendor. Uses an undocumented API that may
change at any time. Use at your own risk.

## License

[MIT](LICENSE)
