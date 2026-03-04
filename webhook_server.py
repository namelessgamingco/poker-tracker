# =============================================================================
# webhook_server.py — Radom Webhook Handler for Nameless Poker
# =============================================================================
#
# Receives payment events from Radom and updates poker_profiles accordingly.
# Deploy as a separate Railway service from the same repo.
#
# Railway start command:  python webhook_server.py
# Railway port:           Reads from PORT env var (Railway sets this automatically)
#
# Required env vars:
#   SUPABASE_URL_PROD (or SUPABASE_URL_DEV if APP_ENV=dev)
#   SUPABASE_SERVICE_ROLE_KEY_PROD (or _DEV)
#   RADOM_WEBHOOK_KEY  — from Radom Dashboard > Developer > Webhooks
#   APP_ENV            — "dev" or "prod"
#
# =============================================================================

import os
import json
import traceback
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify

# ---------------------------------------------------------------------------
# Supabase client (standalone — no Streamlit dependency)
# ---------------------------------------------------------------------------

_supabase_client = None

def _get_env(name, default=None):
    return os.environ.get(name, default)

def _get_supabase():
    """Get or create Supabase admin client (service role)."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    try:
        from supabase import create_client
    except ImportError:
        raise RuntimeError("supabase-py not installed. Run: pip install supabase")

    env = (_get_env("APP_ENV", "prod") or "prod").lower().strip()
    is_dev = env == "dev"

    url = _get_env("SUPABASE_URL_DEV" if is_dev else "SUPABASE_URL_PROD")
    key = _get_env("SUPABASE_SERVICE_ROLE_KEY_DEV" if is_dev else "SUPABASE_SERVICE_ROLE_KEY_PROD")

    if not url or not key:
        raise RuntimeError(
            f"Missing Supabase credentials for env={env}. "
            f"Need SUPABASE_URL_{'DEV' if is_dev else 'PROD'} and "
            f"SUPABASE_SERVICE_ROLE_KEY_{'DEV' if is_dev else 'PROD'}"
        )

    _supabase_client = create_client(url, key)
    print(f"[webhook] Supabase client initialized (env={env})")
    return _supabase_client


def db():
    """Shortcut for Supabase admin client."""
    return _get_supabase()


# ---------------------------------------------------------------------------
# Table name — CRITICAL: must match your actual table
# ---------------------------------------------------------------------------

TABLE = "poker_profiles"


# ---------------------------------------------------------------------------
# Flask App
# ---------------------------------------------------------------------------

app = Flask(__name__)

RADOM_WEBHOOK_KEY = _get_env("RADOM_WEBHOOK_KEY")


@app.route("/", methods=["GET"])
def health():
    """Health check for Railway."""
    return jsonify({
        "status": "ok",
        "service": "nameless-poker-webhooks",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/webhooks/radom", methods=["POST"])
def handle_radom_webhook():
    """
    Main webhook endpoint. Radom POSTs here for all subscription events.

    Radom sends a 'verification_key' header to authenticate.
    """
    # --- Verify authenticity ---
    if RADOM_WEBHOOK_KEY:
        print(f"[webhook] DEBUG stored key length={len(RADOM_WEBHOOK_KEY)} first10='{RADOM_WEBHOOK_KEY[:10]}'")
        incoming_key = None
        for header_name in ["Verification-Key", "Verification_Key", "verification_key", "verification-key"]:
            val = request.headers.get(header_name)
            if val:
                incoming_key = val.strip()
                break
        print(f"[webhook] DEBUG incoming key length={len(incoming_key) if incoming_key else 0} first10='{incoming_key[:10] if incoming_key else 'None'}'")
        if incoming_key != RADOM_WEBHOOK_KEY:
            print(f"[webhook] REJECTED — invalid verification key")
            return jsonify({"error": "Invalid verification key"}), 401

    # --- Parse payload ---
    try:
        payload = request.get_json(force=True)
    except Exception as e:
        print(f"[webhook] Failed to parse JSON: {e}")
        return jsonify({"error": "Invalid JSON"}), 400

    event_type = payload.get("eventType", "unknown")
    print(f"[webhook] ===== Received event: {event_type} =====")
    print(f"[webhook] Payload keys: {list(payload.keys())}")

    # --- Route to handler ---
    handlers = {
        "newSubscription": handle_new_subscription,
        "subscriptionPayment": handle_subscription_payment,
        "subscriptionPaymentReminder": handle_payment_reminder,
        "subscriptionPaymentOverdue": handle_payment_overdue,
        "subscriptionCancelled": handle_subscription_cancelled,
        "subscriptionExpired": handle_subscription_expired,
    }

    handler = handlers.get(event_type)
    if handler:
        try:
            handler(payload)
            return jsonify({"status": "processed", "event": event_type}), 200
        except Exception as e:
            print(f"[webhook] ERROR handling {event_type}: {e}")
            traceback.print_exc()
            # Return 200 anyway so Radom doesn't retry endlessly
            return jsonify({"status": "error", "event": event_type, "message": str(e)}), 200

    print(f"[webhook] Unhandled event type: {event_type}")
    return jsonify({"status": "ignored", "event": event_type}), 200


# =============================================================================
# HELPERS
# =============================================================================

def _find_user_by_subscription_id(subscription_id: str):
    """Find a user by their Radom subscription ID."""
    if not subscription_id:
        return None
    try:
        resp = (
            db().table(TABLE)
            .select("*")
            .eq("radom_subscription_id", subscription_id)
            .maybe_single()
            .execute()
        )
        return resp.data if resp.data else None
    except Exception as e:
        print(f"[webhook] _find_user_by_subscription_id error: {e}")
        return None


def _find_user_by_email(email: str):
    """Find a user by email address."""
    if not email:
        return None
    try:
        resp = (
            db().table(TABLE)
            .select("*")
            .eq("email", email.lower().strip())
            .maybe_single()
            .execute()
        )
        return resp.data if resp.data else None
    except Exception as e:
        print(f"[webhook] _find_user_by_email error: {e}")
        return None


def _update_user(user_id: str, updates: dict):
    """Update a user's poker_profiles row."""
    try:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        db().table(TABLE).update(updates).eq("user_id", user_id).execute()
        return True
    except Exception as e:
        print(f"[webhook] _update_user error for {user_id}: {e}")
        return False


