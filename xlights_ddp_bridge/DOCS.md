# xLights DDP Entity Bridge

## About

Listens for [DDP](https://www.3wayplc.com/ddp-by-3way/) (Distributed Display Protocol) packets—the same protocol xLights uses for WLED—and maps consecutive RGB triplets to Home Assistant `light.*` entities.

Updates are throttled by the **`hz`** option so Wi‑Fi, cloud, or LAN smart lights are not flooded with full show frame rates.

```
xLights / FPP  --DDP UDP-->  this add-on  --HA API-->  light entities
```

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `hz` | `5` | Maximum updates per second to Home Assistant |
| `ddp_port` | `4048` | UDP port for DDP input (must match xLights/FPP) |
| `ddp_bind` | `0.0.0.0` | Address to bind the UDP socket |
| `lights` | example placeholders | Ordered list of light `entity_id`s (one per RGB pixel) |

Replace the example `entity_id` values with your lights before starting.

```yaml
hz: 5
ddp_port: 4048
ddp_bind: "0.0.0.0"
lights:
  - entity_id: light.example_pixel_1
  - entity_id: light.example_pixel_2
```

- `rgb(0,0,0)` turns the entity **off**
- Any other color calls `light.turn_on` with `rgb_color` and `brightness`
- Unchanged colors are not re-sent

## Setup with xLights or Falcon Player

1. Add a network controller:
   - Protocol: **DDP**
   - IP: your Home Assistant host (`HOMEASSISTANT_IP`)
   - Channels: `3 ×` number of configured lights
2. Create a model (for example a Single Line with N nodes) on that controller
3. Sequence relatively slow color changes on that model—avoid high-speed twinkles on slow integrations
4. Allow UDP from the show network to Home Assistant on port **4048** (or your `ddp_port`)

## Example: Govee (or similar) via an integration

Devices themselves are **not** DDP targets. DDP goes to this add-on; your integration (e.g. govee2mqtt) talks to the hardware.

```yaml
hz: 5
ddp_port: 4048
ddp_bind: "0.0.0.0"
lights:
  - entity_id: light.govee_segment_001
  - entity_id: light.govee_segment_002
  - entity_id: light.govee_segment_003
  - entity_id: light.govee_segment_004
```

Add more `entity_id` rows in order for additional pixels. Any light that accepts `rgb_color` works; non-RGB lights may ignore color.

## Troubleshooting

- **Nothing happens**: Check add-on logs for `Listening DDP…`. Test from xLights Output To Lights, or use the repo’s `tests.smoke_ddp` script against `HOMEASSISTANT_IP`.
- **HA API errors**: Confirm the add-on is started after Core and that Supervisor API access is available (`homeassistant_api: true` in the add-on config).
- **Works on LAN tools but not from FPP**: Firewall / VLAN—UDP from the player to Home Assistant must be allowed.
- **Lag or dropped updates**: Lower `hz` (try `2`–`5`) and simplify effects on those pixels.

## Support

- Source and issues: [github.com/alexbbt/ha-xlights-ddp-bridge](https://github.com/alexbbt/ha-xlights-ddp-bridge)
- License: MIT
