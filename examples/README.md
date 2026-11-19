# Examples

Small, complete examples. Each one says at its top what it needs and where its commands come from
in the documentation. The documentation at https://exducer.ai/docs is the reference.

| Example | Needs | What it shows |
| --- | --- | --- |
| [`api/public.sh`](api/public.sh) | Nothing | Availability, prices, status, templates and a quote, with curl |
| [`mcp/hosted-server.sh`](mcp/hosted-server.sh) | Nothing | The hosted MCP server with curl: initialize, list the tools, call one |
| [`mcp/quote.py`](mcp/quote.py) | Nothing | A dependency-free Python client of the MCP server: what is free, what a booking would cost |
| [`mcp/clients.md`](mcp/clients.md) | Nothing | Registering the server in Claude Code, Codex and other agents; which key opens which tools |
| [`webhooks/verify.py`](webhooks/verify.py), [`webhooks/verify.mjs`](webhooks/verify.mjs) | Nothing | Checking the signature of a webhook delivery, in Python and Node.js, with a self-test |
| [`cli/sandbox-rehearsal.sh`](cli/sandbox-rehearsal.sh) | A sandbox key | A booking from quote to stop with the CLI, simulated |
| [`api/sandbox-lifecycle.sh`](api/sandbox-lifecycle.sh) | A sandbox key | The same through the REST API, simulated |
| [`models-api/chat.sh`](models-api/chat.sh), [`models-api/chat.py`](models-api/chat.py) | A write key, Models API access | One chat completion; this call is billed |

## Keys

- Put the key in the environment (`export TURBO_API_KEY=...`) or in `turbo login`. Never in a file
  of your project, a commit or a chat.
- A sandbox key (Account, then API keys, with the Sandbox key option) starts with `tml_test_`. It
  calls the same endpoints against a simulated lifecycle and charges nothing. The two sandbox
  examples refuse any other key.
- A read key is enough to look. Booking and stopping need a write key.
