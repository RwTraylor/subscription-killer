"""PayPal REST wrapper (sandbox-first).

Wired against the PayPal Developer Platform REST APIs:
  Auth:          POST /v1/oauth2/token (client-credentials grant)
  Subscriptions: /v1/billing/subscriptions (list / detail / cancel / suspend)
  History:       /v1/reporting/transactions (31-day windows, fields=all)

Docs: https://developer.paypal.com/docs/api/

Architecture note (from API research): the Subscriptions API is
merchant-side — PayPal offers no buyer-side "list my Netflix/Spotify"
endpoint to third-party apps. So the demo runs the honest full loop
against the app's own sandbox business account: seed test subscriptions
-> detect them -> AI explains -> one-tap kill. Judges can run every step.
"""
import os
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import httpx

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - dotenv is in requirements.txt
    pass

SANDBOX_BASE = "https://api-m.sandbox.paypal.com"
LIVE_BASE = "https://api-m.paypal.com"


class PayPalClient:
    def __init__(self):
        self.client_id = os.environ.get("PAYPAL_CLIENT_ID", "")
        self.client_secret = os.environ.get("PAYPAL_CLIENT_SECRET", "")
        sandbox = os.environ.get("PAYPAL_SANDBOX", "true").lower() == "true"
        self.base = SANDBOX_BASE if sandbox else LIVE_BASE
        self._http = httpx.Client(timeout=30.0)
        self._token = None
        self._token_exp = 0.0

    # -- auth -------------------------------------------------------------
    def _get_access_token(self) -> str:
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        r = self._http.post(
            f"{self.base}/v1/oauth2/token",
            auth=(self.client_id, self.client_secret),
            data={"grant_type": "client_credentials"},
            headers={"Accept": "application/json", "Accept-Language": "en_US"},
        )
        r.raise_for_status()
        data = r.json()
        self._token = data["access_token"]
        self._token_exp = time.time() + data.get("expires_in", 32400)
        return self._token

    def _auth_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": str(uuid.uuid4()),
        }

    def exchange_code(self, code: str) -> dict:
        """Exchange a user OAuth authorization code for tokens."""
        r = self._http.post(
            f"{self.base}/v1/oauth2/token",
            auth=(self.client_id, self.client_secret),
            data={"grant_type": "authorization_code", "code": code},
            headers={"Accept": "application/json"},
        )
        r.raise_for_status()
        return r.json()

    # -- low-level ----------------------------------------------------------
    def _get(self, path: str, params: dict | None = None, retries: int = 3) -> dict:
        for attempt in range(retries):
            r = self._http.get(
                f"{self.base}{path}", headers=self._auth_headers(), params=params
            )
            if r.status_code == 429 and attempt < retries - 1:
                time.sleep(int(r.headers.get("Retry-After", 2)))
                continue
            r.raise_for_status()
            return r.json()
        raise RuntimeError("PayPal kept rate-limiting us")

    def _post(self, path: str, body: dict | None = None):
        r = self._http.post(
            f"{self.base}{path}", headers=self._auth_headers(), json=body or {}
        )
        # cancel/suspend return 204 No Content — no body to parse
        if r.status_code == 204:
            return {}
        r.raise_for_status()
        return r.json() if r.text else {}

    # -- subscriptions -------------------------------------------------------
    def list_subscriptions(self, statuses: str = "ACTIVE") -> list[dict]:
        data = self._get(
            "/v1/billing/subscriptions",
            params={"statuses": statuses, "page_size": 20},
        )
        # PayPal list response is {"subscriptions": [...], "total_items": ...}
        return data.get("subscriptions") or data.get("subscription_collection") or []

    def get_subscription(self, sub_id: str) -> dict:
        return self._get(f"/v1/billing/subscriptions/{sub_id}")

    def cancel_subscription(
        self, sub_id: str, reason: str = "Cancelled via Subscription Killer"
    ) -> dict:
        detail = self.get_subscription(sub_id)
        self._post(f"/v1/billing/subscriptions/{sub_id}/cancel", {"reason": reason})
        savings = 0.0
        try:
            last = detail.get("billing_info", {}).get("last_payment", {})
            savings = float(last.get("amount", {}).get("value", 0.0))
        except (TypeError, ValueError):
            pass
        return {"status": "cancelled", "monthly_savings": savings}

    def suspend_subscription(
        self, sub_id: str, reason: str = "Suspended via Subscription Killer"
    ) -> dict:
        self._post(f"/v1/billing/subscriptions/{sub_id}/suspend", {"reason": reason})
        return {"status": "suspended"}

    # -- transaction history --------------------------------------------------
    def search_transactions(self, start: datetime, end: datetime) -> list[dict]:
        """One 31-day-max window of transaction history (fields=all)."""
        def _fmt(dt: datetime) -> str:
            return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        data = self._get(
            "/v1/reporting/transactions",
            params={
                "start_date": _fmt(start),
                "end_date": _fmt(end),
                "fields": "all",
                "page_size": 500,
            },
        )
        return data.get("transaction_details", [])

    @staticmethod
    def _counterparty(tx: dict) -> str:
        payer = tx.get("payer_info") or {}
        name = payer.get("payer_name") or {}
        full = f"{name.get('given_name', '')} {name.get('surname', '')}".strip()
        return full or payer.get("email_address") or "unknown"

    def get_recurring_charges(self, months: int = 12) -> list[dict]:
        """Detect recurring charges by clustering history on (who, amount).

        Walks 31-day windows back `months`, groups completed payments by
        counterparty + amount + currency, and keeps clusters with 3+ charges
        on a recognizable cadence. Merges in live Subscriptions API data so
        anything created through PayPal Subscriptions carries its ID (which
        is what makes one-tap cancel possible).
        """
        now = datetime.now(timezone.utc)
        txs: list[dict] = []
        cursor = now
        for _ in range(months):
            start = cursor - timedelta(days=31)
            txs.extend(self.search_transactions(start, cursor))
            cursor = start

        clusters: dict[tuple, list[dict]] = defaultdict(list)
        for tx in txs:
            info = tx.get("transaction_info") or {}
            if info.get("transaction_status") not in ("S", "D"):
                continue  # only settled/completed money movement
            amt = info.get("transaction_amount") or {}
            key = (
                self._counterparty(tx).lower(),
                amt.get("value"),
                amt.get("currency_code"),
            )
            clusters[key].append(
                {
                    "date": info.get("transaction_initiation_date", ""),
                    "event_code": info.get("transaction_event_code"),
                }
            )

        recurring: list[dict] = []
        for (who, value, currency), charges in clusters.items():
            if len(charges) < 3:
                continue
            dates = sorted(c["date"] for c in charges if c["date"])
            if len(dates) < 3:
                continue
            try:
                dts = [datetime.fromisoformat(d) for d in dates]
            except ValueError:
                continue
            gaps = [
                (b - a).days for a, b in zip(dts, dts[1:]) if (b - a).days > 0
            ]
            if not gaps:
                continue
            median_gap = sorted(gaps)[len(gaps) // 2]
            if 27 <= median_gap <= 33:
                cadence = "monthly"
            elif 6 <= median_gap <= 8:
                cadence = "weekly"
            elif 350 <= median_gap <= 370:
                cadence = "yearly"
            else:
                continue
            recurring.append(
                {
                    "merchant": who.title(),
                    "amount": float(value or 0),
                    "currency": currency or "USD",
                    "cadence": cadence,
                    "last_charge": dates[-1][:10],
                    "charges_12m": len(charges),
                    "subscription_id": None,
                }
            )

        # Merge live subscription data (these are directly cancellable).
        # The list endpoint omits plan_id and last_payment on fresh subs,
        # so pull the detail (and plan price as fallback) per subscription.
        try:
            for sub in self.list_subscriptions():
                sub_id = sub.get("id")
                try:
                    detail = self.get_subscription(sub_id) if sub_id else sub
                except Exception:  # noqa: BLE001 - fall back to list fields
                    detail = sub
                billing = detail.get("billing_info") or {}
                last = billing.get("last_payment") or {}
                amt = last.get("amount") or {}
                amount = float(amt.get("value", 0) or 0)
                plan_id = detail.get("plan_id") or sub.get("plan_id", "")
                merchant = f"PayPal subscription {plan_id}"
                if plan_id:
                    try:
                        plan = self._get(f"/v1/billing/plans/{plan_id}")
                        merchant = plan.get("name") or merchant
                        if amount == 0:
                            for cycle in plan.get("billing_cycles", []):
                                price = (cycle.get("pricing_scheme") or {}).get(
                                    "fixed_price"
                                ) or {}
                                if price.get("value"):
                                    amount = float(price["value"])
                                    break
                    except Exception:  # noqa: BLE001 - list fields still stand
                        pass
                recurring.append(
                    {
                        "merchant": merchant,
                        "amount": amount,
                        "currency": amt.get("currency_code", "USD"),
                        "cadence": "monthly",
                        "last_charge": (last.get("time") or detail.get("start_time") or "")[:10],
                        "charges_12m": None,
                        "subscription_id": sub_id,
                    }
                )
        except Exception:  # noqa: BLE001 - history clustering still stands alone
            pass

        return recurring
