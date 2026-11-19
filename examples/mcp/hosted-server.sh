#!/bin/sh
# Talk to the hosted MCP server with nothing but curl. No key: the public tools answer.
#   sh examples/mcp/hosted-server.sh
# With a key, the account tools answer too:
#   export TURBO_API_KEY=...   then run it again
set -e
URL="${TURBO_MCP_URL:-https://exducer.ai/mcp}"

rpc() {
  if [ -n "${TURBO_API_KEY:-}" ]; then
    curl -fsS -X POST "$URL" -H "Content-Type: application/json" \
      -H "Accept: application/json, text/event-stream" \
      -H "Authorization: Bearer $TURBO_API_KEY" -d "$1"
  else
    curl -fsS -X POST "$URL" -H "Content-Type: application/json" \
      -H "Accept: application/json, text/event-stream" -d "$1"
  fi
}

echo "== initialize"
rpc '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl-example","version":"1"}}}'
echo

echo "== tools/list (names only)"
rpc '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | python3 -c '
import json, sys
for t in json.load(sys.stdin)["result"]["tools"]:
    print(" ", t["name"])'

echo "== tools/call check_availability"
rpc '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"check_availability","arguments":{}}}' | python3 -c '
import json, sys
for part in json.load(sys.stdin)["result"]["content"]:
    if part.get("type") == "text":
        print(part["text"])'
