# Subscription Killer — PayPal AI Hackathon Devpost Draft (2026-10-03)

Status: DRAFT ONLY. Deadline on file: Nov 12, 2026, 2:00 PM PT (README / NEXT_RUN). Product at 93% per Ricket, 2026-10-03, then live loop proven later that day.
Proven: app boots and serves dashboard + /api/health 200; PayPal sandbox credentials accepted; $9.99/mo demo subscription verified ACTIVE on API; app scan showed it with plain-English verdict; one-tap cancel succeeded and rescan came back empty; API confirms CANCELLED. Full detect -> explain -> kill loop proven 2026-10-03 (see ~/MEMORY.md).
Remaining to Nov 12: public GitHub repo + demo video under 3 minutes.

## Name
Subscription Killer

## Tagline
Find the subscriptions you forgot. Kill them in one tap.

## Inspiration
Everyone bleeds money on recurring charges they stopped using months ago. Auditing statements is a chore nobody schedules. We wanted an agent that does the audit while you sleep, explains each charge like a person, and lets you cancel without hunting through settings.

## What it does
1. Connect PayPal (sandbox in the demo).
2. Scan transaction history and active subscriptions via PayPal REST APIs.
3. Explain: AI turns each recurring charge into plain English — what it is, monthly burn, last hit, and a zombie score for how likely you forgot it.
4. Kill: one tap cancels through the PayPal Subscriptions API and updates your saved-money tally.

## How we built it
FastAPI backend (backend/main.py), PayPal REST wrapper (backend/paypal_client.py), AI analyzer for recurring detection and explanations (backend/ai_analyzer.py), single-page dashboard (frontend/index.html). Sandbox-first: seed_sandbox.py creates a $9.99/month demo product/plan/subscription and prints a buyer approve URL, with a sandbox-only guard and no secrets printed.

Fixes already landed before the live run: subscriptions-array parsing, RFC 3339 transaction dates, and actual .env loading via python-dotenv — mock-verified 2026-10-02.

## Challenges
PayPal's sandbox checkout is the swamp every dev hits: buyer-login password walls, guest-card declines, and verification codes to test numbers. The fix was resetting the sandbox buyer password in the developer dashboard (a live paypal.com reset can't touch sandbox accounts), then approving as the buyer. Three app bugs fell out of the live run and were fixed: token request needed an Accept-Language header, the AI analyzer crashed on a null 12-month charge field, and the scan merge needed subscription detail + plan price so fresh subs show $9.99 instead of $0.00.

## Accomplishments we're proud of
- Dashboard and health endpoint serving locally.
- Sandbox app configured with Subscriptions + Transaction Search, credentials accepted live.
- Demo subscription verified ACTIVE, detected and explained in the dashboard, cancelled in one tap, and confirmed CANCELLED on the API with an empty rescan.

## What's next (in order)
1. Publish the public GitHub repo (check no .env or secrets are committed).
2. Record the demo video under 3 minutes: connect, scan, read the AI explanation, kill one zombie, show the tally.
3. Finalize this Devpost text and submit before Nov 12.

## Demo script outline (60-90 sec, record at PC)
0:00 Problem in one line. 0:10 Connect sandbox. 0:20 Scan finds the $9.99 zombie. 0:35 AI explanation on screen. 0:50 Tap Kill it. 1:05 Rescan — gone, tally updated.
