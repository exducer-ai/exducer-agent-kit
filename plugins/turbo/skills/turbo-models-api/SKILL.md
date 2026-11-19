---
name: turbo-models-api
description: "Call the ExducerAI Models API, an OpenAI-compatible chat completions endpoint served from GPUs in Montréal (preview). Covers the base URL, how to find the served model, the parameters it accepts, that streaming is off, how calls are billed from prepaid credit, and the 402 and 503 answers. Use when the user wants to point an OpenAI client, an SDK or their own code at ExducerAI's hosted model, or to try a prompt from the command line."
---

# The Models API (preview)

One hosted model behind an OpenAI-compatible endpoint. Access is on request during the preview: if
calls are refused for the account, the user writes to hello@exducer.ai.

## The essentials

- Base URL: `https://api.exducer.ai/api/v1/maas`
- Endpoint: `POST /chat/completions`
- Key: a **write** or admin API key (`tml_...`) as a Bearer token. A read key is refused, and a
  sandbox key cannot call it.
- Model: do not hard-code a name. Ask `GET /api/v1/maas/health` (with the key) and use its
  `model`, or omit `model` and the API fills it in.
- Parameters: `messages`, `max_tokens`, `temperature`. `stream` must be `false` for now.

```bash
curl -s https://api.exducer.ai/api/v1/maas/chat/completions \
  -H "Authorization: Bearer $TURBO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello"}],"max_tokens":200}'
```

```python
import os, requests
from openai import OpenAI

base = "https://api.exducer.ai/api/v1/maas"
key = os.environ["TURBO_API_KEY"]
model = requests.get(f"{base}/health", headers={"Authorization": f"Bearer {key}"}).json()["model"]
client = OpenAI(base_url=base, api_key=key)
r = client.chat.completions.create(model=model, messages=[{"role": "user", "content": "Bonjour!"}])
print(r.choices[0].message.content)
```

From the CLI: `turbo chat "your prompt" --max-tokens 300`.

## Billing

Each call is charged to the prepaid credit after it completes, at the rates published at
`https://exducer.ai/api/v1/public/pricing` (the `models` entry). Each call is a line in the credit
ledger. Tell the user before running a large batch: it spends their credit.

## Answers to handle

| Status | Meaning | What to do |
| --- | --- | --- |
| `402 insufficient_credit` | No prepaid credit left | The user tops up; do not retry |
| `403 api_key_scope` | Read key | The user creates a write key |
| `503` | Every GPU is rented; the call is refused, not queued | Retry later with backoff, or serve the model on a rented node |
| `504` | The call ran past the server's time limit | Shorten the request or lower `max_tokens` |

Preview means best effort: the hosted model shares GPU capacity with rentals and has no reserved
capacity. For steady traffic, rent a node and serve a model there (vLLM, SGLang, TGI, Ollama and
llama.cpp templates exist): see `turbo-deploy` and
https://exducer.ai/docs/models-inference/mi-hosting.md.

## Data

Prompts are processed in Québec and are not used for training.
