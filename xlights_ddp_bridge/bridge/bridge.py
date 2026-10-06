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

from .stats import RuntimeStats
from .webui import start_webui


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
    """Runtime configuration for the DDP → HA bridge."""

    hz: float
    ddp_port: int
    ddp_bind: str
    lights: tuple[str, ...]
    ha_url: str
    ha_token: str

    @property
    def channels(self) -> int:
        """Total RGB channels (= 3 × light count)."""
        return len(self.lights) * 3

    @property
    def min_interval(self) -> float:
        """Minimum seconds between HA update batches."""
        return 1.0 / self.hz if self.hz > 0 else 1.0


def load_config_from_env() -> BridgeConfig:
    """Load config from environment (add-on run.sh or local development)."""
    lights_raw = os.environ.get("LIGHTS_JSON", "[]")
    parsed = json.loads(lights_raw)
    if not isinstance(parsed, list):
        raise SystemExit("LIGHTS_JSON must be a JSON array of entity_id strings")
    lights = tuple(str(item) for item in parsed)
    if not lights:
        raise SystemExit("No lights configured (LIGHTS_JSON empty)")

    ha_url = os.environ.get("HA_URL", "").rstrip("/")
    ha_token = os.environ.get("HA_TOKEN", "").strip()
    if not ha_url or not ha_token:
        raise SystemExit("HA_URL and HA_TOKEN are required")

    api_base = ha_url if ha_url.endswith("/api") else f"{ha_url}/api"

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
    options = json.loads(Path(path).read_text(encoding="utf-8"))
    lights = tuple(str(item["entity_id"]) for item in options.get("lights", []))
    if not lights:
        raise SystemExit("No lights configured in options.json")
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
    """Prefer Supervisor options when present; otherwise use environment vars."""
    options = Path("/data/options.json")
    if options.is_file() and os.environ.get("SUPERVISOR_TOKEN"):
        return load_config_from_options(options)
    return load_config_from_env()


class HomeAssistantClient:
    """Minimal Home Assistant REST client for light.turn_on / turn_off."""

    def __init__(self, api_base: str, token: str, timeout: float = 4.0) -> None:
        self.api_base = api_base.rstrip("/")
        self.token = token
        self.timeout = timeout

    def call_light(self, service: str, payload: dict[str, object]) -> None:
        """Call a `light` domain service; log errors without raising."""
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
        except Exception as e:  # noqa: BLE001 — keep bridge loop alive on network blips
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
    stats: RuntimeStats | None = None,
    client: HomeAssistantClient | None = None,
    recv: Callable[[], bytes | None] | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Main loop. `recv` injectable for tests (returns packet or None on idle)."""
    ha = client or HomeAssistantClient(config.ha_url, config.ha_token)
    state = stats or RuntimeStats()
    state.configure(
        hz=config.hz,
        ddp_port=config.ddp_port,
        ddp_bind=config.ddp_bind,
        lights=list(config.lights),
    )

    lights = list(config.lights)
    hz = config.hz
    last: list[tuple[int, int, int] | None] = [None] * len(lights)
    latest = bytearray(len(lights) * 3)
    dirty = False
    last_sent = 0.0

    sock: socket.socket | None = None
    peer_holder: list[str | None] = [None]
    if recv is None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((config.ddp_bind, config.ddp_port))
        sock.settimeout(min(0.5, 1.0 / hz if hz > 0 else 0.5))
        state.set_listening(True)
        state.event("info", f"DDP listening on {config.ddp_bind}:{config.ddp_port}")

        def recv_sock() -> bytes | None:
            try:
                packet, addr = sock.recvfrom(4096)
                peer_holder[0] = f"{addr[0]}:{addr[1]}"
                return packet
            except socket.timeout:
                return None

        recv = recv_sock

    print(
        f"Listening DDP on {config.ddp_bind}:{config.ddp_port} → {config.ha_url} "
        f"({len(lights)} lights @ {hz} Hz)",
        flush=True,
    )
    for i, entity in enumerate(lights):
        print(f"  pixel {i} → {entity}", flush=True)

    try:
        while True:
            # Hot-reload lights / hz from Ingress saves
            snap = state.snapshot()
            snap_lights = snap["lights"]
            snap_hz = float(snap["hz"])
            if snap_lights != lights or snap_hz != hz:
                lights = list(snap_lights)
                hz = snap_hz
                last = [None] * len(lights)
                latest = bytearray(len(lights) * 3)
                dirty = False
                if sock is not None:
                    sock.settimeout(min(0.5, 1.0 / hz if hz > 0 else 0.5))
                print(f"Reloaded mapping: {len(lights)} lights @ {hz} Hz", flush=True)

            packet = recv()
            if packet is not None:
                data = parse_ddp(packet)
                if data is not None:
                    peer = peer_holder[0] or "unknown"
                    state.note_packet(peer, len(data))
                    channels = len(lights) * 3
                    chunk = data[:channels]
                    if len(chunk) < channels:
                        chunk = chunk + bytes(channels - len(chunk))
                    if chunk != latest:
                        latest[:] = chunk
                        dirty = True

            now = clock()
            min_interval = 1.0 / hz if hz > 0 else 1.0
            if not dirty or (now - last_sent) < min_interval:
                if sock is None and packet is None:
                    sleep(0.01)
                continue

            dirty = False
            last_sent = now
            pixels = pixels_from_rgb(bytes(latest), len(lights))
            apply_pixels(ha, lights, pixels, last)
            state.note_colors(pixels)
    finally:
        state.set_listening(False)
        if sock is not None:
            sock.close()


def main() -> None:
    config = resolve_config()
    stats = RuntimeStats()
    stats.configure(
        hz=config.hz,
        ddp_port=config.ddp_port,
        ddp_bind=config.ddp_bind,
        lights=list(config.lights),
    )

    ingress_port = int(os.environ.get("INGRESS_PORT", "8099"))
    try:
        start_webui(
            stats,
            port=ingress_port,
            ha_api=config.ha_url,
            ha_token=config.ha_token,
        )
    except OSError as e:
        print(f"Ingress UI failed to start: {e}", flush=True)
        stats.event("error", f"Ingress UI failed: {e}")

    run_bridge(config, stats=stats)


if __name__ == "__main__":
    main()
