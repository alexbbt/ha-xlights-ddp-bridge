# xLights DDP Entity Bridge (Home Assistant add-on)

Receive [DDP](https://www.3wayplc.com/ddp-by-3way/) from **xLights** or **Falcon Player**, map each RGB pixel to a Home Assistant `light.*` entity, and push updates at a low, configurable rate.

Designed for smart lights (Govee via govee2mqtt, Hue, etc.) that cannot handle full show frame rates.

## Architecture

```
xLights / FPP  --DDP UDP-->  this add-on  --HA API-->  light entities  -->  govee2mqtt / other integrations
```

## Install (Supervisor)

1. **Settings → Add-ons → Add-on store → ⋮ → Repositories**
2. Add this repository URL (or path if using a local checkout on the HA host)
3. Install **xLights DDP Entity Bridge**
4. Configure `hz`, `ddp_port`, and ordered `lights`
5. Start the add-on
6. In xLights/FPP, point the matching controller at your **Home Assistant host IP**, protocol **DDP**, channel count = `3 × number of lights`

Default UDP port: **4048**. Allow that port from your show VLAN to HA if you use firewalling.

## Configuration

| Option | Default | Meaning |
|--------|---------|---------|
| `hz` | `5` | Max updates per second to Home Assistant |
| `ddp_port` | `4048` | UDP listen port |
| `ddp_bind` | `0.0.0.0` | Bind address |
| `lights` | (4 outdoor spotlight segments) | Ordered list of `entity_id`s; pixel 0 → first entry |

`rgb(0,0,0)` turns the entity **off**; any other color calls `light.turn_on` with `rgb_color` and `brightness`.

## Local development / test (no add-on install)

```bash
cd xlights_ddp_bridge
export HA_URL=http://10.0.0.20:8123
export HA_TOKEN=...          # long-lived access token
export HZ=5
export DDP_PORT=4048
export LIGHTS_JSON='[
  "light.outdoor_spotlights_segment_001",
  "light.outdoor_spotlights_segment_002",
  "light.outdoor_spotlights_segment_003",
  "light.outdoor_spotlights_segment_004"
]'
PYTHONPATH=. python3 -m bridge
```

In another terminal:

```bash
PYTHONPATH=. python3 -m tests.smoke_ddp
```

Unit tests:

```bash
cd xlights_ddp_bridge
python3 -m unittest discover -s tests -v
```

## License

MIT
