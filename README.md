# xLights DDP Entity Bridge (Home Assistant add-on)

Receive [DDP](https://www.3wayplc.com/ddp-by-3way/) from **xLights** or **Falcon Player**, map each RGB pixel to a Home Assistant `light.*` entity, and push updates at a low, configurable rate.

Designed for smart lights (Govee via govee2mqtt, Hue, etc.) that cannot handle full show frame rates.

## Architecture

```
xLights / FPP  --DDP UDP-->  this add-on  --HA API-->  light entities  -->  govee2mqtt / other integrations
```

## Install (Supervisor)

1. **Settings → Add-ons → Add-on store → ⋮ → Repositories**
2. Add: `https://github.com/alexbbt/ha-xlights-ddp-bridge`
3. Install **xLights DDP Entity Bridge**
4. Replace the placeholder `lights` with your real `entity_id`s (in pixel order)
5. Start the add-on
6. In xLights/FPP, point the matching controller at your **Home Assistant host IP**, protocol **DDP**, channel count = `3 × number of lights`

Default UDP port: **4048**. Allow that port from your show network to HA if you use firewalling.

## Configuration

| Option | Default | Meaning |
|--------|---------|---------|
| `hz` | `5` | Max updates per second to Home Assistant |
| `ddp_port` | `4048` | UDP listen port |
| `ddp_bind` | `0.0.0.0` | Bind address |
| `lights` | `light.example_pixel_1`, `light.example_pixel_2` | Ordered `entity_id`s; pixel 0 → first entry — **replace these** |

`rgb(0,0,0)` turns the entity **off**; any other color calls `light.turn_on` with `rgb_color` and `brightness`.

### Example (Govee segments via govee2mqtt)

```yaml
hz: 5
ddp_port: 4048
ddp_bind: "0.0.0.0"
lights:
  - entity_id: light.my_govee_segment_001
  - entity_id: light.my_govee_segment_002
  - entity_id: light.my_govee_segment_003
  - entity_id: light.my_govee_segment_004
```

## Local development / test (no add-on install)

```bash
cd xlights_ddp_bridge
export HA_URL=http://HOMEASSISTANT_IP:8123
export HA_TOKEN=...          # long-lived access token
export HZ=5
export DDP_PORT=4048
export LIGHTS_JSON='[
  "light.example_pixel_1",
  "light.example_pixel_2"
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

MIT — see [LICENSE](LICENSE).
