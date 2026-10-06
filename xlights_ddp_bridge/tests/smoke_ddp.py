#!/usr/bin/env python3
"""Send a one-shot DDP test pattern to a running bridge (local or add-on)."""
from __future__ import annotations

import argparse
import socket

from bridge.bridge import build_ddp_packet


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=4048)
    p.add_argument(
        "--rgb",
        default="255,0,0,0,255,0,0,0,255,139,0,255",
        help="Comma-separated RGB bytes for N pixels",
    )
    args = p.parse_args()
    rgb = bytes(int(x) for x in args.rgb.split(",") if x.strip() != "")
    pkt = build_ddp_packet(rgb)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(pkt, (args.host, args.port))
    print(f"Sent {len(rgb) // 3} pixels ({len(pkt)} bytes) → {args.host}:{args.port}")


if __name__ == "__main__":
    main()
