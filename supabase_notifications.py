import json
import os
import urllib.error
import urllib.request


def supabase_email_notifications_enabled() -> bool:
    raw = str(os.getenv("USE_SUPABASE_EMAIL_NOTIFICATIONS", "true")).strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _function_endpoint() -> tuple[str, str, str]:
    base_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    service_role = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    function_name = os.getenv("SUPABASE_NOTIFY_FUNCTION", "email-notify").strip() or "email-notify"
    if not base_url:
        raise RuntimeError("SUPABASE_URL is missing.")
    if not service_role:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is missing.")
    return f"{base_url}/functions/v1/{function_name}", service_role, function_name


def invoke_notification(event_type: str, payload: dict) -> dict[str, object]:
    try:
        endpoint, service_role, function_name = _function_endpoint()
    except Exception as exc:
        return {"ok": False, "error": str(exc), "function": ""}

    request_payload = {
        "event_type": str(event_type or "").strip(),
        "payload": payload or {},
    }
    request = urllib.request.Request(
        url=endpoint,
        method="POST",
        data=json.dumps(request_payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {service_role}",
            "apikey": service_role,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read().decode("utf-8")
            parsed = json.loads(raw) if raw else {}
            return {
                "ok": bool(parsed.get("ok", False)),
                "sent_count": int(parsed.get("sent_count", 0) or 0),
                "error": str(parsed.get("error", "")).strip(),
                "function": function_name,
            }
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8")
        except Exception:
            body = str(exc)
        return {"ok": False, "error": f"HTTP {exc.code}: {body}", "function": function_name}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "function": function_name}
