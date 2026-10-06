"""Ingress web UI: entity picker, status, and test tools."""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from .stats import RuntimeStats

STATIC_DIR = Path(__file__).resolve().parent / "static"
OPTIONS_PATH = Path("/data/options.json")


def _ha_request(
    api_base: str,
    token: str,
    path: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    timeout: float = 8.0,
) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        f"{api_base.rstrip('/')}{path}",
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if not raw:
                return resp.status, None
            return resp.status, json.loads(raw.decode())
    except urllib.error.HTTPError as e:
        raw = e.read()[:500]
        try:
            parsed = json.loads(raw.decode()) if raw else {"message": str(e)}
        except json.JSONDecodeError:
            parsed = {"message": raw.decode(errors="replace")}
        return e.code, parsed


def _supervisor_request(
    token: str,
    path: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    timeout: float = 8.0,
) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        f"http://supervisor{path}",
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if not raw:
                return resp.status, None
            return resp.status, json.loads(raw.decode())
    except urllib.error.HTTPError as e:
        raw = e.read()[:500]
        try:
            parsed = json.loads(raw.decode()) if raw else {"message": str(e)}
        except json.JSONDecodeError:
            parsed = {"message": raw.decode(errors="replace")}
        return e.code, parsed


def load_options() -> dict[str, Any]:
    if OPTIONS_PATH.is_file():
        return json.loads(OPTIONS_PATH.read_text(encoding="utf-8"))
    return {
        "hz": float(os.environ.get("HZ", "5")),
        "ddp_port": int(os.environ.get("DDP_PORT", "4048")),
        "ddp_bind": os.environ.get("DDP_BIND", "0.0.0.0"),
        "lights": [
            {"entity_id": e}
            for e in json.loads(os.environ.get("LIGHTS_JSON", "[]"))
        ],
    }


