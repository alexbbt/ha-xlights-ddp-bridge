"""Tests for add-on version / asset cache-bust helpers."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from bridge import webui


class TestWebuiVersion(unittest.TestCase):
    def test_parse_version_line(self) -> None:
        text = 'name: x\nversion: "1.2.3"\nslug: x\n'
        self.assertEqual(webui._parse_version_line(text), "1.2.3")

    def test_addon_version_from_env(self) -> None:
        with patch.dict("os.environ", {"ADDON_VERSION": "9.9.9"}, clear=False):
            self.assertEqual(webui._addon_version(), "9.9.9")

    def test_asset_version_includes_digest(self) -> None:
        ver = webui._asset_version("1.0.0")
        self.assertTrue(ver.startswith("1.0.0-"))
        self.assertEqual(len(ver.split("-", 1)[1]), 8)


if __name__ == "__main__":
    unittest.main()
