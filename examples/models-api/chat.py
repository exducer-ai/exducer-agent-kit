#!/usr/bin/env python3
"""One chat completion from the Models API with the OpenAI client.

The Models API is a preview, with access on request. It needs a write or admin API key (a read key
is refused) and draws from your prepaid credit: this call is billed.

    pip install openai requests
    export TURBO_API_KEY=...      # never write the key into a file
    python3 examples/models-api/chat.py

Source: https://exducer.ai/docs/models-inference/mi-api
"""
import os

import requests
from openai import OpenAI

BASE = "https://api.exducer.ai/api/v1/maas"

key = os.environ.get("TURBO_API_KEY")
if not key:
    raise SystemExit("Set TURBO_API_KEY first.")

# The served model: ask the service instead of pinning a name.
model = requests.get(f"{BASE}/health", timeout=30).json()["model"]

client = OpenAI(base_url=BASE, api_key=key)
r = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": "Bonjour!"}],
    max_tokens=100,
    stream=False,  # streaming is not served yet
)
print(r.choices[0].message.content)
