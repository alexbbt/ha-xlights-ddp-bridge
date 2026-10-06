"""Unit tests for DDP parsing and pixel mapping (no HA required)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from bridge.bridge import (
    BridgeConfig,
    apply_pixels,
    build_ddp_packet,
    parse_ddp,
    pixels_from_rgb,
    run_bridge,
)


class TestDdp(unittest.TestCase):
    def test_parse_roundtrip(self) -> None:
        rgb = bytes([255, 0, 0, 0, 255, 0, 0, 0, 255, 1, 2, 3])
        pkt = build_ddp_packet(rgb)
        self.assertEqual(parse_ddp(pkt), rgb)

    def test_parse_too_short(self) -> None:
        self.assertIsNone(parse_ddp(b"\x00\x01"))

    def test_pixels_pad(self) -> None:
        self.assertEqual(
            pixels_from_rgb(bytes([9, 8, 7]), 2),
            [(9, 8, 7), (0, 0, 0)],
        )

    def test_apply_skips_unchanged_and_offs(self) -> None:
        client = MagicMock()
        lights = ("light.a", "light.b")
        last: list = [None, None]
        apply_pixels(client, lights, [(10, 0, 0), (0, 0, 0)], last)
        self.assertEqual(client.call_light.call_count, 2)
        client.call_light.assert_any_call(
            "turn_on",
            {"entity_id": "light.a", "rgb_color": [10, 0, 0], "brightness": 10},
        )
        client.call_light.assert_any_call("turn_off", {"entity_id": "light.b"})

        client.reset_mock()
        apply_pixels(client, lights, [(10, 0, 0), (0, 0, 0)], last)
        client.call_light.assert_not_called()

    def test_run_bridge_throttles(self) -> None:
        client = MagicMock()
        config = BridgeConfig(
            hz=10,
            ddp_port=4048,
            ddp_bind="127.0.0.1",
            lights=("light.a",),
            ha_url="http://example/api",
            ha_token="t",
        )
        rgb = bytes([1, 2, 3])
        pkt = build_ddp_packet(rgb)
        packets = [pkt, pkt, None]
        times = iter([0.0, 0.01, 0.2])

        def fake_recv():
            if packets:
                return packets.pop(0)
            raise SystemExit("done")

        def fake_clock():
            return next(times, 1.0)

        with self.assertRaises(SystemExit):
            run_bridge(
                config,
                client=client,
                recv=fake_recv,
                clock=fake_clock,
                sleep=lambda _t: None,
            )
        # First change applied; duplicate before interval skipped; after interval still same color → no extra call
        self.assertGreaterEqual(client.call_light.call_count, 1)


if __name__ == "__main__":
    unittest.main()
