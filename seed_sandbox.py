"""Seed one sandbox subscription for the Subscription Killer demo.

Run ONLY against PayPal sandbox, after you have created a local .env
(copy .env.example to .env and fill it in on your own machine --
never paste the secret into chat):

    .venv\\Scripts\\python seed_sandbox.py

What it does:
  1. Gets a sandbox access token (token/secret are never printed).
  2. Creates a billing product + plan ($9.99/month) if needed.
  3. Creates a subscription and prints the buyer APPROVE URL.
  4. You open that URL logged in as your sandbox PERSONAL (buyer)
     account at sandbox.paypal.com and approve it.
  5. Then start the app and open the dashboard -- the subscription
     will show up in GET /api/subscriptions and can be cancelled
     with the Kill button (POST .../cancel returns 204).

Refuses to run unless PAYPAL_SANDBOX=true.
"""
import os
import sys
import uuid

import httpx

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

BASE = "https://api-m.sandbox.paypal.com"


def main() -> int:
    if os.environ.get("PAYPAL_SANDBOX", "true").lower() != "true":
        print("Refusing to run: PAYPAL_SANDBOX is not 'true'. This seed script is sandbox-only.")
        return 1
    client_id = os.environ.get("PAYPAL_CLIENT_ID", "")
    client_secret = os.environ.get("PAYPAL_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        print("Missing PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET. Create .env from .env.example first.")
        return 1

    with httpx.Client(timeout=30.0) as http:
        tok = http.post(
            f"{BASE}/v1/oauth2/token",
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            headers={"Accept": "application/json"},
        )
        tok.raise_for_status()
        headers = {
            "Authorization": f"Bearer {tok.json()['access_token']}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": str(uuid.uuid4()),
        }

        product = http.post(
            f"{BASE}/v1/catalogs/products",
            headers=headers,
            json={"name": "SubKiller Demo Streaming", "type": "SERVICE"},
        )
        product.raise_for_status()
        product_id = product.json()["id"]

        plan = http.post(
            f"{BASE}/v1/billing/plans",
            headers=headers,
            json={
                "product_id": product_id,
                "name": "Demo Streaming Monthly",
                "billing_cycles": [
                    {
                        "frequency": {"interval_unit": "MONTH", "interval_count": 1},
                        "tenure_type": "REGULAR",
                        "sequence": 1,
                        "total_cycles": 0,
                        "pricing_scheme": {
                            "fixed_price": {"value": "9.99", "currency_code": "USD"}
                        },
                    }
                ],
                "payment_preferences": {"auto_bill_outstanding": True},
            },
        )
        plan.raise_for_status()
        plan_id = plan.json()["id"]

        sub = http.post(
            f"{BASE}/v1/billing/subscriptions",
            headers=headers,
            json={
                "plan_id": plan_id,
                "application_context": {
                    "return_url": "http://localhost:8000/",
                    "cancel_url": "http://localhost:8000/",
                },
            },
        )
        sub.raise_for_status()
        data = sub.json()
        approve = next(
            (link["href"] for link in data.get("links", []) if link.get("rel") == "approve"),
            None,
        )
        print(f"Subscription created: {data.get('id')} (status {data.get('status')})")
        print(f"Plan: {plan_id}")
        if approve:
            print("\nOpen this URL logged in as your sandbox PERSONAL buyer account and approve:")
            print(approve)
            print("\nThen run the app (uvicorn backend.main:app) and open http://localhost:8000")
        return 0


if __name__ == "__main__":
    sys.exit(main())
