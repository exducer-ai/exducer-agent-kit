---
name: turbo-deploy
description: "Rent GPUs on ExducerAI and run a workload on them, end to end - check availability, quote, book with an idempotency key, wait until the deployment runs, connect over SSH with a verified host key, run the job, copy results off, and stop. Use when the user asks to get a GPU, start a training or inference run, launch a node, or shut one down. Covers the sandbox rehearsal and every state a deployment goes through."
---

# Rent GPUs and run a workload

Read `turbo-cloud` first if you have not: it holds the rules (never spend or stop without a yes).

The examples use the `turbo` CLI. The MCP tools named in brackets do the same thing.

## 0. Check the setup

```bash
turbo whoami --json          # account, balance, which API           [get_account]
```

- No key: ask the user to run `turbo login` (key from https://cloud.exducer.ai, Account, API
  keys) or to export `TURBO_API_KEY`. Booking and stopping need a **write** key.
- A key that starts with `tml_test_` is a sandbox key: everything below is simulated and free.
  Use it to rehearse.

## 1. Look before you book

```bash
turbo availability --json    # one yes/no per GPU model               [check_availability]
turbo servers --json         # server id, price, allowed GPU counts   [list_servers]
turbo templates --json       # template slugs and the image each runs [list_templates]
```

Pick the server `id`, a GPU count from that server's `allowed_gpu_counts`, and a template slug
(omit it for the default PyTorch image). "Not available now" does not block a request: it is
queued or placed when capacity frees up.

## 2. Quote, then get a yes

```bash
turbo quote --server SERVER_ID --gpus 8 --hours 24 --json            # [quote_booking]
```

Show the user the total, the hourly rate and the duration, in CAD, and wait for an explicit yes.
A live booking has a minimum duration (the API answers `400 duration_below_minimum` if you are
under it; a day is typical). The sandbox accepts one hour.

## 3. Book, retry-safe

The deployment is reached over SSH only, so a public key is required: pass `--ssh-key`, or rely on
a key already saved on the account (`turbo ssh-keys --json`).

```bash
turbo book --server SERVER_ID --gpus 8 --hours 24 \
  --template pytorch-2.8-cuda12.8 \
  --ssh-key ~/.ssh/id_ed25519.pub \
  --idempotency-key "job-$(date +%Y%m%d)-train-1" \
  --yes --json                                                        # [create_booking]
```

- `--yes` is required when no person is at the terminal; without it the CLI refuses rather than
  hang on a prompt.
- Reuse the **same** `--idempotency-key` if you retry after a timeout or an error: the API replays
  the first answer instead of booking twice. Use a new key only for a genuinely new booking.
- The answer holds `booking.id` (starts with `rnt_`, or `snd_` in the sandbox) and its `status`.
- `"replayed": true` means the API returned the answer to an earlier use of that key: nothing new
  was booked. Check that deployment's current state before going on.
- `pending_payment` means the prepaid credit does not cover it. Nothing was charged and nothing
  will start: the user tops up, then you book again with a new key.

## 4. Wait until it runs

```bash
turbo wait DEPLOYMENT_ID --until running --timeout 1800 --json        # [wait_for_deployment]
```

States: `requested` (waiting for staff to place it), `queued`, `provisioning`, `running`, then
`stopped`, `ended`, `failed` or `cancelled`. Exit code 0 means running; 3 means it ended some
other way (read `turbo events ID --json` for the reason); 4 means the timeout passed and it is
still on its way.

A live request can stay `requested` for a while, because a person places it and emails a start
time. Do not poll in a tight loop and do not book again. Tell the user it is requested, then
check back later or stop here.

## 5. Connect and run

```bash
turbo ssh DEPLOYMENT_ID --batch -- nvidia-smi
turbo ssh DEPLOYMENT_ID --batch -- 'mkdir -p /root/work && cd /root/work && nohup python train.py > train.log 2>&1 &'
turbo ssh DEPLOYMENT_ID --batch -- tail -n 20 /root/work/train.log
```

- `--batch` never prompts. It checks the host key against the fingerprint the API publishes and
  refuses to connect if they differ.
- You are root in a container whose disk is the node's NVMe scratch (fast, and deleted at the
  end). `/root/work` is only an example path. Use `tmux` or `nohup` for anything long: an SSH
  session ending must not kill the job.
- For `scp` or `rsync`, take the host and port from `turbo deployment ID --json`
  (`ssh_host`, `ssh_port`).
- A sandbox deployment has no SSH endpoint. Stop the rehearsal here.

## 6. Keep it alive or let it end

- It ends by itself at `ends_at`. Check `turbo deployment ID --json` for the time left.
- Longer: `turbo extend ID --hours N --idempotency-key KEY --yes` [extend_deployment], after the
  user agrees to the extra cost. At most 720 hours ahead.
- Automatic renewal: `turbo renew ID on --hours N` [set_auto_renew], also only with a yes.

## 7. Save results, then stop

The disk is deleted at stop **and** at the end of the term. Before either:

```bash
rsync -az -e "ssh -p PORT" root@HOST:/root/work/out/ ./out/
# or push to object storage from inside the deployment:
# https://exducer.ai/docs/getting-started/gs-storage.md
```

Then, only after the user confirms and knows the disk goes with it:

```bash
turbo stop DEPLOYMENT_ID --yes --json                                 # [stop_deployment]
```

Billing ends at that minute. Stopping a request that has not started withdraws it at no cost.

## 8. Report

Tell the user: the deployment id, its final state, what it cost
(`accrued_cost` in `turbo deployment ID --json`) and where the results are.

## Rehearse failure on the sandbox

With a sandbox key, `turbo book ... --scenario NAME --speed 10` simulates what an integration must
survive: `busy` (a dated request), `fail_start`, `host_unreachable`, `insufficient_credit`,
`capacity_timeout`, `slow_start`. `--speed` (1 to 60) shortens every wait.
