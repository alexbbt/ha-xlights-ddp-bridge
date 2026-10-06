#!/usr/bin/env python3
"""DDP → Home Assistant light entity bridge.

Runs inside the Supervisor add-on (SUPERVISOR_TOKEN + supervisor API) or
locally for testing (HA_URL + HA_TOKEN / LIGHTS_JSON).
"""
from __future__ import annotations

import json
import os
import socket
import struct
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


def parse_ddp(packet: bytes) -> bytes | None:
    """Return RGB payload bytes from a DDP packet, or None if not usable."""
    if len(packet) < 10:
        return None
    data_len = struct.unpack("!H", packet[8:10])[0]
    if data_len <= 0:
        return None
    data = packet[10 : 10 + data_len]
    return data or None


def build_ddp_packet(rgb: bytes, *, sequence: int = 1, dest_id: int = 1) -> bytes:
    """Build a minimal DDP RGB data packet (for tests / smoke tools)."""
    header = bytes([0x41, sequence & 0xFF, 0x0A, dest_id & 0xFF])
    header += struct.pack("!IH", 0, len(rgb))
    return header + rgb


def pixels_from_rgb(data: bytes, count: int) -> list[tuple[int, int, int]]:
    """Slice RGB bytes into `count` pixels; pad missing channels with 0."""
    need = count * 3
    if len(data) < need:
        data = data + bytes(need - len(data))
    out: list[tuple[int, int, int]] = []
    for i in range(count):
        o = i * 3
        out.append((data[o], data[o + 1], data[o + 2]))
    return out


@dataclass(frozen=True)
class BridgeConfig:
    hz: float
    ddp_port: int
    ddp_bind: str
    lights: tuple[str, ...]
    ha_url: str
    ha_token: str

    @property
    def channels(self) -> int:
        return len(self.lights) * 3

    @property
    def min_interval(self) -> float:
        return 1.0 / self.hz if self.hz > 0 else 1.0


def load_config_from_env() -> BridgeConfig:
    """Load config from environment (add-on run.sh or local smoke)."""
    lights_raw = os.environ.get("LIGHTS_JSON", "[]")
    lights = tuple(json.loads(lights_raw))
    if not lights:
        raise SystemExit("No lights configured (LIGHTS_JSON empty)")

    ha_url = os.environ.get("HA_URL", "").rstrip("/")
    ha_token = os.environ.get("HA_TOKEN", "").strip()
    if not ha_url or not ha_token:
        raise SystemExit("HA_URL and HA_TOKEN are required")

    # Normalize: accept base with or without /api
    if ha_url.endswith("/api"):
        api_base = ha_url
    else:
        api_base = f"{ha_url}/api"

    return BridgeConfig(
        hz=float(os.environ.get("HZ", "5")),
        ddp_port=int(os.environ.get("DDP_PORT", "4048")),
        ddp_bind=os.environ.get("DDP_BIND", "0.0.0.0"),
        lights=lights,
        ha_url=api_base,
        ha_token=ha_token,
    )


def load_config_from_options(path: Path | str = "/data/options.json") -> BridgeConfig:
    """Load Supervisor add-on options + SUPERVISOR_TOKEN."""
    options = json.loads(Path(path).read_text())
    lights = tuple(item["entity_id"] for item in options.get("lights", []))
    token = os.environ.get("SUPERVISOR_TOKEN", "").strip()
    if not token:
        raise SystemExit("SUPERVISOR_TOKEN missing (not running as add-on?)")
    return BridgeConfig(
        hz=float(options.get("hz", 5)),
        ddp_port=int(options.get("ddp_port", 4048)),
        ddp_bind=str(options.get("ddp_bind", "0.0.0.0")),
        lights=lights,
        ha_url="http://supervisor/core/api",
        ha_token=token,
    )


def resolve_config() -> BridgeConfig:
    options = Path("/data/options.json")
    if options.is_file() and os.environ.get("SUPERVISOR_TOKEN"):
        return load_config_from_options(options)
    return load_config_from_env()


class HomeAssistantClient:
    def __init__(self, api_base: str, token: str, timeout: float = 4.0) -> None:
        self.api_base = api_base.rstrip("/")
        self.token = token
        self.timeout = timeout

    def call_light(self, service: str, payload: dict) -> None:
        req = urllib.request.Request(
            f"{self.api_base}/services/light/{service}",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp.read()
        except urllib.error.HTTPError as e:
            body = e.read()[:200]
            print(f"HA light.{service} HTTP {e.code}: {body!r}", flush=True)
        except Exception as e:
            print(f"HA light.{service} error: {e}", flush=True)


def apply_pixels(
    client: HomeAssistantClient,
    lights: Sequence[str],
    pixels: Sequence[tuple[int, int, int]],
    last: list[tuple[int, int, int] | None],
) -> None:
    """Push changed pixels to HA light entities."""
    for i, entity in enumerate(lights):
        r, g, b = pixels[i]
        if last[i] == (r, g, b):
            continue
        last[i] = (r, g, b)
        if r == 0 and g == 0 and b == 0:
            client.call_light("turn_off", {"entity_id": entity})
        else:
            client.call_light(
                "turn_on",
                {
                    "entity_id": entity,
                    "rgb_color": [r, g, b],
                    "brightness": max(r, g, b),
                },
            )


def run_bridge(
    config: BridgeConfig,
    *,
    client: HomeAssistantClient | None = None,
    recv: Callable[[], bytes | None] | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Main loop. `recv` injectable for tests (returns packet or None on idle)."""
    ha = client or HomeAssistantClient(config.ha_url, config.ha_token)
    last: list[tuple[int, int, int] | None] = [None] * len(config.lights)
    latest = bytearray(config.channels)
    dirty = False
    last_sent = 0.0

    sock: socket.socket | None = None
    if recv is None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((config.ddp_bind, config.ddp_port))
        sock.settimeout(min(0.5, config.min_interval))

        def recv_sock() -> bytes | None:
            try:
                packet, _addr = sock.recvfrom(4096)
                return packet
            except socket.timeout:
                return None

        recv = recv_sock

    print(
        f"Listening DDP on {config.ddp_bind}:{config.ddp_port} → {config.ha_url} "
        f"({len(config.lights)} lights @ {config.hz} Hz)",
        flush=True,
    )
    for i, entity in enumerate(config.lights):
        print(f"  pixel {i} → {entity}", flush=True)

    try:
        while True:
            packet = recv()
            if packet is not None:
                data = parse_ddp(packet)
                if data is not None:
                    chunk = data[: config.channels]
                    if len(chunk) < config.channels:
                        chunk = chunk + bytes(config.channels - len(chunk))
                    if chunk != latest:
                        latest[:] = chunk
                        dirty = True

            now = clock()
            if not dirty or (now - last_sent) < config.min_interval:
                if sock is None and packet is None:
                    # test mode with idle recv: avoid busy spin
                    sleep(0.01)
                continue

            dirty = False
            last_sent = now
            pixels = pixels_from_rgb(bytes(latest), len(config.lights))
            apply_pixels(ha, config.lights, pixels, last)
    finally:
        if sock is not None:
            sock.close()


def main() -> None:
    config = resolve_config()
    run_bridge(config)


if __name__ == "__main__":
    main()
