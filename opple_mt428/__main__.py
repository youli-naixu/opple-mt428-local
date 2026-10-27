# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 youli-naixu and contributors

import argparse
import json
import logging
import sys

from .discovery import discover
from .protocol import LampError, OppleLamp
from .server import serve
from .simulator import SimulatedLamp


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description="OPPLE MT428 局域网发现、只读研究与网页控制 / LAN discovery, research and web control")
    sub = parser.add_subparsers(dest="command", required=True)
    search = sub.add_parser("discover", help="只读发现 / read-only discovery (SEARCH only)")
    group = search.add_mutually_exclusive_group(required=True)
    group.add_argument("--interface", help="本机网卡IPv4/CIDR / local interface IPv4/CIDR")
    group.add_argument("--target", help="已知台灯IP / one known device IPv4")
    search.add_argument("--bind", default="0.0.0.0", help="单播本机源IP / source IPv4 for direct discovery")
    search.add_argument("--timeout", type=float, default=3.0)
    search.add_argument("--json", action="store_true", help="输出JSON / JSON output (contains local device identity)")
    query = sub.add_parser("status", help="只查询 / read-only state query")
    web = sub.add_parser("serve", help="本地网页 / localhost web demo")
    for item in (query, web):
        item.add_argument("--ip", help="台灯单播IPv4 / device unicast IPv4")
        item.add_argument("--mac", help="预期台灯MAC / expected device MAC")
        item.add_argument("--bind", default="0.0.0.0")
        item.add_argument("--experimental-side-light", action="store_true", help="候选侧灯字段，尚未真机验证 / unverified side-light fields")
    web.add_argument("--port", type=int, default=8765)
    web.add_argument("--simulate", action="store_true", help="纯内存模拟，不连接实物 / in-memory preview, no hardware")
    access = web.add_mutually_exclusive_group()
    access.add_argument("--allow-write", action="store_true", help="允许改变实物灯光 / explicitly allow real light changes")
    access.add_argument("--read-only", action="store_true", help="禁止写入（实物默认） / block writes (default for hardware)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    try:
        if args.command == "discover":
            candidates = discover(interface=args.interface, target=args.target, bind=args.bind, timeout=args.timeout)
            if args.json:
                print(json.dumps([item.as_dict() for item in candidates], ensure_ascii=False, indent=2))
            else:
                for item in candidates:
                    print(f"{item.ip}:{item.port}  {item.mac}  SKU {item.sku}  {item.name}")
                print(f"{len(candidates)} candidate(s). No light-changing command was sent.")
            return
        if args.command == "serve" and args.simulate:
            if args.ip or args.mac:
                parser.error("--simulate must not be combined with a hardware --ip/--mac")
            lamp = SimulatedLamp(read_only=args.read_only, experimental_side_light=args.experimental_side_light)
        else:
            if not args.ip or not args.mac:
                parser.error("Hardware access requires explicit --ip and --mac; run discover first")
            lamp = OppleLamp(args.ip, args.mac, bind=args.bind, read_only=args.command == "status" or not args.allow_write, experimental_side_light=args.experimental_side_light)
        if args.command == "status":
            try:
                state = lamp.query()
                print(json.dumps({"device": lamp.identity, "state": state, "read_only": True}, ensure_ascii=False, indent=2))
            finally:
                lamp.close()
        else:
            serve(lamp, args.port)
    except (LampError, OSError, ValueError) as error:
        parser.exit(1, f"Error / 错误: {error}\n")


if __name__ == "__main__":
    main()
