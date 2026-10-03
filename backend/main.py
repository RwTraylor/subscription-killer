"""Subscription Killer — FastAPI backend.

Routes:
  GET  /                        -> serves the dashboard
  GET  /api/health              -> liveness check
  POST /api/paypal/connect      -> exchange OAuth code for tokens (sandbox)
  GET  /api/subscriptions       -> recurring charges found, AI-analyzed
  POST /api/subscriptions/analyze -> run the AI analyzer over cached data
  POST /api/subscriptions/{sub_id}/cancel -> cancel via PayPal Subscriptions API
"""
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - dotenv is in requirements.txt
    pass

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .ai_analyzer import analyze_subscriptions
from .paypal_client import PayPalClient

app = FastAPI(title="Subscription Killer")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


class ConnectRequest(BaseModel):
    code: str  # OAuth authorization code from PayPal


class CancelResponse(BaseModel):
    subscription_id: str
    status: str
    monthly_savings: float


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/")
def dashboard():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.post("/api/paypal/connect")
def paypal_connect(body: ConnectRequest):
    """Exchange the OAuth code for access/refresh tokens (sandbox)."""
    client = PayPalClient()
    try:
        tokens = client.exchange_code(body.code)
    except Exception as exc:  # noqa: BLE001 - surface PayPal errors cleanly
        raise HTTPException(status_code=502, detail=f"PayPal connect failed: {exc}")
    return {"connected": True, "scope": tokens.get("scope")}


@app.get("/api/subscriptions")
def list_subscriptions():
    """Return AI-analyzed recurring charges, ranked by zombie score."""
    client = PayPalClient()
    raw = client.get_recurring_charges()
    analyzed = analyze_subscriptions(raw)
    total_burn = round(sum(s["monthly_cost"] for s in analyzed), 2)
    return {"subscriptions": analyzed, "total_monthly_burn": total_burn}


@app.post("/api/subscriptions/{sub_id}/cancel", response_model=CancelResponse)
def cancel_subscription(sub_id: str):
    """Cancel a subscription through PayPal; report the monthly savings."""
    client = PayPalClient()
    try:
        result = client.cancel_subscription(sub_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Cancel failed: {exc}")
    return CancelResponse(
        subscription_id=sub_id,
        status=result.get("status", "cancelled"),
        monthly_savings=result.get("monthly_savings", 0.0),
    )


# Serve any other frontend assets (css/js if split out later)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR, check_dir=False), name="static")
