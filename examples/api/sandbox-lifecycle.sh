#!/bin/sh
# The whole life of a deployment through the REST API, on the sandbox: quote, request, wait,
# read the events, stop, read the usage. A sandbox key simulates everything and charges nothing.
#
#   export TURBO_API_KEY=...      # a sandbox key: Account -> API keys, with the Sandbox key option
#   sh examples/api/sandbox-lifecycle.sh ~/.ssh/id_ed25519.pub
#
# The commands are the ones on https://exducer.ai/docs/compute/c-provisioning
# ("Try it without spending: sandbox keys").
set -e
API="${TURBO_API:-https://api.exducer.ai}"
PUBKEY_FILE="${1:-$HOME/.ssh/id_ed25519.pub}"

case "${TURBO_API_KEY:-}" in
  tml_test_*) ;;
  "") echo "Set TURBO_API_KEY to a sandbox key first."; exit 2 ;;
  *)  echo "TURBO_API_KEY is not a sandbox key (those start with tml_test_). This example refuses a live key."; exit 2 ;;
esac
[ -r "$PUBKEY_FILE" ] || { echo "Give an SSH public key file (.pub) as the first argument."; exit 2; }

auth="Authorization: Bearer $TURBO_API_KEY"
field() { python3 -c 'import json,sys; print(json.load(sys.stdin).get(sys.argv[1]) or "")' "$1"; }

echo "== 1. The quote (public)"
curl -fsS "$API/api/bookings/preview" -H "Content-Type: application/json" \
  -d '{"serverId":"rtx-pro-6000","gpus":8,"pricing":"ondemand","durationHours":1}'
echo

echo "== 2. The request, with an idempotency key so a retry never books twice"
body=$(python3 -c '
import json, sys
print(json.dumps({"serverId": "rtx-pro-6000", "gpus": 8, "pricing": "ondemand", "durationHours": 1,
                  "sshKey": open(sys.argv[1]).read().strip(), "clientReference": "example-1",
                  "sandbox": {"speed": 10}}))' "$PUBKEY_FILE")
id=$(curl -fsS "$API/api/bookings" -H "$auth" -H "Content-Type: application/json" \
  -H "Idempotency-Key: example-$(date -u +%Y%m%d%H%M%S)" -d "$body" | field id)
[ -n "$id" ] || { echo "The request returned no id."; exit 1; }
echo "deployment $id"

echo "== 3. Poll until it runs"
n=0
while :; do
  phase=$(curl -fsS -H "$auth" "$API/api/v1/deployments/$id" | field phase)
  echo "  $phase"
  case "$phase" in running) break ;; stopped|ended|failed|cancelled) echo "It ended before running."; break ;; esac
  n=$((n + 1)); [ "$n" -lt 60 ] || { echo "Still not running after five minutes."; break; }
  sleep 5
done

echo "== 4. Its events, oldest first"
curl -fsS -H "$auth" "$API/api/v1/deployments/$id/events"
echo

echo "== 5. Stop it"
curl -fsS -X DELETE -H "$auth" "$API/api/v1/deployments/$id"
echo

echo "== 6. The usage report and the simulated balance"
curl -fsS -H "$auth" "$API/api/billing/usage?group=type"
echo
curl -fsS -H "$auth" "$API/api/billing/credits/balance"
echo
