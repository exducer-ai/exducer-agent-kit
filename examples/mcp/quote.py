#!/usr/bin/env python3
"""Ask the hosted MCP server what is free and what a booking would cost.

No key and no dependency: Python 3.9 or newer. Nothing is booked.

    python3 examples/mcp/quote.py            # 8 GPUs for 24 hours on the first bookable server
    python3 examples/mcp/quote.py 8 48       # GPUs, hours
"""
import json
import os
import sys
import urllib.request

URL = os.environ.get("TURBO_MCP_URL", "https://exducer.ai/mcp")
_next_id = 0


def rpc(method, params=None):
    """One JSON-RPC call. The server is stateless: no session to open or close."""
    global _next_id
    _next_id += 1
    body = json.dumps({"jsonrpc": "2.0", "id": _next_id, "method": method, "params": params or {}}).encode()
    # Name your client: the default Python user agent is turned away at the edge (403).
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
               "User-Agent": "exducer-mcp-example/1"}
    key = os.environ.get("TURBO_API_KEY")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    with urllib.request.urlopen(urllib.request.Request(URL, body, headers), timeout=30) as r:
        answer = json.load(r)
    if "error" in answer:
        raise SystemExit(f"{method}: {answer['error'].get('message')}")
    return answer["result"]


def tool(name, **arguments):
    """Call one tool and return its text."""
    result = rpc("tools/call", {"name": name, "arguments": arguments})
    text = "\n".join(p["text"] for p in result.get("content", []) if p.get("type") == "text")
    if result.get("isError"):
        raise SystemExit(f"{name}: {text}")
    return text


def main():
    gpus = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24

    info = rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                              "clientInfo": {"name": "quote-example", "version": "1"}})
    print(f"server: {info['serverInfo'].get('title')} {info['serverInfo'].get('version')}")

    print("\n== Free right now?")
    print(tool("check_availability"))

    print("\n== Bookable servers")
    servers = tool("list_servers")
    print(servers)

    # list_servers answers in JSON text; take the first server id from it.
    try:
        data = json.loads(servers)
        rows = data if isinstance(data, list) else data.get("servers") or data.get("items") or []
        server_id = rows[0]["id"]
    except (ValueError, LookupError, TypeError):
        raise SystemExit("Could not read a server id from list_servers; pass one to quote_booking yourself.")

    print(f"\n== Quote: {gpus} GPUs for {hours} hours on {server_id}")
    print(tool("quote_booking", server_id=server_id, gpus=gpus, hours=hours))


if __name__ == "__main__":
    main()
