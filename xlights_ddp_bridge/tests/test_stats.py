"""Unit tests for runtime stats."""

from __future__ import annotations

import unittest

from bridge.stats import RuntimeStats


class TestRuntimeStats(unittest.TestCase):
    def test_configure_and_snapshot(self) -> None:
        s = RuntimeStats()
        s.configure(hz=5, ddp_port=4048, ddp_bind="0.0.0.0", lights=["light.a", "light.b"])
        snap = s.snapshot()
        self.assertEqual(snap["lights"], ["light.a", "light.b"])
        self.assertEqual(snap["expected_payload_len"], 6)
        self.assertFalse(snap["listening"])

    def test_note_packet_and_pps(self) -> None:
        s = RuntimeStats()
        s.configure(hz=5, ddp_port=4048, ddp_bind="0.0.0.0", lights=["light.a"])
        s.note_packet("10.0.0.5:1234", 3)
        snap = s.snapshot()
        self.assertEqual(snap["last_peer"], "10.0.0.5:1234")
        self.assertEqual(snap["last_payload_len"], 3)
        self.assertIsNotNone(snap["last_packet_age_s"])
        self.assertGreaterEqual(s.packets_per_second(), 0.0)

    def test_set_lights_preserves_overlap(self) -> None:
        s = RuntimeStats()
        s.configure(hz=5, ddp_port=4048, ddp_bind="0.0.0.0", lights=["light.a"])
        s.note_colors([(1, 2, 3)])
        s.set_lights(["light.a", "light.b"], hz=4)
        self.assertEqual(s.last_colors[0], (1, 2, 3))
        self.assertIsNone(s.last_colors[1])
        self.assertEqual(s.hz, 4.0)


if __name__ == "__main__":
    unittest.main()
