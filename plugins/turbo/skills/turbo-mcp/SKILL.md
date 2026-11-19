---
name: turbo-mcp
description: "The ExducerAI MCP server - how to register it in Claude Code, Codex, Cursor and other MCP clients (hosted at https://exducer.ai/mcp or over stdio with `turbo mcp`), which tools it has (pricing, availability, servers, templates, quotes, bookings, deployments, events, billing, usage, docs search), which need an API key, and the confirmation and idempotency rules of the tools that spend or delete. Use when tools named like check_availability, create_booking or get_deployment are available, or when asked to connect an agent to ExducerAI."
---

# The ExducerAI MCP server

The same API as the console and the CLI, as tools. Stateless, Streamable HTTP, JSON answers.

## Register it

The simplest route registers it for every coding agent found on the machine, together with these
skills:

```bash
turbo agent setup
```

By hand, pick one of the two transports.

**stdio through the CLI** (the key stays in `~/.config/turbo`, nothing is copied into the agent's
settings):

```bash
claude mcp add --scope user turbo -- turbo mcp        # Claude Code
codex mcp add turbo -- turbo mcp                      # Codex
```

```json
{ "mcpServers": { "turbo": { "command": "turbo", "args": ["mcp"] } } }
```

**Hosted, with the key as a header** (no CLI needed):

```bash
claude mcp add --transport http --scope user turbo https://exducer.ai/mcp \
  --header "Authorization: Bearer $TURBO_API_KEY"
```

```json
{ "mcpServers": { "turbo": { "url": "https://exducer.ai/mcp",
    "headers": { "Authorization": "Bearer ${TURBO_API_KEY}" } } } }
```

Without a key the server still answers the public tools.

## Tools

Public (no key):

| Tool | Returns |
| --- | --- |
| `get_pricing` | List prices: GPU-hour, storage, Models API. CAD |
| `check_availability` | One yes or no per GPU model, right now |
| `get_service_status` | Public status of each service |
| `list_servers` | Bookable servers: id, price, `allowed_gpu_counts` |
| `list_templates` | Template slugs and the image each runs |
| `quote_booking` | What a booking would cost, tax included. Books nothing |
| `search_docs` | Sections of the documentation that match a query |
| `read_doc` | One documentation page as Markdown |

With a read key:

| Tool | Returns |
| --- | --- |
| `get_account` | Account and prepaid balance |
| `list_deployments` | Every deployment (`include_sandbox` adds sandbox rows on a live key) |
| `get_deployment` | State, SSH host and port, host key fingerprint, rate, cost so far, end time |
| `get_deployment_events` | State changes with reasons |
| `wait_for_deployment` | Polls for up to 50 seconds; call again while `reached` is false |
| `get_billing` | Balance and recent ledger lines |
| `get_usage` | Charges per day or per type for a date range |
| `list_invoices` | Invoices |
| `list_ssh_keys` | SSH public keys saved on the account |
| `get_storage_usage` | Object storage used and billed this month |

With a write key (each needs `confirm: true`):

| Tool | Does |
| --- | --- |
| `create_booking` | Sends a GPU request |
| `extend_deployment` | Adds hours to a deployment |
| `set_auto_renew` | Turns renewal at the end of the term on or off |
| `stop_deployment` | Stops it now and deletes its container and disk, or withdraws a request |

## Rules of the write tools

- `confirm: true` is your statement that the user approved **this** action after seeing its cost
  (or, for a stop, after being told the disk is deleted). Never set it on your own initiative.
  With a sandbox key (`tml_test_`) nothing is real, so you may set it freely.
- `create_booking` and `extend_deployment` are retry-safe. If you pass no `idempotency_key`, the
  server derives one from the request and the UTC date, so sending the identical request again the
  same day returns the first answer instead of acting twice. To really book or extend a second
  time with identical parameters, pass a new `idempotency_key`. An answer with `replayed: true` is
  that stored first answer: nothing new was done, so read the deployment's current state before
  telling the user anything.
- `create_booking` needs an SSH public key: pass `ssh_public_key` (the text of the `.pub` file),
  or leave it out to use the keys saved on the account.
- A tool error carries `status`, `code`, `message` and often `hint`. `api_key_scope` means the key
  is too weak for that tool: tell the user which scope to create; do not look for another way.

## What the server does not do

It has no shell on the GPUs: connect with `turbo ssh ID --batch -- COMMAND` or plain `ssh`. It
does not create or delete API keys, SSH keys, storage keys or webhooks: those belong to the user,
in the console. It does not call the hosted model: use `turbo-models-api`.
