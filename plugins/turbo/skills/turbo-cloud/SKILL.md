---
name: turbo-cloud
description: "Start here for anything on ExducerAI, a Canadian GPU cloud (whole RTX PRO 6000 Blackwell GPUs in Montréal, rented by the hour, plus an OpenAI-compatible Models API). Explains what the platform offers and does not offer, the rules that keep the user's money and data safe, and which of the other turbo-* skills to load for booking GPUs, the CLI, the MCP server, billing or the Models API."
---

# ExducerAI: what it is and how an agent works with it

ExducerAI rents whole GPUs on bare metal in Montréal, Québec (region `CA-QC`). You reach a rental
over SSH as root inside a container. There is also a hosted Models API (preview, OpenAI-compatible).

Use this skill to orient yourself, then load the skill for the job:

| Job | Skill |
| --- | --- |
| Rent GPUs, wait for them, run a workload, stop | `turbo-deploy` |
| Command reference for the `turbo` CLI | `turbo-cli` |
| The tools of the MCP server, and how to register it | `turbo-mcp` |
| Balance, cost so far, usage reports, invoices | `turbo-usage` |
| Call the hosted model with an OpenAI client | `turbo-models-api` |

## Two ways to act

- **The `turbo` CLI** (single Python file, no dependencies). Every command takes `--json`.
  Install: `curl -sSL https://exducer.ai/cli/install.sh | sh`
- **The MCP server** at `https://exducer.ai/mcp` (or `turbo mcp` over stdio). Same API, as tools.

Both use one API key. Prefer the MCP tools when they are registered in this session; otherwise use
the CLI. Do not call the REST API by hand unless neither covers the need
(reference: https://exducer.ai/docs/compute/c-api-reference.md).

## Facts to rely on

- **Live data beats memory.** Prices, GPU models, allowed GPU counts and templates change. Read them
  from `turbo servers --json`, `turbo templates --json` and
  `https://exducer.ai/api/v1/public/pricing`. Never quote a price from this file or from memory.
- **Currency is CAD.** Every amount is in Canadian dollars, including the older fields whose names
  end in `_usd` or `Usd`.
- **GPUs come per node.** A booking asks for the GPU counts the server allows
  (`allowed_gpu_counts` in `turbo servers --json`), not for a single GPU.
- **A booking is a request, not an instant start.** It is created as `requested` or `queued` and
  becomes `running` later, sometimes after staff place it. Never assume it is running: wait for it.
- **Billing is per minute, from prepaid credit, only while the deployment runs.** Nothing is
  charged for a request that has not started.
- **Stopping deletes data.** A stop ends billing and deletes the container and its NVMe scratch
  disk. Nothing on that disk can be recovered. Copy results off first.
- **Access is SSH only**, with the user's public key. There is no web terminal.
- **Sandbox keys exist.** A key that starts with `tml_test_` runs the same commands against a
  simulated lifecycle: nothing is charged and no machine is involved.

## Not offered (do not promise or plan around these)

Spot pricing, autoscaling, serverless endpoints, multiple regions, Slurm, a service-level
agreement, and NVLink or InfiniBand between the RTX GPUs. B200 and B300 are reserved through
sales, not through the API.

## Rules for an agent

1. **Never spend without a yes.** Before any booking or extension on a live key, show the user the
   quote (`turbo quote`, or the `quote_booking` tool) and get an explicit approval of the total.
2. **Rehearse on the sandbox.** If the user has a sandbox key, run the whole flow there first.
3. **Make spending retry-safe.** Pass an idempotency key on every booking and extension, and reuse
   the same key when you retry the same request.
4. **Never stop a deployment without a yes**, and say first that its disk is deleted.
5. **Do not handle the key in chat.** Ask the user to run `turbo login` themselves or to set
   `TURBO_API_KEY`. Never print a key, write it to a file in the repository, or put it in a commit.
6. **Leave credentials alone.** Creating or deleting API keys, SSH keys, storage keys and webhooks
   needs an admin key and belongs to the user, in the console.
7. **Say what you did.** After acting, report the deployment id, its state, its hourly rate and
   when it ends.

## When something fails

- `401`: the key is missing, revoked, or belongs to the other environment.
- `403 api_key_scope`: the key's scope is too low. Read keys cannot book or stop; credentials need
  admin. Tell the user which scope is needed; do not try to work around it.
- `403 sandbox_boundary`: a sandbox key touched something live. Expected; use a live key only if
  the user wants real GPUs.
- `402` or `pending_payment`: prepaid credit does not cover it. The user tops up on
  https://cloud.exducer.ai/portal/billing.
- Every error code is listed at `https://api.exducer.ai/api/v1/public/errors`.
- Docs index for agents: https://exducer.ai/llms.txt (each page is also served as Markdown: add
  `.md` to its URL). Human help: hello@exducer.ai.
