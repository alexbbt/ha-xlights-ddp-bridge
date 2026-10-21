# xLights DDP Entity Bridge

## About

Listens for [DDP](https://www.3wayplc.com/ddp-by-3way/) (Distributed Display Protocol) packets from xLights or Falcon Player and maps consecutive RGB triplets to any Home Assistant `light.*` entity.

Updates are throttled by the **`hz`** option. Use that when a light cannot take a full show frame rate. A cloud light that waits for a reply is one reason — Govee is the device this was measured against — and the same path works for any other light.

```
xLights / FPP  --DDP UDP-->  this app  --HA API-->  light entities
```

## Open Web UI

Use **Open Web UI** on the app to pick lights with an entity selector, reorder pixels, watch DDP/xLights traffic, and run connection tests. The Configuration tab remains available for the same options as plain text—both paths write the same settings.

This is a Home Assistant app (formerly an add-on) for Home Assistant OS or Supervised. Install it from **Settings → Apps → Install app → ⋮ → Repositories**.

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `hz` | `2` | Maximum updates per second to Home Assistant |
| `ddp_port` | `4048` | UDP port for DDP input (must match xLights/FPP) |
| `ddp_bind` | `0.0.0.0` | Address to bind the UDP socket |
| `lights` | example placeholders | Ordered list of light `entity_id`s (one per RGB pixel) |

`1` Hz is a safe rate. `2` Hz is the measured ceiling for a Govee light that waits for a reply. Anything faster depends on the device.

Each update waits for Home Assistant to finish before the next light is touched. Two slow lights in one tick can take longer than `1 / hz`, so that tick misses the rate cap.

Replace the example `entity_id` values with your lights before starting (or use Open Web UI). Pixel 0 is the first entry. Architectures are aarch64 and amd64 only.

```yaml
hz: 2
ddp_port: 4048
ddp_bind: "0.0.0.0"
lights:
  - entity_id: light.example_pixel_1
  - entity_id: light.example_pixel_2
```

- `rgb(0,0,0)` turns the entity **off**
- Any other color calls `light.turn_on` with `rgb_color` and `brightness` set to the max of R, G, and B
- Unchanged colors are not re-sent
- The color Home Assistant shows is that integration's color, not a match to WLED or Twinkly. xLights gamma and `brightness` set to the max of R, G, and B both change the result. This app does not calibrate color.

## Setup with xLights or Falcon Player

1. Add a network controller:
   - Protocol: **DDP**
   - IP: the IP address of the machine running Home Assistant
   - Channels: `3 ×` number of configured lights
2. Create a model (for example a Single Line with N nodes) on that controller
3. Sequence relatively slow color changes on that model—avoid high-speed twinkles on slow integrations
4. Allow UDP from the show network to Home Assistant on port **4048** (or your `ddp_port`)

## Example: one whole light

DDP goes to this app. The integration that owns the light talks to the device. That integration can be Govee, Hue, or any other source of a `light.*` entity.

Map the entity for the whole light. Per-segment entities are the wrong target when the integration has to use the cloud: each segment is another call, and that call waits before the next light is touched.

```yaml
hz: 2
ddp_port: 4048
ddp_bind: "0.0.0.0"
lights:
  - entity_id: light.porch
```

Add more `entity_id` rows, in order, for more pixels. Any light that accepts `rgb_color` can take a color. Other lights still turn on and off.

## Troubleshooting

- **Nothing happens**: Open Web UI → Status should show DDP listening and recent packets when xLights is outputting. Or check app logs for `Listening DDP…`.
- **HA API errors**: Use **Test HA connection** on the Web UI. Confirm the app starts after Core.
- **Works on LAN tools but not from FPP**: Firewall / VLAN—UDP from the player to Home Assistant must be allowed. Status → Last peer shows the source when packets arrive.
- **Lag or dropped updates**: `1` Hz is safe. `2` Hz is the measured ceiling for a Govee light that waits for a reply; anything faster depends on the device. Two slow lights in one tick can miss that cap, because each update waits for Home Assistant before the next light is touched.
- **Wrong mapping**: Reorder lights on the Web UI; pixel 0 is the first entry.

## Support

- Source and issues: [github.com/alexbbt/ha-xlights-ddp-bridge](https://github.com/alexbbt/ha-xlights-ddp-bridge)
- Contributing: see the repository [CONTRIBUTING.md](https://github.com/alexbbt/ha-xlights-ddp-bridge/blob/main/CONTRIBUTING.md)
- License: [MIT](https://github.com/alexbbt/ha-xlights-ddp-bridge/blob/main/LICENSE)
