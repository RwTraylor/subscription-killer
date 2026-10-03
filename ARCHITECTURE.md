# Architecture — the clean fast approach

## Stack (boring on purpose)

- **Backend:** Python + FastAPI. One process, no build step, judges can run it from the README.
- **Frontend:** Vanilla JS single page served by FastAPI. No npm, no bundler, nothing to break in judging.
- **PayPal:** Direct REST calls with `httpx` (fewer dependency surprises than the SDK). Sandbox base URL swapped by env var.
- **AI:** Pluggable analyzer. Default path calls an LLM for plain-English summaries + zombie scoring; a deterministic heuristic fallback guarantees the demo works even with no AI key.

## Data flow

```
OAuth (PayPal sandbox)
  → Transaction Search API (12 months of history)
  → Subscriptions API (currently active subscriptions)
  → Recurring-charge detector (same merchant + amount + cadence)
  → AI analyzer: { plain_english, monthly_cost, last_charge, zombie_score, reason }
  → Dashboard: total monthly burn, ranked zombie list
  → One-tap cancel → Subscriptions API (suspend/cancel)
  → "Money saved" counter
```

## Why this maps to the judging criteria

- **Technological Implementation:** Real PayPal REST integration (OAuth, transaction search, subscription lifecycle) + real AI categorization. Not a wrapper.
- **Design:** One screen, one job. Connect → see the burn → kill the zombies.
- **Potential Impact:** The average person holds 5+ forgotten subscriptions. Universal, daily, invisible.
- **Innovation:** The zombie score — AI inferring "you forgot this" from charge patterns and merchant identity.
- **Presentation:** The demo writes itself: scan → "$X/month found" → kill → counter goes up. Under 3 minutes easily.

## What's stubbed (filled in overnight)

- `paypal_client.py` — exact endpoints/scopes land when the API research completes.
- `ai_analyzer.py` — heuristic fallback is real; LLM prompt layer gets tuned against sample data.
