import json
import os
import socket
import urllib.parse
import urllib.request
from uuid import uuid4


class SupabaseStorageError(Exception):
    pass


def _require_supabase_env() -> tuple[str, str, str]:
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "").strip()
    if not url:
        raise SupabaseStorageError("SUPABASE_URL is missing in environment.")
    if not service_role_key:
        raise SupabaseStorageError("SUPABASE_SERVICE_ROLE_KEY is missing in environment.")
    if not bucket:
        raise SupabaseStorageError("SUPABASE_STORAGE_BUCKET is missing in environment.")
    return url, service_role_key, bucket


def _friendly_upload_error(exc: Exception) -> str:
    message = str(exc)
    reason = getattr(exc, "reason", None)
    if isinstance(reason, socket.gaierror) or "getaddrinfo failed" in message.lower():
        return (
            "Supabase Storage hostname could not be resolved. Check internet/DNS, try mobile hotspot, "
            "or keep ALLOW_LOCAL_DOCUMENT_FALLBACK=true for local demo submissions."
        )
    if "timed out" in message.lower():
        return "Supabase Storage request timed out. Check network connectivity and try again."
    return f"Failed to upload file to Supabase Storage: {exc}"


def _request_json(url: str, method: str, headers: dict[str, str], body: bytes | None = None) -> dict:
    request = urllib.request.Request(url=url, method=method, data=body, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read().decode("utf-8")
        if not payload:
            return {}
        return json.loads(payload)


def upload_file(
    user_uid: str,
    loan_id: str,
    filename: str,
    file_bytes: bytes,
    content_type: str = "",
) -> str:
    base_url, service_role_key, bucket = _require_supabase_env()
    safe_name = str(filename or "document").replace("\\", "_").replace("/", "_")
    storage_path = f"applications/{user_uid}/{loan_id}/{uuid4().hex}_{safe_name}"
    encoded_path = urllib.parse.quote(storage_path, safe="/")
    endpoint = f"{base_url}/storage/v1/object/{bucket}/{encoded_path}"

    headers = {
        "Authorization": f"Bearer {service_role_key}",
        "apikey": service_role_key,
        "x-upsert": "false",
        "Content-Type": content_type or "application/octet-stream",
    }
    request = urllib.request.Request(url=endpoint, method="POST", data=file_bytes, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60):
            return storage_path
    except Exception as exc:
        raise SupabaseStorageError(_friendly_upload_error(exc)) from exc


def get_signed_url(storage_path: str, expires: int = 3600) -> str | None:
    if not storage_path:
        return None
    base_url, service_role_key, bucket = _require_supabase_env()
    encoded_path = urllib.parse.quote(storage_path, safe="/")
    endpoint = f"{base_url}/storage/v1/object/sign/{bucket}/{encoded_path}"
    payload = json.dumps({"expiresIn": int(expires)}).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {service_role_key}",
        "apikey": service_role_key,
        "Content-Type": "application/json",
    }
    try:
        response = _request_json(endpoint, "POST", headers, payload)
        signed_path = str(response.get("signedURL", "") or response.get("signedUrl", "")).strip()
        if not signed_path:
            return None
        if signed_path.startswith("http://") or signed_path.startswith("https://"):
            return signed_path
        return f"{base_url}/storage/v1{signed_path}"
    except Exception:
        return None
