# G-MScreen Integration for Home Assistant

Home Assistant integration for set-top boxes that are controlled by the G-MScreen Android/iOS app. It talks to the box directly over your local network, no cloud and no app needed.

Unofficial, and not affiliated with the app's publisher. Only tested on one box (model FUN_60, software 4.01), so other boxes and firmware versions may behave differently. Test the integration and report your findings.

> This integration is experimental. It's basically my excuse to jump on the AI-powered reverse engineering / clean room reimplementation bandwagon.

## Install

With HACS, add this repository as a custom repository, install it and restart Home Assistant.

Or copy `custom_components/gmscreen` into your Home Assistant `config/custom_components` folder and restart.

## Setup

Go to Settings > Devices & services > Add integration > and pick G-MScreen Set-top Box. The box is found by its UDP beacon, or you can type its IP address. Make sure the box is on and on the same network as Home Assistant.

The box only accepts a limited number of paired clients. If setup says the box is full, make sure your phone app is disconnected (or just reconnect later, it sometimes frees up on its own).

## Entities

- **Remote**: on means running, off means standby.
- **Mute** switch: reflects the real mute state.
- **Diagnostic sensors** (disabled by default): signal strength, signal quality, channel count and the satellite selected in the box's channels menu. Enabling one makes the integration poll the extra data it needs.

The box is polled every 15 seconds.

## Actions

Send key names like `menu`, `ok`, `up`, `volume_up`, `mute`, `5`, or `code:NN` for a raw key code.

```yaml
action: remote.send_command
target:
  entity_id: remote.fun_60
data:
  command: [menu, down, down, ok]
  delay_secs: 0.5
```

## Notes

- Power and mute are toggle keys on the box, so the integration only presses them when the reported state differs from what you asked for.
- I couldn't pull the channels list on my box. The original app also fails, so I assume something's wrong with my box or its firmware.
- The protocol is written up in [docs/protocol.md](docs/protocol.md), and the scripts used to work it out are in [tools](tools/README.md).