def _extract_email_from_payload(payload: dict) -> str:
    """
    Extract user email from Radom webhook payload.

    Radom can pass metadata in several places depending on configuration:
    1. eventData.*.gateway.metadata.user_email
    2. eventData.*.tags.user_email
    3. URL parameter passed through (appears in inputData or metadata)
    """
    event_data = payload.get("eventData", {})

    # Walk through all event data looking for email
    for key, value in event_data.items():
        if not isinstance(value, dict):
            continue

        # Check gateway metadata
        gateway = value.get("gateway", {})
        if isinstance(gateway, dict):
            metadata = gateway.get("metadata", {})
            if isinstance(metadata, dict):
                email = metadata.get("user_email") or metadata.get("email")
                if email:
                    return email.lower().strip()

        # Check tags
        tags = value.get("tags", {})
        if isinstance(tags, dict):
            email = tags.get("user_email") or tags.get("email")
            if email:
                return email.lower().strip()

        # Check inputData (custom fields)
        input_data = value.get("inputData", [])
        if isinstance(input_data, list):
            for item in input_data:
                if isinstance(item, dict):
                    field = (item.get("name") or item.get("label") or "").lower()
                    if "email" in field:
                        return (item.get("value") or "").lower().strip()

    # Check top-level radomData
    radom_data = payload.get("radomData", {})
    if isinstance(radom_data, dict):
        metadata = radom_data.get("metadata", {})
        if isinstance(metadata, dict):
            email = metadata.get("user_email") or metadata.get("email")
            if email:
                return email.lower().strip()

    return ""


