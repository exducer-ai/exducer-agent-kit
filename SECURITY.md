# Security

## Reporting a problem

If you think you found a security problem in the hosted MCP server (`https://exducer.ai/mcp`), the
API, the CLI or a file in this repository, write to **security@exducer.ai**.

Please do not open a public issue for it, and do not include API keys, SSH private keys or customer
data in a report.

## How the kit handles keys

- The hosted MCP server keeps no session. An API key travels as a Bearer header, is forwarded to
  the API and is never stored.
- `turbo login` stores the key under `~/.config/turbo` on your machine. `turbo agent setup`
  registers the MCP server as the command `turbo mcp`, which reads that file: the key is not copied
  into the agent's settings.
- The four tools that change an account (`create_booking`, `extend_deployment`, `set_auto_renew`,
  `stop_deployment`) refuse a call without `confirm: true`. API keys, SSH keys, storage keys and
  webhooks cannot be changed through the MCP server.
- A sandbox key reaches simulated objects only. A read key cannot book or stop.

## If a key leaks

Delete it in the console (https://cloud.exducer.ai, Account, then API keys) and create a new one.
