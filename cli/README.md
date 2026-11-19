# The turbo CLI

One Python file with no dependency (Python 3.9 or newer). The same file the site serves at
https://exducer.ai/cli/turbo.py; the installer below always fetches the current one from the site.

## Install

```bash
curl -sSL https://exducer.ai/cli/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
turbo --version
```

## Sign in

```bash
turbo login        # type an API key from https://cloud.exducer.ai (Account, then API keys)
turbo whoami
```

Or export `TURBO_API_KEY`. A sandbox key is the safe start: everything is simulated and nothing is
charged. Do not paste a key into a chat and do not commit one.

## A booking from quote to stop

```bash
turbo availability                                        # is each GPU model free right now
turbo servers                                             # the ids `book` accepts
turbo quote --server rtx-pro-6000 --gpus 8 --hours 24     # the price, tax included; books nothing
turbo book  --server rtx-pro-6000 --gpus 8 --hours 24 --ssh-key ~/.ssh/id_ed25519.pub
turbo wait <id> --until running                           # exit 0 running, 3 ended otherwise, 4 timed out
turbo ssh <id> -- nvidia-smi                              # run one command there, or omit it for a shell
turbo stop <id>                                           # billing ends; the container and scratch disk are deleted
```

`turbo book`, `turbo extend` and `turbo stop` ask for confirmation and exit with code 2 when nobody
can answer; a script passes `--yes`. Every command takes `--json`.

## Commands

| Command | What it does |
| --- | --- |
| `login`, `logout`, `whoami` | Store or forget an API key; show the account, balance and API in use |
| `availability` | Is each GPU model free right now (yes or no) |
| `servers`, `templates` | The servers and templates a booking can name |
| `quote` | The price of a booking, tax included; books nothing and needs no key |
| `book` | Request GPUs (quote, confirm, send) |
| `deployments`, `deployment`, `events` | Your deployments, one in detail, its state transitions |
| `wait` | Block until a deployment reaches a state |
| `ssh` | SSH into a running deployment, or run one command there |
| `extend`, `renew` | Run a deployment longer; renew it automatically at the end of its term |
| `stop` | Stop a deployment now, or withdraw a request |
| `ssh-keys`, `webhooks`, `storage` | SSH keys, webhook endpoints, object storage keys and usage |
| `billing`, `invoices` | Prepaid balance and ledger; invoices |
| `chat` | Ask the hosted model |
| `status` | Public service status |
| `mcp` | Serve the MCP tools over stdio for a coding agent |
| `agent` | Set up coding agents: install the skills and register the MCP server (`setup`, `status`, `remove`) |

`turbo <command> -h` lists the options of each.

## For coding agents

```bash
turbo agent setup --dry-run     # what would change
turbo agent setup               # skills and MCP server, for the agents found on this machine
turbo agent status
turbo agent remove
```

This copy is version 0.3.0.