def save_options_via_supervisor(
    token: str, options: dict[str, Any]
) -> tuple[bool, str]:
    """Persist options through Supervisor so the Configuration tab stays in sync."""
    code, resp = _supervisor_request(
        token,
        "/addons/self/options",
        method="POST",
        body={"options": options},
    )
    if code >= 400:
        return False, f"Supervisor options HTTP {code}: {resp}"
    # Also write locally so resolve stays consistent if Supervisor is slow
    try:
        OPTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
        OPTIONS_PATH.write_text(json.dumps(options, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass
    return True, "ok"


def make_handler(
    stats: RuntimeStats,
    *,
    ha_api: str,
    ha_token: str,
    pulse_fn: Callable[[list[tuple[int, int, int]]], None] | None = None,
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            return  # quiet; use stats.event for important things

        def _normalize_path(self) -> str:
            """Strip query + optional Ingress prefix; Ingress usually already strips it."""
            path = urlparse(self.path).path
            for header in ("X-Ingress-Path", "X-Forwarded-Prefix"):
                prefix = (self.headers.get(header) or "").rstrip("/")
                if prefix and path.startswith(prefix):
                    path = path[len(prefix) :] or "/"
                    break
            return path

        def _json(self, code: int, payload: Any) -> None:
            raw = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length <= 0:
                return {}
            return json.loads(self.rfile.read(length).decode())

        def _serve_static(self, rel: str) -> None:
            rel = rel.split("?", 1)[0].lstrip("/") or "index.html"
            path = (STATIC_DIR / rel).resolve()
            if not str(path).startswith(str(STATIC_DIR.resolve())) or not path.is_file():
                self.send_error(404)
                return
            data = path.read_bytes()
            ctype = "text/html; charset=utf-8"
            if path.suffix == ".js":
                ctype = "application/javascript; charset=utf-8"
            elif path.suffix == ".css":
                ctype = "text/css; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            if path.suffix in {".js", ".css"}:
                self.send_header("Cache-Control", "no-cache")
            else:
                self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _config_payload(self) -> dict[str, Any]:
            opts = load_options()
            return {
                "hz": opts.get("hz", stats.hz),
                "ddp_port": opts.get("ddp_port", stats.ddp_port),
                "ddp_bind": opts.get("ddp_bind", stats.ddp_bind),
                "lights": [
                    item["entity_id"] if isinstance(item, dict) else str(item)
                    for item in opts.get("lights", [])
                ],
            }

        def _available_lights(self) -> tuple[int, Any]:
            code, data = _ha_request(ha_api, ha_token, "/states")
            if code >= 400 or not isinstance(data, list):
                return (code if code >= 400 else 502), {"error": data}
            lights = []
            for ent in data:
                eid = ent.get("entity_id", "")
                if not eid.startswith("light."):
                    continue
                lights.append(
                    {
                        "entity_id": eid,
                        "name": ent.get("attributes", {}).get("friendly_name") or eid,
                        "state": ent.get("state"),
                    }
                )
            lights.sort(key=lambda x: x["name"].lower())
            return 200, {"lights": lights}

        def do_GET(self) -> None:  # noqa: N802
            path = self._normalize_path()

            if path in ("/", "/index.html"):
                self._serve_static("index.html")
                return
            if path.startswith("/static/"):
                self._serve_static(path[len("/static/") :])
                return
            # Prefer /bridge/* (does not collide with HA Core /api/* if mis-routed)
            if path in ("/bridge/status", "/api/status"):
                self._json(200, stats.snapshot())
                return
            if path in ("/bridge/config", "/api/config"):
                self._json(200, self._config_payload())
                return
            if path in ("/bridge/lights/available", "/api/lights/available"):
                code, payload = self._available_lights()
                self._json(code, payload)
                return

            self.send_error(404)

        def do_POST(self) -> None:  # noqa: N802
            path = self._normalize_path()
            body = self._read_json()

            if path in ("/bridge/config", "/api/config"):
                lights = [str(x) for x in body.get("lights", []) if str(x).strip()]
                hz = float(body.get("hz", stats.hz))
                if hz < 0.1 or hz > 60:
                    self._json(400, {"error": "hz must be between 0.1 and 60"})
                    return
                if not lights:
                    self._json(400, {"error": "Configure at least one light"})
                    return
                opts = load_options()
                opts["hz"] = hz
                opts["lights"] = [{"entity_id": e} for e in lights]
                token = os.environ.get("SUPERVISOR_TOKEN", ha_token)
                if os.environ.get("SUPERVISOR_TOKEN"):
                    ok, msg = save_options_via_supervisor(token, opts)
                    if not ok:
                        self._json(502, {"error": msg})
                        return
                else:
                    try:
                        OPTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
                        OPTIONS_PATH.write_text(
                            json.dumps(opts, indent=2) + "\n", encoding="utf-8"
                        )
                    except OSError as e:
                        self._json(500, {"error": str(e)})
                        return
                stats.set_lights(lights, hz=hz)
                self._json(200, {"ok": True, "lights": lights, "hz": hz})
                return

            if path in ("/bridge/test/ha", "/api/test/ha"):
                code, data = _ha_request(ha_api, ha_token, "/")
                if code >= 400:
                    stats.note_ha_check(False)
                    stats.event("error", f"HA API check failed HTTP {code}")
                    self._json(502, {"ok": False, "error": data})
                    return
                missing: list[str] = []
                for eid in stats.snapshot()["lights"]:
                    sc, _ = _ha_request(ha_api, ha_token, f"/states/{eid}")
                    if sc == 404:
                        missing.append(eid)
                ok = not missing
                stats.note_ha_check(ok, missing)
                stats.event(
                    "info",
                    "HA OK" if ok else f"Missing entities: {', '.join(missing)}",
                )
                self._json(
                    200,
                    {
                        "ok": ok,
                        "ha": data,
                        "missing": missing,
                        "configured": stats.snapshot()["lights"],
                    },
                )
                return

            if path in ("/bridge/test/pulse", "/api/test/pulse"):
                colors = body.get("rgb", [255, 255, 255])
                if (
                    not isinstance(colors, list)
                    or len(colors) != 3
                    or not all(isinstance(c, int) and 0 <= c <= 255 for c in colors)
                ):
                    self._json(400, {"error": "rgb must be [r,g,b] 0-255"})
                    return
                r, g, b = colors
                snap = stats.snapshot()
                lights = snap["lights"]
                if not lights:
                    self._json(400, {"error": "No lights configured"})
                    return
                for eid in lights:
                    if r == 0 and g == 0 and b == 0:
                        _ha_request(
                            ha_api,
                            ha_token,
                            "/services/light/turn_off",
                            method="POST",
                            body={"entity_id": eid},
                        )
                    else:
                        _ha_request(
                            ha_api,
                            ha_token,
                            "/services/light/turn_on",
                            method="POST",
                            body={
                                "entity_id": eid,
                                "rgb_color": [r, g, b],
                                "brightness": max(r, g, b),
                            },
                        )
                stats.note_colors([(r, g, b)] * len(lights))
                stats.event("test", f"Pulse RGB({r},{g},{b}) → {len(lights)} lights")
                if pulse_fn is not None:
                    pulse_fn([(r, g, b)] * len(lights))
                self._json(200, {"ok": True})
                return

            self.send_error(404)

    return Handler


def start_webui(
    stats: RuntimeStats,
    *,
    host: str = "0.0.0.0",
    port: int = 8099,
    ha_api: str,
    ha_token: str,
) -> ThreadingHTTPServer:
    handler = make_handler(stats, ha_api=ha_api, ha_token=ha_token)
    server = ThreadingHTTPServer((host, port), handler)
    thread = threading.Thread(target=server.serve_forever, name="ingress-webui", daemon=True)
    thread.start()
    stats.event("info", f"Ingress UI listening on {host}:{port}")
    print(f"Ingress UI on http://{host}:{port}", flush=True)
    return server
