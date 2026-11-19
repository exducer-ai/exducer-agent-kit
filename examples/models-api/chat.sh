#!/bin/sh
# One chat completion from the Models API with curl.
#
# The Models API is a preview, with access on request. It needs a write or admin API key (a read
# key is refused) and draws from your prepaid credit: this call is billed.
#
#   export TURBO_API_KEY=...      # never write the key into a file
#   sh examples/models-api/chat.sh
#
# Source: https://exducer.ai/docs/models-inference/mi-api
set -e
[ -n "${TURBO_API_KEY:-}" ] || { echo "Set TURBO_API_KEY first."; exit 2; }

curl -fsS https://api.exducer.ai/api/v1/maas/chat/completions \
  -H "Authorization: Bearer $TURBO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Summarize PIPEDA in two sentences."}],
    "max_tokens": 300
  }'
echo
