# xLights DDP Entity Bridge

## What it does

Listens for DDP (Distributed Display Protocol) packets—the same protocol xLights uses for WLED—and maps consecutive RGB triplets to Home Assistant light entities.

Updates are throttled by the **`hz`** option so slow Wi‑Fi / cloud / LAN smart lights (Govee, Hue, etc.) are not flooded.

## Setup with xLights

1. Add an Ethernet controller:
   - Protocol: **DDP**
   - IP: your Home Assistant host IP
   - Channels: `3 ×` number of configured lights
2. Create a model (e.g. Single Line with N nodes) on that controller
3. Sequence slow color changes—not twinkles or chases—on that model
4. Ensure the show network can reach HA UDP port **4048** (or your configured `ddp_port`)

## Configuration notes

Shipped defaults use placeholder entities (`light.example_pixel_1`, …). Replace them with your real lights before starting.

### Example: Govee (or similar) segments

```yaml
hz: 5
ddp_port: 4048
ddp_bind: "0.0.0.0"
lights:
  - entity_id: light.my_device_segment_001
  - entity_id: light.my_device_segment_002
  - entity_id: light.my_device_segment_003
  - entity_id: light.my_device_segment_004
```

The physical Wi‑Fi device is **not** a DDP target. DDP goes to this add-on; your existing integration (e.g. govee2mqtt) talks to the device.

## Expanding to other lights

Add more `entity_id` rows in order. Each row is one RGB pixel / one light. Any HA light that accepts `rgb_color` works; non-RGB lights may ignore color.

## Troubleshooting

- **Nothing happens**: Check add-on logs for “Listening DDP…”. Send a test from xLights Output, or use the repo smoke script.
- **HA API errors**: Confirm the add-on has Home Assistant API access and is started after Core.
- **Works locally but not from FPP**: Firewall / VLAN—UDP 4048 from the player to HA must be allowed.
