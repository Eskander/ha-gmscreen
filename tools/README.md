# Exploration tools

Small scripts used to work out the protocol (see `docs/protocol.md`). They are
handy when a box behaves differently from the one the integration was built
against. They need only Python 3.12+; Home Assistant is not required.

| Script | What it does |
|---|---|
| `diag.py` | Listens for beacons, then does one handshake and reports timing and the "full" flag. Add `press` to send MENU and EXIT. |
| `request.py` | Sends request numbers or JSON bodies and decodes the replies. |
| `watch.py` | Polls power, mute and the selected satellite and prints changes while you use the physical remote. |
| `sweep_all.py` | Tries every request id the app knows. Read its warning first. |

Every script takes `HOST` or `HOST:PORT`. Run them from the repository root,
for example `python tools/diag.py 192.168.1.187`.
