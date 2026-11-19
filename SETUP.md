# Set up ExducerAI in a coding agent

You are a coding agent (Claude Code, Codex, Cursor or another) and a person asked you to set up
ExducerAI. Follow these steps in order. Run the commands yourself; ask the person only where a step
says so. Stop and report if a step fails twice.

ExducerAI rents whole GPUs in Montréal by the hour and serves an OpenAI-compatible Models API. After
this setup you can check availability, quote, book, wait for, connect to and stop GPU deployments
for the person, with their approval at every step that costs money.

## 1. Install the CLI

Needs Python 3.9 or newer and `curl`. Nothing else is installed.

```bash
curl -sSL https://exducer.ai/cli/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
turbo --version
```

## 2. Get an API key from the person

Ask them, in these words or close to them:

> I need a ExducerAI API key. Open https://cloud.exducer.ai, go to Account, then API keys, and
> create one. A **sandbox key** is the safe start: everything is simulated and nothing is charged.
> For real GPUs, create a key with the **write** scope. Then run `turbo login` in a terminal and
> paste the key there. Please do not paste the key into this chat.

Do not ask for the key in the conversation, do not write it to any file in the project, and do
not echo it. If the person already exported `TURBO_API_KEY`, that works too.

Check it:

```bash
turbo whoami --json
```

## 3. Install the skills and the MCP server

```bash
turbo agent setup
```

This copies the ExducerAI skills into the skills folder of each coding agent found on this machine
and registers the MCP server (`turbo mcp`, which reads the key the CLI stored). It prints what it
did. Add `--dry-run` first if the person wants to see the changes before they are made.

If you cannot run it, register the hosted server by hand instead:

```bash
claude mcp add --transport http --scope user turbo https://exducer.ai/mcp \
  --header "Authorization: Bearer $TURBO_API_KEY"
```

In Claude Code, the skills and the server also install as a plugin. Use it instead of
`turbo agent setup`, not as well as it, or every skill is listed twice:

```bash
claude plugin marketplace add https://exducer.ai/agents/marketplace.json
claude plugin install turbo@turbo-cloud
```

The skills are also served at https://exducer.ai/.well-known/agent-skills/index.json.

## 4. Verify

```bash
turbo agent status
turbo availability --json
turbo servers --json
```

Then tell the person:

- what was installed and where;
- whether the key is a sandbox key or a live key, and its scope if a command told you;
- that the skills and the MCP tools load in a **new** session of the agent;
- one thing they can ask next, for example: "Rehearse a GPU booking on the sandbox."

## Rules that apply from now on

1. Never book, extend or turn on renewal without showing the quote and getting an explicit yes.
2. Never stop a deployment without a yes: stopping deletes its container and its disk.
3. Read prices and availability from the CLI or the tools, never from memory. Amounts are in CAD.
4. A booking is a request that starts later. Wait for it; never book twice.
5. Keep the key out of the chat, the repository and the logs.

More: https://exducer.ai/llms.txt (documentation index for agents) and https://exducer.ai/agents
(this setup, for people).
