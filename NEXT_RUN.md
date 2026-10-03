# Subscription Killer — next live sandbox run

Prepared 2026-10-02 after the Sandbox credential step was completed.
Do these steps on your own machine, in order. Never paste the Client
Secret (or the access token) into chat.

## 0. What was fixed before this run (already done locally)

- `backend/paypal_client.py` — `list_subscriptions()` now reads the
  `subscriptions` array PayPal actually returns (it previously read a
  non-existent `subscription_collection` key and would always show
  zero subscriptions).
- `backend/paypal_client.py` — Transaction Search dates now send
  RFC 3339 UTC (`2026-10-01T00:00:00Z`) instead of `+0000`.
- `backend/main.py` + `backend/paypal_client.py` — `.env` is now
  actually loaded (`python-dotenv` was installed but never called).
- Mock-verified 2026-10-02 (no live credentials): list parsing,
  date formatting, and `GET /api/health` -> 200 all pass.

## 1. Put the credentials where the app reads them

In `subscription-killer/`:

```
copy .env.example .env
```

Edit `.env` locally and fill in `PAYPAL_CLIENT_ID` and
`PAYPAL_CLIENT_SECRET` from the Sandbox app you configured today.
Keep `PAYPAL_SANDBOX=true`. Do not commit or share this file.

## 2. Boot and health-check

```
.venv\Scripts\activate
uvicorn backend.main:app --reload
```

Open `http://localhost:8000/api/health` — expect `{"ok": true}`.

## 3. Seed one sandbox subscription (so the demo is not $0)

With the app stopped or in a second terminal:

```
.venv\Scripts\python seed_sandbox.py
```

It creates a demo product + $9.99/month plan + subscription and
prints an approve URL. Open that URL logged in as your sandbox
PERSONAL (buyer) account at sandbox.paypal.com and approve it.

The seed script refuses to run if `PAYPAL_SANDBOX` is not `true`,
and never prints your secret or token.

## 4. Prove the loop

1. Refresh `http://localhost:8000` and click **Connect PayPal (sandbox)**.
2. The seeded subscription should appear; total monthly burn should
   include $9.99.
3. Click **Kill it** — this calls
   `POST /api/subscriptions/{id}/cancel` (PayPal returns 204).
4. Re-run the dashboard scan: the cancelled subscription should no
   longer be listed as ACTIVE.

If step 2 shows zero: check the token scope in the PayPal app
(Subscriptions must be enabled — a 403 usually means the app lacks
that product permission, not bad credentials).

## Deadline note

PayPal AI Hackathon deadline in this project: **Nov 12, 2026, 2pm PT**
(README). Star Keeper deadline is Nov 18 — keep this lane to this
one run + demo recording until Star Keeper Gate 1/Quest build is done.
