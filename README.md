# ExducerAI GPU cloud for coding agents

ExducerAI rents whole GPUs in Montréal by the hour and serves an OpenAI-compatible Models API.
This repository is the kit that lets a coding agent use it for you: check availability, quote,
book, wait, connect over SSH, stop, and read billing, with your approval at every step that costs
money.

| | |
| --- | --- |
| MCP server | `https://exducer.ai/mcp` (streamable HTTP), `ai.exducer/turbo` in the MCP Registry |
| CLI | `turbo`, one Python file: `curl -sSL https://exducer.ai/cli/install.sh \| sh` |
| Skills | Six agent skills, also packaged as a Claude Code plugin |
| Documentation | https://exducer.ai/docs, and https://exducer.ai/llms.txt for agents |

The MCP server and the API are hosted services. Their code is not in this repository. The setup
text, the skills and the CLI here are copies of what [exducer.ai](https://exducer.ai/agents) serves;
if a copy and the site ever differ, the site is right (`sh scripts/check-against-site.sh` compares).

## Set up with one prompt

Paste this into Claude Code, Codex, Cursor or another coding agent:

```
Read https://exducer.ai/agents.md and set up ExducerAI.
```

The agent installs the CLI, asks you to create an API key and to type it into `turbo login`
yourself, then installs the skills and registers the MCP server. The steps it follows are in
[SETUP.md](SETUP.md).

Start with a **sandbox key** (https://cloud.exducer.ai, Account, then API keys, with the Sandbox
key option). It runs the same commands against a simulated lifecycle, so the agent can rehearse a
booking from request to stop and nothing is charged.

## Set up by hand

```bash
curl -sSL https://exducer.ai/cli/install.sh | sh   # one Python 3 file, no dependencies
turbo login                                          # type the key here, not into a chat
turbo agent setup                                    # skills and MCP server, for the agents on this machine
turbo agent status                                   # what is installed where
```

`turbo agent setup --dry-run` prints the changes without making them, and `turbo agent remove`
undoes them. More in [cli/README.md](cli/README.md).

In Claude Code the skills and the server also install as a plugin. Use it instead of
`turbo agent setup`, not as well as it:

```bash
claude plugin marketplace add https://exducer.ai/agents/marketplace.json
claude plugin install turbo@turbo-cloud
```

## The MCP server only

No key is needed for prices, availability, the catalog, quotes and the documentation:

```bash
claude mcp add --transport http turbo https://exducer.ai/mcp
```

With a key, the account tools answer too:

```bash
claude mcp add --transport http --scope user turbo https://exducer.ai/mcp \
  --header "Authorization: Bearer $TURBO_API_KEY"
```

Other agents and the stdio route through the CLI are in
[examples/mcp/clients.md](examples/mcp/clients.md).

## What the agent may do without you

These rules are enforced by the server and the CLI, so they hold whatever the agent was told.

- Reading is open within the key's scope: availability, prices, quotes, your deployments and their
  events, the cost so far, your balance and usage.
- `create_booking`, `extend_deployment`, `set_auto_renew` and `stop_deployment` refuse unless the
  call carries `confirm: true`. The skills tell the agent to set it only after you approved the
  quote or, for a stop, after you were told the disk is deleted.
- Every booking and extension carries an idempotency key, so a retried call replays the first
  answer instead of booking twice.
- API keys, SSH keys, storage keys and webhooks cannot be changed through the MCP server. They stay
  with you, in the console.

A read key is enough for an agent that only reports. Give it a write key when it should book and
stop. It never needs an admin key.

## Tools

The server has 22 tools. The "Key" column is the least key a tool needs.

| Tool | Key | What it does |
| --- | --- | --- |
| `get_pricing` | None | List prices in CAD: GPU-hour per GPU model, object storage per GB-month, and the Models API. |
| `check_availability` | None | One yes or no per GPU model: is it free right now. |
| `get_service_status` | None | The public status of each service (console, API, GPU region, object storage, Models API). |
| `list_servers` | None | The servers a booking can name: id (the server_id of quote_booking and create_booking), GPU model, price per GPU-hour in CAD, allowed_gpu_counts, region, and whether it is free now. |
| `list_templates` | None | The templates a booking can name: slug, name, the container image it runs, category. |
| `quote_booking` | None | What a booking would cost in CAD: GPU cost, tax and total for the whole duration, and the hourly rates. |
| `search_docs` | None | Search the documentation by keyword. |
| `read_doc` | None | One documentation page as Markdown, by its slug (from search_docs). |
| `get_account` | Read | The account behind the API key (email, company, type), whether the key is a sandbox key, and the prepaid balance in CAD (simulated under a sandbox key). |
| `list_deployments` | Read | Every deployment of the account with its state, GPU count, rate, cost so far and end time. |
| `get_deployment` | Read | One deployment in full: state and reason, SSH host and port, the host key fingerprint to verify, rate per GPU-hour, cost so far, start and end time, endpoints. |
| `get_deployment_events` | Read | The state changes of a deployment, oldest first, each with its reason, actor and time. |
| `wait_for_deployment` | Read | Poll a deployment until it reaches a state (default running) or a final state, for at most 50 seconds per call. |
| `get_billing` | Read | The prepaid balance and the most recent credit ledger lines (top-ups and charges) in CAD. |
| `get_usage` | Read | What the account was charged for GPU time, object storage and the Models API over a date range, in CAD before tax. |
| `list_invoices` | Read | The account's invoices (not available to a sandbox key). |
| `list_ssh_keys` | Read | The SSH public keys saved on the account: a booking with no ssh_public_key uses them (not available to a sandbox key). |
| `get_storage_usage` | Read | Object storage: GB stored, active keys, price per GB-month and the amount billed this month (not available to a sandbox key). |
| `create_booking` | Write | Send a GPU request. |
| `extend_deployment` | Write | Add hours to the term of a deployment that is requested, queued, provisioning or running. |
| `set_auto_renew` | Write | Turn automatic renewal of a deployment on or off. |
| `stop_deployment` | Write | Stop a deployment now: billing ends at this minute and its container and NVMe scratch disk are deleted and cannot be recovered. |

## Examples

[examples/](examples/README.md) has small, complete examples: the public API and the MCP server
with no key at all, webhook signature checks in Python and Node.js, a simulated booking on the
sandbox with the CLI and with the REST API, and the Models API.

## In this repository

| Path | What it is |
| --- | --- |
| [`SETUP.md`](SETUP.md) | The setup an agent follows, as served at https://exducer.ai/agents.md |
| [`plugins/turbo/skills/`](plugins/turbo/skills) | The six skills, as listed at https://exducer.ai/.well-known/agent-skills/index.json |
| [`plugins/turbo/`](plugins/turbo), [`.claude-plugin/`](.claude-plugin) | The Claude Code plugin and its catalog |
| [`cli/`](cli/README.md) | The `turbo` CLI, as served at https://exducer.ai/cli/turbo.py |
| [`examples/`](examples/README.md) | Examples for the API, the MCP server, webhooks, the CLI and the Models API |
| [`server.json`](server.json) | The listing published to the MCP Registry |
| [`scripts/check-against-site.sh`](scripts/check-against-site.sh) | Compares the copies here with the site |
| [`SECURITY.md`](SECURITY.md), [`CHANGELOG.md`](CHANGELOG.md) | How to report a security problem; what changed |

## Help

- Documentation: https://exducer.ai/docs
- Service status: https://exducer.ai/status
- Questions: hello@exducer.ai
- Security: security@exducer.ai ([SECURITY.md](SECURITY.md))
