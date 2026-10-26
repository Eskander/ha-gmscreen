# Protocol notes

These notes describe how set-top boxes controlled by the **G-MScreen** Android
app (package `mktvsmart.screen`) talk over the local network. Everything here
was reverse engineered from the app (version 1.0.22176) and checked against one
box: model `FUN_60`, platform id 96, software 3.87. Other boxes and firmware
versions may differ. This is unofficial and not endorsed by the app's publisher.

## Overview

1. The box broadcasts a 108 byte **beacon** on UDP port 25860.
2. A client opens a TCP connection to port **20000** and sends a **handshake**.
   The box answers with the same 108 byte beacon, which tells the client how
   to talk to it (JSON or XML, which key table, whether the box is full).
3. The client sends **key presses** and **queries** as framed messages. Queries
   are answered with zlib compressed JSON.

There is no PIN or encryption. "Pairing" is just the box seeing a client UUID.

## Beacon (UDP 25860, also the handshake reply)

108 bytes. On the wire the bytes are **reversed and XORed with 0x5B**, which is
its own inverse, so the same function decodes and encodes. After decoding:

| Offset | Size | Meaning |
|---|---|---|
| 0 | 12 | magic `39WwijOog54a` |
| 12 | 6 | serial number: two 3 byte big-endian numbers, printed as 6 digits each |
| 20 | 32 | model name, NUL terminated (may end in whitespace) |
| 68 | 4 | IPv4 address in reverse byte order |
| 72 | 1 | platform id, selects the key table (30 is special) |
| 73 | 2 | software version, big-endian (387 means 3.87) |
| 75 | 1 | customer id |
| 76 | 1 | model id |
| 80 | 4 | software sub-version, little-endian |
| 84 | 1 | flags, see below |
| 85 | 1 | more flags, see below |
| 88 | 1 | "like platform" id |

Byte 84: bit 0 box is full (refuses more clients), bit 1 client type, bit 2
satellite capable, bits 3-4 Sat>IP mode, bit 6 data type (0 XML, 1 JSON),
bit 7 spectrum. Byte 85: bit 0 satellite finder, bit 1 DLNA, bit 2 OTT.
The flag meanings come from the app's code; only "full" and the data type have
been confirmed on a real box.

## TCP messages (client to box)

Every message is `Start` + 7 digit zero padded payload length + `End` + payload:

```
Start0000016Endabcdefghijklmnop
```

### Handshake

XML, regardless of the box's data type:

```xml
<?xml version='1.0' encoding='UTF-8' standalone='yes' ?><Command request="998"><data>DEVICE NAME</data><uuid>CLIENT UUID</uuid></Command>
```

The reply is the raw 108 byte beacon, **not framed**. If its "full" flag is set
the box ignores commands from this client.

### Requests

In JSON mode a bare query is `{"request":"15"}`. In XML mode it is
`<Command request="15"/>`. Key presses use request 1040:

```json
{"request":"1040","array":[{"KeyValue":"5"}]}
```

```xml
<Command request="1040"><KeyValue>5</KeyValue></Command>
```

Key presses get no reply.

## Replies (box to client)

```
"GCDH" | u32le body length | u32le request id | u32 0 | zlib(JSON)
```

* The body is a JSON array, usually with a single object.
* The request id in the header identifies what the reply answers. Replies can
  arrive late and a client must not match them by arrival order.
* Some requests are answered with a **zero length** frame first (a bare
  acknowledgement) and the real reply afterwards.
* Requests the firmware does not implement get `[{"Command": ""}]`.

## Queries that this firmware answers

Found by sending every request id the app uses (and their neighbours) to a
`FUN_60`. All other ids returned the empty reply.

| Request | Reply |
|---|---|
| 15 | `StbStatus` (1 running, 0 standby), `ProductName`, `SoftwareVersion`, `SerialNumber`, `ChannelNum`, `MaxNumOfPrograms` |
| 19 | `{"Data": "0"}` sound on, `{"Data": "1"}` muted |
| 22 | satellite list: `SatName`, `SatIndex`, `SatAngle`, `SatDir` |
| 23 | `{"Data": "84"}`: `SatIndex` selected in the box's channels menu, 120 means all satellites |
| 24 | transponder list (about 200 KB, slow): `TPIndex`, `SatIndex`, `SR`, `POL`, `FEC`, `Freq` |
| 403 | `{"strength": 96, "quality": 90}` in percent |

The app's channel list and streaming requests are not answered by this
firmware, and the box does not listen on the RTSP port 554. The app also
greys out playback for boxes that advertise Sat>IP mode 2, which includes this
one.

## Key codes

The app uses the default table unless the platform id is 30.

| Key | Default | Platform 30 |
|---|---|---|
| `power` | 42 | 44 |
| `exit` | 7 | 21 |
| `menu` | 6 | 20 |
| `home` | 82 |  |
| `red` | 8 | 16 |
| `green` | 9 | 17 |
| `yellow` | 10 | 18 |
| `blue` | 11 | 19 |
| `up` | 1 | 24 |
| `down` | 2 | 25 |
| `left` | 3 | 22 |
| `right` | 4 | 23 |
| `ok` | 5 | 27 |
| `0` | 12 | 10 |
| `1` | 13 | 1 |
| `2` | 14 | 2 |
| `3` | 15 | 3 |
| `4` | 16 | 4 |
| `5` | 17 | 5 |
| `6` | 18 | 6 |
| `7` | 19 | 7 |
| `8` | 20 | 8 |
| `9` | 21 | 9 |
| `recall` | 29 | 58 |
| `tv_radio` | 22 | 11 |
| `page_up` | 37 | 34 |
| `page_down` | 38 | 35 |
| `volume_up` | 35 | 56 |
| `volume_down` | 36 | 57 |
| `mute` | 23 | 12 |
| `epg` | 32 | 29 |
| `txt` | 34 | 30 |
| `sub` | 31 | 28 |
| `usb` | 43 | 46 |
| `record` | 58 | 43 |
| `play` | 61 | 38 |
| `stop` | 62 | 39 |
| `pause` | 63 | 42 |
| `previous` | 64 | 40 |
| `next` | 65 | 41 |
| `rewind` | 59 | 36 |
| `fast_forward` | 60 | 37 |

## Quirks seen on real hardware

* The box closes a session after roughly 25 seconds without traffic.
* The box seems to keep one client slot per UUID. The stock app generates a
  new UUID on every launch (it never saves it), so after a few launches the box
  reports "full" and ignores key presses until it is power cycled. Reuse one
  UUID.
* After many connections with different UUIDs the box stopped answering both
  beacons and handshakes for a while, then recovered after power cycles and
  waiting. A later firmware update made the LAN service much more stable.
* Right after boot the service can take a while to start answering.
