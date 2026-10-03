# Subscription Killer

**PayPal AI Hackathon entry** — an AI agent that finds your forgotten recurring PayPal charges, explains each one in plain English, and kills the zombies with one tap.

Everyone bleeds money on subscriptions they forgot. Nobody wants to spend a Saturday auditing statements. This does it while you sleep.

## How it works

1. **Connect** — OAuth into PayPal (sandbox for the demo, production-ready flow).
2. **Scan** — Pull transaction history + active subscriptions via PayPal's REST APIs.
3. **Explain** — AI turns every recurring charge into plain English: what it is, what it costs, when it last hit, and a "zombie score" for how likely you forgot it.
4. **Kill** — One tap cancels through PayPal's Subscriptions API. Running tally of money saved.

## Quick start

```bash
cp .env.example .env
# fill in PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET from developer.paypal.com
pip install -r requirements.txt
uvicorn backend.main:app --reload
# open http://localhost:8000
```

## Project layout

- `backend/main.py` — FastAPI app + routes
- `backend/paypal_client.py` — PayPal REST wrapper (sandbox)
- `backend/ai_analyzer.py` — recurring-charge detection + AI explanations
- `frontend/index.html` — single-page dashboard, no build step

## Hackathon

- Devpost: paypalaihackathon.devpost.com
- Deadline: Nov 12, 2026, 2pm PT
- Requirement: meaningfully use both PayPal and AI. This does.
