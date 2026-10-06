"""Tests for Ingress-safe POST body reading."""

from __future__ import annotations

import base64
import json
import unittest
from io import BytesIO
from bridge.stats import RuntimeStats
from bridge.webui import make_handler


def _handler_cls():
    return make_handler(
        RuntimeStats(),
        ha_api="http://example/api",
        ha_token="token",
    )


def _bare_handler():
    Handler = _handler_cls()
    return Handler.__new__(Handler)


class TestWebuiBody(unittest.TestCase):
    def test_read_json_from_content_length(self) -> None:
        h = _bare_handler()
        payload = {"lights": ["light.a"], "hz": 5}
        raw = json.dumps(payload).encode()
        h.headers = {"Content-Length": str(len(raw))}  # type: ignore[assignment]
        h.rfile = BytesIO(raw)  # type: ignore[assignment]
        self.assertEqual(h._read_json(), payload)

    def test_read_json_from_bridge_body_header(self) -> None:
        h = _bare_handler()
        payload = {"lights": ["light.a", "light.b"], "hz": 5}
        b64 = base64.b64encode(json.dumps(payload).encode()).decode()
        h.headers = {"Content-Length": "0", "X-Bridge-Body": b64}  # type: ignore[assignment]
        h.rfile = BytesIO(b"")  # type: ignore[assignment]
        self.assertEqual(h._read_json(), payload)

    def test_read_chunked_body(self) -> None:
        h = _bare_handler()
        payload = {"lights": ["light.a"], "hz": 3}
        data = json.dumps(payload).encode()
        chunked = f"{len(data):X}\r\n".encode() + data + b"\r\n" + b"0\r\n\r\n"
        h.headers = {"Transfer-Encoding": "chunked"}  # type: ignore[assignment]
        h.rfile = BytesIO(chunked)  # type: ignore[assignment]
        self.assertEqual(h._read_json(), payload)


if __name__ == "__main__":
    unittest.main()