def _extract_subscription_id(payload: dict) -> str:
    """Extract Radom subscription ID from the payload."""
    event_data = payload.get("eventData", {})

    for key, value in event_data.items():
        if isinstance(value, dict):
            sid = value.get("subscriptionId")
            if sid:
                return str(sid)

    # Check radomData
    radom_data = payload.get("radomData", {})
    if isinstance(radom_data, dict):
        sub = radom_data.get("subscription", {})
        if isinstance(sub, dict):
            sid = sub.get("subscriptionId")
            if sid:
                return str(sid)

    return ""


def _log_event(event_type: str, email: str, details: str):
    """Log a webhook event (prints to Railway logs)."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[webhook] [{ts}] {event_type} | {email} | {details}")


# =============================================================================
# EVENT HANDLERS
# =============================================================================

def handle_new_subscription(payload: dict):
    """
    First successful payment — activate the subscription.

    Flow: User clicks payment link → pays on Radom → this fires
    → match by email → set status=active, store subscription ID
    """
    subscription_id = _extract_subscription_id(payload)
    email = _extract_email_from_payload(payload)

    _log_event("newSubscription", email, f"sub_id={subscription_id}")

    # Find user — try email first (most reliable for initial payment)
    user = _find_user_by_email(email) if email else None

    # Fallback: try subscription ID (shouldn't happen for first payment)
    if not user and subscription_id:
        user = _find_user_by_subscription_id(subscription_id)

    if not user:
        print(f"[webhook] ERROR: No user found for newSubscription. email={email}, sub_id={subscription_id}")
        print(f"[webhook] Full payload: {json.dumps(payload, indent=2)[:2000]}")
        return

    now = datetime.now(timezone.utc)
    period_end = now + timedelta(days=30)
    grace_end = period_end + timedelta(days=3)

    # Get payment amount from payload
    event_data = payload.get("eventData", {})
    new_sub_data = event_data.get("newSubscription", {})
    amount = new_sub_data.get("amount") or 299.00

    _update_user(user["user_id"], {
        "radom_subscription_id": subscription_id,
        "subscription_status": "active",
        "subscription_plan": "monthly",
        "subscription_amount": float(amount),
        "subscription_started_at": now.isoformat(),
        "subscription_current_period_end": period_end.isoformat(),
        "subscription_grace_period_end": grace_end.isoformat(),
        "last_successful_payment_at": now.isoformat(),
        "failed_payment_count": 0,
        "is_active": True,
        "is_trial": False,
        "lockout_reason": None,
    })

    _log_event("newSubscription", user["email"], "ACTIVATED — access granted")


def handle_subscription_payment(payload: dict):
    """
    Recurring payment succeeded (not the first one).

    Flow: Radom auto-charges → success → this fires
    → match by subscription ID → renew period, reset failures
    """
    subscription_id = _extract_subscription_id(payload)
    _log_event("subscriptionPayment", "?", f"sub_id={subscription_id}")

    user = _find_user_by_subscription_id(subscription_id)

    if not user:
        # Try email as fallback
        email = _extract_email_from_payload(payload)
        user = _find_user_by_email(email) if email else None

    if not user:
        print(f"[webhook] ERROR: No user found for subscriptionPayment. sub_id={subscription_id}")
        return

    now = datetime.now(timezone.utc)
    period_end = now + timedelta(days=30)
    grace_end = period_end + timedelta(days=3)

    _update_user(user["user_id"], {
        "subscription_status": "active",
        "subscription_current_period_end": period_end.isoformat(),
        "subscription_grace_period_end": grace_end.isoformat(),
        "last_successful_payment_at": now.isoformat(),
        "failed_payment_count": 0,
        "is_active": True,
        "lockout_reason": None,
        "payment_overdue_notified_at": None,
    })

    _log_event("subscriptionPayment", user["email"], "RENEWED — period extended 30 days")


def handle_payment_reminder(payload: dict):
    """
    Payment due soon (~24 hours before charge attempt).

    No status change — just log it. Email notification can be added later.
    """
    subscription_id = _extract_subscription_id(payload)
    user = _find_user_by_subscription_id(subscription_id)

    email = user["email"] if user else "unknown"
    _log_event("subscriptionPaymentReminder", email, "Payment due soon")

    if user:
        _update_user(user["user_id"], {
            "payment_reminder_sent_at": datetime.now(timezone.utc).isoformat(),
        })


def handle_payment_overdue(payload: dict):
    """
    Payment failed after Radom's retry period.

    CRITICAL: This locks the user out.

    Flow: Radom retries payment → all attempts fail → this fires
    → set status=overdue, is_active=False → user sees lockout screen
    """
    subscription_id = _extract_subscription_id(payload)
    user = _find_user_by_subscription_id(subscription_id)

    if not user:
        print(f"[webhook] ERROR: No user found for paymentOverdue. sub_id={subscription_id}")
        return

    failed_count = (user.get("failed_payment_count") or 0) + 1

    _update_user(user["user_id"], {
        "subscription_status": "overdue",
        "is_active": False,
        "failed_payment_count": failed_count,
        "payment_overdue_notified_at": datetime.now(timezone.utc).isoformat(),
        "lockout_reason": "Payment failed. Please update your payment method to restore access.",
    })

    _log_event("subscriptionPaymentOverdue", user["email"],
               f"LOCKED OUT — failed_count={failed_count}")


def handle_subscription_cancelled(payload: dict):
    """
    Subscription cancelled (by user request or admin).

    Immediate lockout — no grace period for cancellations.
    User can resubscribe anytime via payment link.
    """
    subscription_id = _extract_subscription_id(payload)
    user = _find_user_by_subscription_id(subscription_id)

    if not user:
        print(f"[webhook] ERROR: No user found for subscriptionCancelled. sub_id={subscription_id}")
        return

    _update_user(user["user_id"], {
        "subscription_status": "cancelled",
        "is_active": False,
        "lockout_reason": "Subscription cancelled.",
    })

    _log_event("subscriptionCancelled", user["email"], "CANCELLED — access revoked")


def handle_subscription_expired(payload: dict):
    """
    Subscription term ended without renewal.

    Lock user out, they need to resubscribe.
    """
    subscription_id = _extract_subscription_id(payload)
    user = _find_user_by_subscription_id(subscription_id)

    if not user:
        print(f"[webhook] ERROR: No user found for subscriptionExpired. sub_id={subscription_id}")
        return

    _update_user(user["user_id"], {
        "subscription_status": "expired",
        "is_active": False,
        "lockout_reason": "Subscription expired. Please renew to continue.",
    })

    _log_event("subscriptionExpired", user["email"], "EXPIRED — access revoked")


# =============================================================================
# RUN SERVER
# =============================================================================

if __name__ == "__main__":
    port = int(_get_env("PORT", "8080"))
    env = _get_env("APP_ENV", "prod")

    print(f"")
    print(f"  ╔══════════════════════════════════════════════╗")
    print(f"  ║  NAMELESS POKER — Webhook Server             ║")
    print(f"  ║  Port: {port:<5}  Env: {env:<10}              ║")
    print(f"  ║  Endpoint: /webhooks/radom                   ║")
    print(f"  ╚══════════════════════════════════════════════╝")
    print(f"")

    # Validate Supabase connection on startup
    try:
        _get_supabase()
        print(f"[webhook] Supabase connection OK")
    except Exception as e:
        print(f"[webhook] WARNING: Supabase connection failed: {e}")
        print(f"[webhook] Server will start but webhook processing will fail")

    if not RADOM_WEBHOOK_KEY:
        print(f"[webhook] WARNING: RADOM_WEBHOOK_KEY not set — webhooks will NOT be verified")

    app.run(host="0.0.0.0", port=port)