#!/bin/sh
# Public endpoints: no account and no key needed. Nothing is booked.
#   sh examples/api/public.sh
set -e
SITE="${TURBO_SITE:-https://exducer.ai}"
API="${TURBO_API:-https://api.exducer.ai}"

echo "== Is each GPU model free right now (yes or no per model)"
curl -fsS "$SITE/api/v1/public/availability"
echo

echo "== List prices, in CAD"
curl -fsS "$SITE/api/v1/public/pricing"
echo

echo "== Service status"
curl -fsS "$SITE/api/v1/public/status"
echo

echo "== Templates: the images a deployment can run"
curl -fsS "$API/api/v1/templates" | python3 -c '
import json, sys
for t in json.load(sys.stdin):
    print(" ", t["slug"], "-", t["name"])'

echo "== A quote: 8 GPUs for one day. It books nothing and charges nothing."
curl -fsS "$API/api/bookings/preview" -H "Content-Type: application/json" \
  -d '{"serverId":"rtx-pro-6000","gpus":8,"pricing":"ondemand","durationHours":24}'
echo
