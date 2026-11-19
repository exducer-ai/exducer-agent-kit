---
name: turbo-usage
description: "Read money on ExducerAI - prepaid balance, what a running deployment has cost so far, charges per day or per type, ledger lines, invoices and object storage usage, and what happens when credit runs out. Use when the user asks what they spent, what something costs, how long their credit lasts, why a deployment stopped, or wants a cost report."
---

# Balance, cost and usage

Everything here is read-only and needs a **read** key. All amounts are in CAD, including fields
whose names end in `_usd` or `Usd` (older names for the same values).

## Quick answers

| Question | CLI | MCP tool |
| --- | --- | --- |
| How much credit is left? | `turbo whoami --json` | `get_account` |
| What has this deployment cost? | `turbo deployment ID --json` (`accrued_cost`, `hourly_rate`) | `get_deployment` |
| What did I spend this month? | `turbo billing --json` | `get_usage` |
| Recent charges and top-ups | `turbo billing -n 50 --json` | `get_billing` |
| Invoices | `turbo invoices --json` | `list_invoices` |
| Object storage | `turbo storage usage` | `get_storage_usage` |
| What does it cost before I book? | `turbo quote ... --json` | `quote_booking` |
| List prices | `curl -s https://exducer.ai/api/v1/public/pricing` | `get_pricing` |

## How charging works

- **GPU time** is charged per GPU-hour, by the minute, from prepaid credit, only while a
  deployment is `running`. An idle running deployment still costs money. A request that has not
  started costs nothing.
- `hourly_rate` on a deployment is per GPU. The node rate is `hourly_rate` times `gpu_count`.
- **Object storage** is metered hourly per GB-month from the same credit.
- **The Models API** is charged per call from the same credit.
- Tax (GST and QST) applies to Canadian customers and shows in the quote.

## How long does the credit last?

```
hours_left = balance / (sum over running deployments of hourly_rate * gpu_count)
```

Take the balance from `get_account` and the rates from `list_deployments`, and tell the user when
the credit runs out at the current burn rate.

## When credit reaches zero

Running deployments are stopped and their containers and NVMe scratch disks are **deleted**.
Object storage keys are paused and the stored objects are kept. Warn the user well before that
point if the numbers above show it coming: the fix is a top-up on
https://cloud.exducer.ai/portal/billing, which only they can do.

## Usage report

`get_usage` (or `GET /api/billing/usage`) takes `from` and `to` as `YYYY-MM-DD` days in
America/Toronto time, and `group` as `day` (default) or `type`. Amounts are before tax. Only
deployments that actually ran appear.

## Why did my deployment stop?

Read its events: `turbo events ID --json` or `get_deployment_events`. The last row's `reason`
says it: the term ended, the user stopped it, credit ran out, the start failed, or the host was
unreachable (time without the host is not billed).
