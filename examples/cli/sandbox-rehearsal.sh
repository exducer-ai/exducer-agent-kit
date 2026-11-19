#!/bin/sh
# Rehearse a booking from request to stop with the turbo CLI, on the sandbox.
# A sandbox key simulates everything and charges nothing.
#
#   curl -sSL https://exducer.ai/cli/install.sh | sh
#   export TURBO_API_KEY=...      # a sandbox key: Account -> API keys, with the Sandbox key option
#   sh examples/cli/sandbox-rehearsal.sh ~/.ssh/id_ed25519.pub
#
# The commands are the ones on https://exducer.ai/docs/getting-started/gs-agents
# ("Rehearse on the sandbox").
set -e
PUBKEY_FILE="${1:-$HOME/.ssh/id_ed25519.pub}"

case "${TURBO_API_KEY:-}" in
  tml_test_*) ;;
  "") echo "Set TURBO_API_KEY to a sandbox key first."; exit 2 ;;
  *)  echo "TURBO_API_KEY is not a sandbox key (those start with tml_test_). This example refuses a live key."; exit 2 ;;
esac
command -v turbo >/dev/null 2>&1 || { echo "Install the CLI first: curl -sSL https://exducer.ai/cli/install.sh | sh"; exit 2; }
[ -r "$PUBKEY_FILE" ] || { echo "Give an SSH public key file (.pub) as the first argument."; exit 2; }

echo "== The quote"
turbo quote --server rtx-pro-6000 --gpus 8 --hours 1 --json

echo "== The request (ten times faster than real time)"
id=$(turbo book --server rtx-pro-6000 --gpus 8 --hours 1 --ssh-key "$PUBKEY_FILE" \
  --idempotency-key "rehearsal-$(date -u +%Y%m%d%H%M%S)" --speed 10 --yes --json \
  | python3 -c 'import json,sys; print(json.load(sys.stdin).get("id") or "")')
[ -n "$id" ] || { echo "The request returned no id."; exit 1; }
echo "deployment $id"

echo "== Wait until it runs (exit 0 running, 3 ended otherwise, 4 timed out)"
turbo wait "$id" --until running --timeout 600

echo "== State, rate, cost so far, end time"
turbo deployment "$id" --json

echo "== Stop it"
turbo stop "$id" --yes
