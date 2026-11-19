# ExducerAI GPU cloud for coding agents

ExducerAI rents whole GPUs in Montréal by the hour. This repository holds what a coding agent
needs to use it: the setup text, the Claude Code plugin with six skills, and the MCP Registry
listing of the hosted MCP server.

The MCP server is a hosted service at `https://exducer.ai/mcp`. Its code is not in this
repository. The files here are copies of what [exducer.ai](https://exducer.ai/agents) serves to
agents. If a copy and the site ever differ, the site is right.

## Connect to the MCP server

Prices, availability and quotes need no key:

```bash
claude mcp add --transport http turbo https://exducer.ai/mcp
```

An API key opens the account tools: bookings, deployments, billing and usage. Create one at
https://cloud.exducer.ai (Account, then API keys). A sandbox key simulates everything and charges
nothing.

```bash
claude mcp add --transport http --scope user turbo https://exducer.ai/mcp \
  --header "Authorization: Bearer $TURBO_API_KEY"
```

Keep the key in your environment. Do not paste it into a chat and do not commit it.

The transport is streamable HTTP. In the MCP Registry the server is `ai.exducer/turbo`
([server.json](server.json)).

## Let your agent set itself up

Tell it: "Read https://exducer.ai/agents.md and set up ExducerAI." The same text is
[SETUP.md](SETUP.md).

## Claude Code plugin

```bash
claude plugin marketplace add https://exducer.ai/agents/marketplace.json
claude plugin install turbo@turbo-cloud
```

The catalog at the root of this repository (`.claude-plugin/marketplace.json`) is the same one.
The plugin's MCP server is `turbo mcp`, so it needs the CLI from step 1 of [SETUP.md](SETUP.md).

## Tools

The server has 22 tools; 18 of them only read.

| Tool | What it does | Effect |
| --- | --- | --- |
| `get_pricing` | List prices in CAD: GPU-hour per GPU model, object storage per GB-month, and the Models API. | Read-only |
| `check_availability` | One yes or no per GPU model: is it free right now. | Read-only |
| `get_service_status` | The public status of each service (console, API, GPU region, object storage, Models API). | Read-only |
| `list_servers` | The servers a booking can name: id (the server_id of quote_booking and create_booking), GPU model, price per GPU-hour in CAD, allowed_gpu_counts, region, and whether it is free now. | Read-only |
| `list_templates` | The templates a booking can name: slug, name, the container image it runs, category. | Read-only |
| `quote_booking` | What a booking would cost in CAD: GPU cost, tax and total for the whole duration, and the hourly rates. | Read-only |
| `search_docs` | Search the documentation by keyword. | Read-only |
| `read_doc` | One documentation page as Markdown, by its slug (from search_docs). | Read-only |
| `get_account` | The account behind the API key (email, company, type), whether the key is a sandbox key, and the prepaid balance in CAD (simulated under a sandbox key). | Read-only |
| `list_deployments` | Every deployment of the account with its state, GPU count, rate, cost so far and end time. | Read-only |
| `get_deployment` | One deployment in full: state and reason, SSH host and port, the host key fingerprint to verify, rate per GPU-hour, cost so far, start and end time, endpoints. | Read-only |
| `get_deployment_events` | The state changes of a deployment, oldest first, each with its reason, actor and time. | Read-only |
| `wait_for_deployment` | Poll a deployment until it reaches a state (default running) or a final state, for at most 50 seconds per call. | Read-only |
| `get_billing` | The prepaid balance and the most recent credit ledger lines (top-ups and charges) in CAD. | Read-only |
| `get_usage` | What the account was charged for GPU time, object storage and the Models API over a date range, in CAD before tax. | Read-only |
| `list_invoices` | The account's invoices (not available to a sandbox key). | Read-only |
| `list_ssh_keys` | The SSH public keys saved on the account: a booking with no ssh_public_key uses them (not available to a sandbox key). | Read-only |
| `get_storage_usage` | Object storage: GB stored, active keys, price per GB-month and the amount billed this month (not available to a sandbox key). | Read-only |
| `create_booking` | Send a GPU request. | Changes the account |
| `extend_deployment` | Add hours to the term of a deployment that is requested, queued, provisioning or running. | Changes the account |
| `set_auto_renew` | Turn automatic renewal of a deployment on or off. | Changes the account |
| `stop_deployment` | Stop a deployment now: billing ends at this minute and its container and NVMe scratch disk are deleted and cannot be recovered. | Changes the account, deletes data |

The 4 tools that change the account (`create_booking`, `extend_deployment`, `set_auto_renew`, `stop_deployment`) only act when called with `confirm: true`, after the person said yes to the cost or the deletion.

## What is in this repository

| Path | What it is |
| --- | --- |
| `server.json` | The listing published to the MCP Registry. |
| `SETUP.md` | The setup an agent follows, as served at https://exducer.ai/agents.md. |
| `.claude-plugin/marketplace.json` | The Claude Code plugin catalog. |
| `plugins/turbo/` | The plugin: its manifest, its MCP server entry and the six skills. |
| `plugins/turbo/skills/*/SKILL.md` | The skills, as served under https://exducer.ai/.well-known/agent-skills/. |

## Help

Documentation: https://exducer.ai/docs. Service status: https://exducer.ai/status.
Questions: hello@exducer.ai.
