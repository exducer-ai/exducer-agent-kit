---
name: turbo-cli
description: "Command reference for `turbo`, the ExducerAI command-line client, written for agents - install, authenticate, JSON output, non-interactive flags, exit codes, and every command (availability, servers, templates, quote, book, wait, deployment, events, ssh, extend, renew, stop, billing, storage, chat, mcp, agent setup). Use whenever you are about to run a turbo command or need to know which command does a job."
---

# The `turbo` CLI

One Python 3.9+ file with no dependencies.

```bash
curl -sSL https://exducer.ai/cli/install.sh | sh     # installs ~/.local/bin/turbo
turbo --version
```

## Authentication

- `turbo login` stores a key in `~/.config/turbo/config.json` (mode 600). It prompts for the key,
  so the **user** runs it. Or the user exports `TURBO_API_KEY`.
- Keys come from https://cloud.exducer.ai (Account, API keys) and start with `tml_`.
  `tml_test_` keys are sandbox keys.
- Scopes: **read** lists things; **write** books, stops, extends and calls the model; **admin**
  changes credentials. A command that needs more answers with the scope to ask for.
- `TURBO_API` overrides the API base (default `https://api.exducer.ai`).

## Rules for running it without a person

- Add `--json` to every command and parse the output. Tables are for people.
- Commands that spend or delete (`book`, `extend`, `stop`) ask for confirmation. With no terminal
  attached they **refuse** (exit code 2) unless you pass `--yes`. Pass it only after the user
  agreed.
- Errors go to stderr as `turbo: message`. Exit codes: `0` success, `1` error (API, network,
  bad input), `2` confirmation needed, `3` and `4` only from `turbo wait` (see below).
- Send `--idempotency-key` on `book` and `extend`, and reuse it on a retry.

## Commands

| Command | What it does | Key |
| --- | --- | --- |
| `turbo whoami` | Account, prepaid balance, API in use | read |
| `turbo status` | Public service status | none |
| `turbo availability` | Is each GPU model free right now (yes or no) | none |
| `turbo servers` | Bookable servers: id, price, allowed GPU counts | none |
| `turbo templates [--category C]` | Templates and the image each runs | none |
| `turbo quote --server ID [--gpus N] [--hours H]` | Price of a booking, tax included. Books nothing | none |
| `turbo book --server ID [--gpus N] [--hours H] [--template SLUG] [--ssh-key PATH] [--idempotency-key K] [--client-reference R] [--notes T] --yes` | Send a GPU request. `--json` prints `{"quote": ..., "booking": ...}` | write |
| `turbo deployments` | All deployments (sandbox rows are marked) | read |
| `turbo deployment ID` | One deployment: state, SSH host and port, rate, cost so far, end time | read |
| `turbo events ID` | Its state changes with reasons | read |
| `turbo wait ID [--until STATE] [--timeout S] [--interval S]` | Block until the state is reached. Exit 0 reached, 3 ended otherwise, 4 timed out | read |
| `turbo ssh ID [--batch] [-- COMMAND]` | SSH in, or run one command. `--batch` never prompts and verifies the host key | read |
| `turbo extend ID --hours N [--idempotency-key K] --yes` | Run longer | write |
| `turbo renew ID on` / `turbo renew ID off` `[--hours N]` | Automatic renewal at the end of the term | write |
| `turbo stop ID --yes` | Stop now (deletes the container and its disk), or withdraw a request | write |
| `turbo billing [-n N]` | Balance and the last ledger lines | read |
| `turbo invoices` | Invoices | read |
| `turbo storage usage` / `turbo storage keys` | Object storage usage and keys | read |
| `turbo ssh-keys [list]` | SSH keys saved on the account | read |
| `turbo chat "PROMPT" [--max-tokens N]` | One call to the hosted model (billed) | write |
| `turbo mcp` | Run the MCP server over stdio for an agent | as the tools need |
| `turbo agent setup` | Install these skills and register the MCP server for the coding agents found on this machine | none |
| `turbo agent status` | What is installed where | none |

Credential commands (`ssh-keys add|remove`, `storage create|revoke`, `webhooks add|remove|rotate`)
need an admin key. Leave them to the user unless they ask for exactly that.

## Sandbox extras

With a `tml_test_` key, `turbo book` also takes `--scenario` (`immediate`, `busy`, `fail_start`,
`host_unreachable`, `insufficient_credit`, `capacity_timeout`, `slow_start`,
`marketplace_release`) and `--speed` (1 to 60, shortens the simulated waits).
`turbo ssh` refuses a sandbox deployment: there is no machine behind it.

## Patterns

```bash
# the id of every running deployment
turbo deployments --json | python3 -c 'import json,sys; print(*[d["id"] for d in json.load(sys.stdin) if d.get("status")=="running"])'

# cost so far and time of end for one deployment
turbo deployment rnt_xxxxxxxx --json | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["accrued_cost"], d["currency"], d["ends_at"])'
```

For the full workflow (quote, book, wait, connect, stop) load `turbo-deploy`.
