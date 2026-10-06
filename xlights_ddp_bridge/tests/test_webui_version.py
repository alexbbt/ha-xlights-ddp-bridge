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

    def test_html_rewrite_does_not_corrupt_injected_globals(self) -> None:
        """Regression: replacing __ASSET_VERSION__ broke window.__ASSET_VERSION__."""
        asset = "0.2.10-068f641a"
        raw = (
            "<!--INGRESS_SCRIPT-->\n"
            '<link href="static/style.@@ASSET_VERSION@@.css" />\n'
            '<script src="static/app.@@ASSET_VERSION@@.js"></script>\n'
        )
        html = raw.replace("@@ASSET_VERSION@@", asset)
        ingress = "/api/hassio_ingress/TOKEN"
        parts = [
            f'<base href="{ingress}/">',
            "<script>"
            f"window.__XL_ADDON_VERSION__={webui.json.dumps('0.2.10')};"
            f"window.__XL_INGRESS_PATH__={webui.json.dumps(ingress)};"
            f"window.__XL_ASSET_VERSION__={webui.json.dumps(asset)};"
            "window.__ADDON_VERSION__=window.__XL_ADDON_VERSION__;"
            "window.__INGRESS_PATH__=window.__XL_INGRESS_PATH__;"
            "window.__ASSET_VERSION__=window.__XL_ASSET_VERSION__;"
            "</script>",
        ]
        html = html.replace("<!--INGRESS_SCRIPT-->", "".join(parts), 1)
        self.assertIn('window.__XL_ASSET_VERSION__="0.2.10-068f641a"', html)
        self.assertIn("window.__ASSET_VERSION__=window.__XL_ASSET_VERSION__", html)
        self.assertNotIn("window.0.2.10", html)
        self.assertIn(f"static/app.{asset}.js", html)
        self.assertTrue(webui._VERSIONED_JS.match(f"app.{asset}.js"))
        self.assertTrue(webui._VERSIONED_CSS.match(f"style.{asset}.css"))


if __name__ == "__main__":
    unittest.main()
