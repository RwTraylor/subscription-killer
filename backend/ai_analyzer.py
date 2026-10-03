"""AI analyzer: turn raw recurring charges into plain-English verdicts.

Two layers:
  1. Heuristic pass (always runs): cadence detection, zombie-score signals.
  2. LLM pass (when AI_API_KEY is set): natural-language summaries, zombie
     likelihood, and a kill/keep/review verdict per subscription.

Output per subscription:
  {"merchant", "amount", "currency", "cadence", "last_charge",
   "monthly_cost", "plain_english", "zombie_score" (0-100), "reason",
   "subscription_id",
   plus LLM fields: "ai_plain_english", "ai_zombie_score",
   "ai_verdict" ("kill"|"keep"|"review"), "ai_verdict_reason"}

The LLM call is strictly best-effort: any failure (no network, bad key,
malformed response) leaves the heuristic output untouched, so the demo
never breaks.
"""
import json
import os
import re

import urllib.request

AI_API_KEY = os.environ.get("AI_API_KEY", "")
AI_MODEL = os.environ.get("AI_MODEL", "gpt-4o-mini")
AI_API_BASE = os.environ.get("AI_API_BASE", "https://api.openai.com/v1").rstrip("/")
AI_TIMEOUT = float(os.environ.get("AI_TIMEOUT", "20"))


def _heuristic_summary(charge: dict) -> tuple[str, int, str]:
    """Return (plain_english, zombie_score, reason) without any LLM."""
    merchant = charge.get("merchant", "Unknown merchant")
    amount = charge.get("amount", 0.0)
    cadence = charge.get("cadence", "monthly")
    charges_12m = charge.get("charges_12m") or 0

    # Zombie signals: perfect cadence with no variation smells forgotten.
    score = 0
    reasons = []
    if charges_12m >= 11:
        score += 40
        reasons.append("charged like clockwork for a year")
    if re.search(r"(trial|premium|plus|pro)$", merchant, re.I):
        score += 15
        reasons.append("name looks like a free-trial conversion")
    if amount < 5:
        score += 15
        reasons.append("small enough to ignore on a statement")

    plain = (
        f"{merchant} charges ${amount:.2f} {cadence}. "
        f"Last hit {charge.get('last_charge', 'recently')}."
    )
    reason = "; ".join(reasons) if reasons else "no strong zombie signals"
    return plain, min(score, 100), reason


_SYSTEM_PROMPT = (
    "You are a subscription-audit assistant. The user gave you PayPal sandbox "
    "data showing recurring charges. For EACH subscription, return one JSON "
    "object in a top-level JSON array with exactly these keys:\n"
    '  "id": the subscription id from the input,\n'
    '  "plain_english": one plain sentence a non-technical person would '
    'understand ("Netflix takes $15.49 every month"),\n'
    '  "zombie_score": integer 0-100, how likely the user forgot this '
    "subscription (small amounts, trial-converted names, and year-long "
    "unchanged cadences score high; daily-use services score low),\n"
    '  "verdict": one of "kill", "keep", or "review",\n'
    '  "verdict_reason": one short sentence justifying the verdict.\n'
    "Reply with ONLY the JSON array, no markdown, no commentary."
)


def _build_llm_payload(charges: list[dict]) -> dict:
    slim = [
        {
            "id": c.get("subscription_id") or c.get("merchant"),
            "merchant": c.get("merchant"),
            "amount": c.get("amount"),
            "currency": c.get("currency", "USD"),
            "cadence": c.get("cadence"),
            "last_charge": c.get("last_charge"),
            "charges_12m": c.get("charges_12m", 0),
            "heuristic_note": c.get("reason"),
        }
        for c in charges[:12]
    ]
    return {
        "model": AI_MODEL,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "Subscriptions to audit:\n"
                + json.dumps(slim, indent=1),
            },
        ],
    }


def _merge_llm_results(charges: list[dict], raw_text: str) -> list[dict]:
    """Fold LLM verdicts back onto charges. Raises ValueError on bad JSON."""
    parsed = json.loads(raw_text)
    # Accept either a bare array or {"results": [...]}.
    items = parsed.get("results") if isinstance(parsed, dict) else parsed
    if not isinstance(items, list):
        raise ValueError("LLM response is not a JSON array")
    by_id = {str(i.get("id")): i for i in items if isinstance(i, dict)}
    merged = []
    for c in charges:
        key = str(c.get("subscription_id") or c.get("merchant"))
        ai = by_id.get(key, {})
        verdict = str(ai.get("verdict", "")).lower()
        if verdict not in ("kill", "keep", "review"):
            verdict = "review"
        try:
            ai_score = int(ai.get("zombie_score", 0))
        except (TypeError, ValueError):
            ai_score = 0
        merged.append(
            {
                **c,
                "ai_plain_english": str(ai.get("plain_english") or c["plain_english"]),
                "ai_zombie_score": max(0, min(100, ai_score)),
                "ai_verdict": verdict,
                "ai_verdict_reason": str(ai.get("verdict_reason") or c["reason"]),
            }
        )
    return merged


def _llm_summary(charges: list[dict]) -> list[dict]:
    """LLM enrichment pass. Best-effort: any failure returns charges unchanged."""
    if not AI_API_KEY or not charges:
        return charges
    try:
        body = json.dumps(_build_llm_payload(charges)).encode()
        req = urllib.request.Request(
            f"{AI_API_BASE}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {AI_API_KEY}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=AI_TIMEOUT) as resp:
            if resp.status != 200:
                return charges
            content = json.loads(resp.read().decode())["choices"][0][
                "message"
            ]["content"]
        return _merge_llm_results(charges, content)
    except Exception:
        return charges


def analyze_subscriptions(raw_charges: list[dict]) -> list[dict]:
    analyzed = []
    for charge in raw_charges:
        plain, score, reason = _heuristic_summary(charge)
        monthly = charge.get("amount", 0.0)
        if charge.get("cadence") == "yearly":
            monthly = monthly / 12
        elif charge.get("cadence") == "weekly":
            monthly = monthly * 4.33
        analyzed.append(
            {
                **charge,
                "monthly_cost": round(monthly, 2),
                "plain_english": plain,
                "zombie_score": score,
                "reason": reason,
            }
        )
    if AI_API_KEY:
        analyzed = _llm_summary(analyzed)
    # Zombies first.
    analyzed.sort(key=lambda s: s["zombie_score"], reverse=True)
    return analyzed
