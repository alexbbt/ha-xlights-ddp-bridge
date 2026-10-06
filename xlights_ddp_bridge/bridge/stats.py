"""Thread-safe runtime stats and event log for the Ingress UI."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuntimeStats:
    """Shared state between the DDP loop and Ingress web UI."""

    hz: float = 5.0
    ddp_port: int = 4048
    ddp_bind: str = "0.0.0.0"
    lights: list[str] = field(default_factory=list)

    listening: bool = False
    last_peer: str | None = None
    last_packet_at: float | None = None
    last_payload_len: int = 0
    packet_times: deque[float] = field(default_factory=lambda: deque(maxlen=200))
    last_colors: list[tuple[int, int, int] | None] = field(default_factory=list)

    ha_ok: bool | None = None
    ha_last_check_at: float | None = None
    ha_missing: list[str] = field(default_factory=list)
    events: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=50))

    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def configure(
        self,
        *,
        hz: float,
        ddp_port: int,
        ddp_bind: str,
        lights: list[str],
    ) -> None:
        with self._lock:
            self.hz = hz
            self.ddp_port = ddp_port
            self.ddp_bind = ddp_bind
            self.lights = list(lights)
            self.last_colors = [None] * len(lights)

    def set_lights(self, lights: list[str], *, hz: float | None = None) -> None:
        with self._lock:
            if hz is not None:
                self.hz = hz
            self.lights = list(lights)
            # Preserve colors for overlapping indices
            old = self.last_colors
            self.last_colors = [
                old[i] if i < len(old) else None for i in range(len(lights))
            ]
            self.event("config", f"Lights updated ({len(lights)} pixels)")

    def set_listening(self, listening: bool) -> None:
        with self._lock:
            self.listening = listening

    def note_packet(self, peer: str, payload_len: int) -> None:
        now = time.time()
        with self._lock:
            self.last_peer = peer
            self.last_packet_at = now
            self.last_payload_len = payload_len
            self.packet_times.append(now)

    def note_colors(self, colors: list[tuple[int, int, int]]) -> None:
        with self._lock:
            self.last_colors = list(colors)

    def note_ha_check(
        self, ok: bool, missing: list[str] | None = None
    ) -> None:
        with self._lock:
            self.ha_ok = ok
            self.ha_last_check_at = time.time()
            self.ha_missing = list(missing or [])

    def event(self, kind: str, message: str) -> None:
        with self._lock:
            self.events.appendleft(
                {"t": time.time(), "kind": kind, "message": message}
            )

    def packets_per_second(self, window: float = 5.0) -> float:
        now = time.time()
        with self._lock:
            recent = [t for t in self.packet_times if now - t <= window]
        if not recent:
            return 0.0
        span = max(now - recent[0], 0.001)
        return len(recent) / span

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            expected = len(self.lights) * 3
            age = (
                None
                if self.last_packet_at is None
                else max(0.0, time.time() - self.last_packet_at)
            )
            return {
                "hz": self.hz,
                "ddp_port": self.ddp_port,
                "ddp_bind": self.ddp_bind,
                "lights": list(self.lights),
                "listening": self.listening,
                "last_peer": self.last_peer,
                "last_packet_age_s": age,
                "last_payload_len": self.last_payload_len,
                "expected_payload_len": expected,
                "payload_matches": self.last_payload_len == expected
                if self.last_packet_at
                else None,
                "packets_per_second": round(self.packets_per_second(), 2),
                "last_colors": [
                    list(c) if c is not None else None for c in self.last_colors
                ],
                "ha_ok": self.ha_ok,
                "ha_last_check_at": self.ha_last_check_at,
                "ha_missing": list(self.ha_missing),
                "events": list(self.events),
            }
