# Register the MCP server in a coding agent

Two ways to reach the same tools. Pick one per agent.

## Through the CLI (stdio)

The key stays in `~/.config/turbo`, where `turbo login` stored it. It is not copied into the
agent's settings.

```bash
curl -sSL https://exducer.ai/cli/install.sh | sh
turbo login                                   # type the key here, not into a chat

claude mcp add --scope user turbo -- turbo mcp
codex mcp add turbo -- turbo mcp
```

For an agent that reads a JSON file of MCP servers:

```json
{ "mcpServers": { "turbo": { "command": "turbo", "args": ["mcp"] } } }
```

`turbo agent setup` does all of this for every coding agent it finds on the machine, and installs
the skills too. `turbo agent setup --dry-run` prints the changes first; `turbo agent remove` undoes
them.

## The hosted server (streamable HTTP)

Without a key, the public tools answer:

```bash
claude mcp add --transport http turbo https://exducer.ai/mcp
```

With a key as a header:

```bash
claude mcp add --transport http --scope user turbo https://exducer.ai/mcp \
  --header "Authorization: Bearer $TURBO_API_KEY"
```

The server answers in JSON and keeps no session. The key is forwarded to the API and never stored.

## Which key opens which tools

| Key | Tools |
| --- | --- |
| None | `get_pricing`, `check_availability`, `get_service_status`, `list_servers`, `list_templates`, `quote_booking`, `search_docs`, `read_doc` |
| Read | `get_account`, `list_deployments`, `get_deployment`, `get_deployment_events`, `wait_for_deployment`, `get_billing`, `get_usage`, `list_invoices`, `list_ssh_keys`, `get_storage_usage` |
| Write, each call with `confirm: true` | `create_booking`, `extend_deployment`, `set_auto_renew`, `stop_deployment` |

A read key is enough for an agent that only reports. Give it a write key when it should book and
stop. It never needs an admin key.

Start a new session of the agent after registering: tools and skills load when it starts.

Source: https://exducer.ai/docs/getting-started/gs-agents
