import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from firebase_config import get_app_namespace, get_firebase_service_account, get_firebase_web_config
from supabase_storage import SupabaseStorageError, get_signed_url as get_supabase_signed_url, upload_file as upload_to_supabase
from tools import analyze_application

try:
    import firebase_admin
    from firebase_admin import credentials, firestore, storage
except ImportError:  # pragma: no cover - dependency may not be installed locally yet
    firebase_admin = None
    credentials = None
    firestore = None
    storage = None

try:
    from google.api_core.exceptions import FailedPrecondition, NotFound, PermissionDenied
    from google.auth.exceptions import RefreshError, GoogleAuthError
except ImportError:  # pragma: no cover - optional dependency path
    FailedPrecondition = None
    NotFound = None
    PermissionDenied = None
    RefreshError = None
    GoogleAuthError = None


class FirebaseServiceError(Exception):
    pass


def _map_firebase_auth_error(message: str) -> str:
    error_map = {
        "CONFIGURATION_NOT_FOUND": (
            "Firebase Authentication is not configured for this project. "
            "Enable the Email/Password sign-in provider in Firebase Console."
        ),
        "EMAIL_NOT_FOUND": "No account exists for this email.",
        "INVALID_PASSWORD": "The password is incorrect.",
        "INVALID_LOGIN_CREDENTIALS": "The email or password is incorrect.",
        "EMAIL_EXISTS": "An account with this email already exists.",
        "OPERATION_NOT_ALLOWED": (
            "This sign-in method is disabled in Firebase. "
            "Enable Email/Password authentication in Firebase Console."
        ),
    }
    return error_map.get(message, message)


def _map_google_cloud_error(exc: Exception) -> str:
    message = str(exc)
    if "firestore.googleapis.com" in message or "Cloud Firestore API has not been used" in message:
        return (
            "Cloud Firestore API is disabled for project 'creditmind-loan'. "
            "Enable it in Google Cloud Console, then wait a minute and try again."
        )
    if "SERVICE_DISABLED" in message:
        return "A required Google Cloud API is disabled for this Firebase project."
    if "The database" in message and "does not exist" in message:
        return "Cloud Firestore database has not been created yet. Create a Firestore database in Firebase Console."
    if "specified bucket does not exist" in message.lower():
        return (
            "Firebase Storage bucket is not available for this project yet. "
            "Create Firebase Storage in Firebase Console or use the fallback mock-processing mode."
        )
    if "storage" in message.lower() and "not found" in message.lower():
        return "Firebase Storage is not initialized for this project yet."
    if "invalid_grant" in message.lower() or "invalid jwt signature" in message.lower():
        return (
            "Your Firebase service account credentials are invalid, revoked, or incorrectly configured. "
            "Regenerate the service account key in Google Cloud Console and update FIREBASE_SERVICE_ACCOUNT_JSON "
            "or FIREBASE_SERVICE_ACCOUNT_PATH in your .env file."
        )
    return message


def _wrap_google_cloud_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except FirebaseServiceError:
        raise
    except Exception as exc:
        handled = False
        if PermissionDenied is not None and isinstance(exc, PermissionDenied):
            handled = True
        elif FailedPrecondition is not None and isinstance(exc, FailedPrecondition):
            handled = True
        elif NotFound is not None and isinstance(exc, NotFound):
            handled = True
        elif RefreshError is not None and isinstance(exc, RefreshError):
            handled = True
        elif GoogleAuthError is not None and isinstance(exc, GoogleAuthError):
            handled = True
        elif "google.api_core.exceptions" in str(type(exc)):
            handled = True
        elif "invalid_grant" in str(exc) or "Invalid JWT Signature" in str(exc):
            handled = True

        if handled:
            raise FirebaseServiceError(_map_google_cloud_error(exc)) from exc
        raise


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_firebase_admin() -> None:
    if firebase_admin is None or credentials is None or firestore is None or storage is None:
        raise FirebaseServiceError(
            "firebase-admin is not available in the Python environment running Streamlit. "
            "Install dependencies in that environment or start Streamlit with "
            ".\\.venv\\Scripts\\python.exe -m streamlit run main.py."
        )


def _get_firebase_app():
    _require_firebase_admin()

    if not firebase_admin._apps:
        service_account = get_firebase_service_account()
        if not service_account:
            raise FirebaseServiceError(
                "Firebase service account credentials are missing. "
                "Set FIREBASE_SERVICE_ACCOUNT_JSON or FIREBASE_SERVICE_ACCOUNT_PATH."
            )
        try:
            firebase_admin.initialize_app(
                credentials.Certificate(service_account),
                {"storageBucket": get_firebase_web_config().get("storageBucket", "")},
            )
        except Exception as exc:
            raise FirebaseServiceError(
                "Failed to initialize Firebase Admin SDK. Check your service account credentials and project configuration."
            ) from exc

    return firebase_admin.get_app()


def get_firestore_client():
    _get_firebase_app()

    return firestore.client()


def get_storage_bucket():
    _get_firebase_app()
    return storage.bucket()


def _firebase_auth_request(endpoint: str, payload: dict[str, object]) -> dict[str, object]:
    api_key = get_firebase_web_config().get("apiKey", "").strip()
    if not api_key:
        raise FirebaseServiceError("Firebase API key is missing.")

    request = urllib.request.Request(
        url=f"https://identitytoolkit.googleapis.com/v1/accounts:{endpoint}?key={api_key}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_payload = exc.read().decode("utf-8")
        try:
            parsed = json.loads(error_payload)
            message = parsed.get("error", {}).get("message", "Firebase Auth request failed.")
        except json.JSONDecodeError:
            message = "Firebase Auth request failed."
        raise FirebaseServiceError(_map_firebase_auth_error(message)) from exc
    except urllib.error.URLError as exc:
        raise FirebaseServiceError("Unable to reach Firebase Auth.") from exc


def _users_collection():
    return get_firestore_client().collection("users")


def _applications_collection():
    return get_firestore_client().collection("applications")


def _current_namespace() -> str:
    return get_app_namespace()


def _get_user_document_by_email(email: str) -> dict | None:
    def _fetch_and_iterate():
        docs = _users_collection().where("email", "==", email).limit(5).stream()
        namespace = _current_namespace()
        fallback_match = None
        for doc in docs:
            payload = doc.to_dict()
            if namespace and str(payload.get("app_namespace", "")).strip() != namespace:
                if fallback_match is None:
                    payload["doc_id"] = doc.id
                    fallback_match = payload
                continue
            payload["doc_id"] = doc.id
            return payload
        return fallback_match
    
    return _wrap_google_cloud_call(_fetch_and_iterate)


def _get_user_document_by_uid(uid: str) -> dict | None:
    def _fetch_doc():
        snapshot = _users_collection().document(uid).get()
        if not snapshot.exists:
            return None
        payload = snapshot.to_dict() or {}
        payload["doc_id"] = snapshot.id
        return payload
    
    return _wrap_google_cloud_call(_fetch_doc)


def _set_user_profile(uid: str, payload: dict[str, object]) -> None:
    def _update_doc():
        _users_collection().document(uid).set(payload, merge=True)
    
    _wrap_google_cloud_call(_update_doc)


def _applications_document(app_id: str):
    return _applications_collection().document(app_id)


def _extract_document_excerpt(payload: dict[str, object]) -> str:
    excerpt = str(payload.get("text_excerpt", "")).strip()
    return excerpt[:2500]


def _build_firebase_download_url(bucket_name: str, storage_path: str, download_token: str) -> str:
    encoded_path = urllib.parse.quote(storage_path, safe="")
    return f"https://firebasestorage.googleapis.com/v0/b/{bucket_name}/o/{encoded_path}?alt=media&token={download_token}"


def _upload_to_firebase_storage(
    bucket,
    storage_path: str,
    file_bytes: bytes,
    content_type: str,
) -> str:
    blob = bucket.blob(storage_path)
    download_token = uuid4().hex
    blob.metadata = {"firebaseStorageDownloadTokens": download_token}
    _wrap_google_cloud_call(blob.upload_from_string, file_bytes, content_type=content_type or None)
    _wrap_google_cloud_call(blob.patch)
    return _build_firebase_download_url(bucket.name, storage_path, download_token)


def _save_documents_to_local_storage(user_uid: str, loan_id: str, uploaded_files: list[dict[str, object]]) -> list[dict[str, object]]:
    upload_root = Path("uploaded_documents") / user_uid / loan_id
    upload_root.mkdir(parents=True, exist_ok=True)

    stored_documents = []
    for file_payload in uploaded_files:
        file_bytes = file_payload.get("bytes", b"")
        if not isinstance(file_bytes, bytes):
            continue

        safe_name = str(file_payload.get("name", "document")).replace("\\", "_").replace("/", "_")
        local_filename = f"{uuid4().hex}_{safe_name}"
        local_path = upload_root / local_filename
        local_path.write_bytes(file_bytes)

        stored_documents.append(
            {
                "name": safe_name,
                "required_document_name": file_payload.get("required_document_name", safe_name),
                "storage_provider": "local",
                "storage_path": "",
                "storage_status": "local_filesystem",
                "storage_fallback": True,
                "local_path": str(local_path),
                "content_type": file_payload.get("content_type", ""),
                "size": int(file_payload.get("size", 0) or 0),
                "uploaded_at": _utc_now(),
                "text_excerpt": _extract_document_excerpt(file_payload),
                "extraction_method": str(file_payload.get("extraction_method", "Direct text extraction (pdfplumber)")),
                "extracted_fields": file_payload.get("extracted_fields", {}),
            }
        )
    return stored_documents


def _allow_local_document_fallback() -> bool:
    raw_value = str(os.getenv("ALLOW_LOCAL_DOCUMENT_FALLBACK", "true")).strip().lower()
    return raw_value not in {"0", "false", "no", "off"}


def _store_single_document_for_application(
    user_doc: dict[str, object],
    loan_id: str,
    file_payload: dict[str, object],
) -> dict[str, object]:
    safe_name = str(file_payload.get("name", "document")).replace("\\", "_").replace("/", "_")
    required_document_name = file_payload.get("required_document_name", safe_name)
    file_bytes = file_payload.get("bytes", b"")
    if not isinstance(file_bytes, bytes):
        file_bytes = b""

    try:
        storage_path = upload_to_supabase(
            user_uid=str(user_doc.get("uid", "")),
            loan_id=str(loan_id),
            filename=safe_name,
            file_bytes=file_bytes,
            content_type=str(file_payload.get("content_type", "")),
        )
    except SupabaseStorageError as exc:
        if _allow_local_document_fallback():
            fallback_docs = _save_documents_to_local_storage(
                str(user_doc.get("uid", "unknown-user")),
                str(loan_id),
                [file_payload],
            )
            if fallback_docs:
                fallback_docs[0]["storage_provider"] = "local"
                fallback_docs[0]["storage_error"] = str(exc)
                return fallback_docs[0]
        raise FirebaseServiceError(str(exc)) from exc

    return {
        "name": safe_name,
        "required_document_name": required_document_name,
        "storage_provider": "supabase",
        "storage_path": storage_path,
        "download_url": "",
        "storage_status": "uploaded",
        "content_type": file_payload.get("content_type", ""),
        "size": int(file_payload.get("size", 0) or 0),
        "uploaded_at": _utc_now(),
        "text_excerpt": _extract_document_excerpt(file_payload),
        "extraction_method": str(file_payload.get("extraction_method", "Direct text extraction (pdfplumber)")),
        "extracted_fields": file_payload.get("extracted_fields", {}),
    }


def sign_in_user(email: str, password: str, expected_role: str) -> dict[str, object]:
    auth_payload = _firebase_auth_request(
        "signInWithPassword",
        {"email": email, "password": password, "returnSecureToken": True},
    )
    uid = auth_payload.get("localId", "")
    user_doc = _get_user_document_by_email(email)
    if not user_doc and uid:
        user_doc = _get_user_document_by_uid(uid)

    if not user_doc:
        # Recover from split state where Firebase Auth account exists but Firestore user profile is missing.
        recovered_profile = {
            "uid": uid,
            "email": email,
            "role": expected_role,
            "app_namespace": _current_namespace(),
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
        }
        if expected_role == "company":
            recovered_profile["company_profile"] = {
                "company_name": "",
                "industry": "",
                "location": "",
                "annual_revenue": 0.0,
            }
        _set_user_profile(uid, recovered_profile)
        user_doc = recovered_profile

    # If namespace changed between runs, self-heal the user document to current namespace.
    namespace = _current_namespace()
    if namespace and str(user_doc.get("app_namespace", "")).strip() != namespace:
        _set_user_profile(uid, {"app_namespace": namespace, "updated_at": _utc_now()})
        user_doc["app_namespace"] = namespace

    if user_doc.get("role") != expected_role:
        raise FirebaseServiceError("This account is registered with a different role.")

    return {
        "uid": uid,
        "email": email,
        "role": user_doc.get("role"),
        "profile": user_doc,
        "id_token": auth_payload.get("idToken", ""),
    }


def register_company_user(email: str, password: str) -> dict[str, object]:
    auth_payload = _firebase_auth_request(
        "signUp",
        {"email": email, "password": password, "returnSecureToken": True},
    )
    uid = auth_payload.get("localId", "")
    profile = {
        "uid": uid,
        "email": email,
        "role": "company",
        "app_namespace": _current_namespace(),
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "company_profile": {
            "company_name": "",
            "industry": "",
            "location": "",
            "annual_revenue": 0.0,
        },
    }
    _set_user_profile(uid, profile)
    return {"uid": uid, "email": email, "role": "company", "profile": profile}


def register_officer_user(
    email: str,
    password: str,
    full_name: str,
    bank_name: str,
    branch_location: str,
    employee_id: str,
    designation: str,
) -> dict[str, object]:
    auth_payload = _firebase_auth_request(
        "signUp",
        {"email": email, "password": password, "returnSecureToken": True},
    )
    uid = auth_payload.get("localId", "")
    profile = {
        "uid": uid,
        "email": email,
        "role": "credit_officer",
        "app_namespace": _current_namespace(),
        "full_name": full_name,
        "bank_name": bank_name,
        "branch_location": branch_location,
        "employee_id": employee_id,
        "designation": designation,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
    }
    _set_user_profile(uid, profile)
    return {"uid": uid, "email": email, "role": "credit_officer", "profile": profile}


def get_company_profile(email: str) -> dict[str, object]:
    user_doc = _get_user_document_by_email(email)
    if not user_doc:
        raise FirebaseServiceError("Company profile not found.")
    return user_doc.get(
        "company_profile",
        {"company_name": "", "industry": "", "location": "", "annual_revenue": 0.0},
    )


def save_company_profile(email: str, profile: dict[str, object]) -> dict[str, object]:
    user_doc = _get_user_document_by_email(email)
    if not user_doc:
        raise FirebaseServiceError("Company profile not found.")
    _set_user_profile(
        user_doc["uid"],
        {
            "company_profile": profile,
            "updated_at": _utc_now(),
        },
    )
    return profile


def upload_application_documents(email: str, loan_id: str, uploaded_files: list[dict[str, object]]) -> list[dict[str, object]]:
    user_doc = _get_user_document_by_email(email)
    if not user_doc:
        raise FirebaseServiceError("Company account not found.")

    stored_documents = []

    for file_payload in uploaded_files:
        file_bytes = file_payload.get("bytes", b"")
        if not isinstance(file_bytes, bytes):
            continue
        safe_name = str(file_payload.get("name", "document")).replace("\\", "_").replace("/", "_")
        try:
            storage_path = upload_to_supabase(
                user_uid=str(user_doc.get("uid", "")),
                loan_id=str(loan_id),
                filename=safe_name,
                file_bytes=file_bytes,
                content_type=str(file_payload.get("content_type", "")),
            )
        except SupabaseStorageError as exc:
            if _allow_local_document_fallback():
                fallback_docs = _save_documents_to_local_storage(
                    str(user_doc.get("uid", "unknown-user")),
                    str(loan_id),
                    [file_payload],
                )
                if fallback_docs:
                    fallback_docs[0]["storage_provider"] = "local"
                    fallback_docs[0]["storage_error"] = str(exc)
                    stored_documents.extend(fallback_docs)
                    continue
            raise FirebaseServiceError(str(exc)) from exc

        stored_documents.append(
            {
                "name": safe_name,
                "required_document_name": file_payload.get("required_document_name", safe_name),
                "storage_provider": "supabase",
                "storage_path": storage_path,
                "download_url": "",
                "storage_status": "uploaded",
                "content_type": file_payload.get("content_type", ""),
                "size": int(file_payload.get("size", 0) or 0),
                "uploaded_at": _utc_now(),
                "text_excerpt": _extract_document_excerpt(file_payload),
                "extraction_method": str(file_payload.get("extraction_method", "Direct text extraction (pdfplumber)")),
                "extracted_fields": file_payload.get("extracted_fields", {}),
            }
        )
    if not stored_documents:
        raise FirebaseServiceError("No valid documents were uploaded to Supabase Storage.")
    return stored_documents


def list_company_applications(email: str) -> list[dict]:
    def _fetch_apps():
        docs = _applications_collection().where("user_email", "==", email).stream()
        namespace = _current_namespace()
        applications = []
        for doc in docs:
            payload = doc.to_dict()
            if namespace and str(payload.get("app_namespace", "")).strip() != namespace:
                continue
            payload["id"] = doc.id
            applications.append(payload)
        return sorted(applications, key=lambda app: app.get("created_at", ""), reverse=True)
    
    return _wrap_google_cloud_call(_fetch_apps)


def submit_application(email: str, application: dict[str, object], company_profile: dict[str, object]) -> dict[str, object]:
    user_doc = _get_user_document_by_email(email)
    if not user_doc:
        raise FirebaseServiceError("Company account not found.")

    payload = {
        **application,
        "app_namespace": _current_namespace(),
        "user_uid": user_doc["uid"],
        "user_email": email,
        "company_name": company_profile.get("company_name", "") or email,
        "industry": company_profile.get("industry", ""),
        "location": company_profile.get("location", ""),
        "status": "under_review",
        "risk_score": application.get("risk_score", 0),
        "document_flags": application.get("document_flags", {}),
        "officer_decision": None,
        "officer_remarks": "",
        "officer_notes": "",
        "decided_at": None,
        "ai_analysis": application.get("ai_analysis", {}),
        "email_log": application.get(
            "email_log",
            {
                "officer_notified_at": None,
                "seeker_notified_at": None,
                "notification_status": "",
            },
        ),
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
    }
    doc_ref = _applications_collection().document()
    def _save_app():
        doc_ref.set(payload)
    _wrap_google_cloud_call(_save_app)
    payload["id"] = doc_ref.id
    return payload


def update_application_analysis(app_id: str, analysis: dict[str, object]) -> None:
    snapshot = _wrap_google_cloud_call(_applications_document(app_id).get)
    current_status = "under_review"
    if snapshot.exists:
        current_status = str((snapshot.to_dict() or {}).get("status", "under_review"))
    safe_status = current_status if current_status in {"approved", "rejected", "conditional"} else "under_review"

    _wrap_google_cloud_call(
        _applications_document(app_id).set,
        {
            "ai_analysis": analysis,
            "financial_summary": analysis.get("financial_summary", {}),
            "risk_score": analysis.get("shield_score", 0),
            "risk_signals": analysis.get("risk_signals", []),
            "ai_recommendation": analysis.get("ai_recommendation", ""),
            "ai_reason": analysis.get("ai_reason", ""),
            "missing_documents": analysis.get("missing_documents", []),
            "document_summary": analysis.get("document_summary", ""),
            "agent_status": analysis.get("agent_status", "completed"),
            "risk_level": analysis.get("risk_level", ""),
            "default_probability": analysis.get("default_probability", 0.0),
            "shield_components": analysis.get("shield_components", {}),
            "shield_flags": analysis.get("shield_flags", {}),
            "news_summary": analysis.get("news_summary", {}),
            "news_signals": analysis.get("news_signals", {}),
            "cam_text": analysis.get("cam_text", ""),
            "status": safe_status,
            "officer_decision": None,
            "officer_remarks": "",
            "officer_notes": "",
            "decided_at": None,
            "analysis_generated_at": _utc_now(),
            "updated_at": _utc_now(),
        },
        merge=True,
    )


def run_agent_analysis_for_application(app_id: str) -> dict[str, object]:
    snapshot = _wrap_google_cloud_call(_applications_document(app_id).get)
    if not snapshot.exists:
        raise FirebaseServiceError("Application not found.")

    application = snapshot.to_dict()
    analysis = analyze_application(application)
    update_application_analysis(app_id, analysis)
    return analysis


def list_officer_applications(bank_name: str | None = None) -> list[dict]:
    def _fetch_apps():
        query = _applications_collection()
        if bank_name:
            query = query.where("assigned_bank_name", "==", bank_name)
        
        namespace = _current_namespace()
        applications = []
        for doc in query.stream():
            payload = doc.to_dict()
            if namespace and str(payload.get("app_namespace", "")).strip() != namespace:
                continue
            payload["id"] = doc.id
            applications.append(payload)
        return sorted(applications, key=lambda app: app.get("created_at", ""), reverse=True)
    
    return _wrap_google_cloud_call(_fetch_apps)


def list_registered_officer_emails() -> list[str]:
    def _fetch_emails():
        namespace = _current_namespace()
        query = _users_collection().where("role", "==", "credit_officer")
        emails: list[str] = []
        for doc in query.stream():
            payload = doc.to_dict() or {}
            if namespace and str(payload.get("app_namespace", "")).strip() != namespace:
                continue
            email = str(payload.get("email", "")).strip().lower()
            if email:
                emails.append(email)
        return sorted(set(emails))
    
    return _wrap_google_cloud_call(_fetch_emails)


def update_officer_decision(
    app_id: str,
    decision: str,
    remarks: str,
    officer_email: str,
    sanctioned_amount: float | int | None = None,
) -> None:
    normalized_decision = str(decision or "").strip().lower()
    if normalized_decision not in {"approved", "rejected", "conditional"}:
        raise FirebaseServiceError("Invalid officer decision.")

    decided_at = firestore.SERVER_TIMESTAMP if firestore is not None else _utc_now()
    
    def _update_decision():
        _applications_collection().document(app_id).set(
            {
                "officer_decision": normalized_decision,
                "officer_remarks": remarks,
                "officer_notes": remarks,
                "sanctioned_amount": float(sanctioned_amount or 0),
                "status": normalized_decision,
                "reviewed_by": officer_email,
                "decided_at": decided_at,
                "updated_at": _utc_now(),
            },
            merge=True,
        )
    
    _wrap_google_cloud_call(_update_decision)


def update_application_email_log(
    app_id: str,
    notification_target: str,
    status: str,
) -> None:
    target = str(notification_target or "").strip().lower()
    normalized_status = "sent" if str(status or "").strip().lower() == "sent" else "failed"
    now_value = firestore.SERVER_TIMESTAMP if firestore is not None else _utc_now()

    email_log_payload: dict[str, object] = {
        "notification_status": normalized_status,
        "last_notification_target": target,
        "updated_at": _utc_now(),
    }
    if target == "officer":
        email_log_payload["officer_notified_at"] = now_value
    elif target == "seeker":
        email_log_payload["seeker_notified_at"] = now_value

    def _update_log():
        _applications_collection().document(app_id).set(
            {"email_log": email_log_payload},
            merge=True,
        )
    
    _wrap_google_cloud_call(_update_log)


def save_document_review_flags(
    app_id: str,
    document_flags: dict[str, dict[str, object]],
    officer_email: str,
) -> None:
    reviewed_at = _utc_now()
    normalized_flags: dict[str, dict[str, object]] = {}
    for doc_name, payload in (document_flags or {}).items():
        current = dict(payload or {})
        current["reviewed_by"] = officer_email
        current["reviewed_at"] = reviewed_at
        normalized_flags[doc_name] = current

    has_action_required = any(
        str(flag.get("status", "")).strip() in {"Incorrect", "Missing", "Needs Resubmission"}
        for flag in normalized_flags.values()
    )

    payload = {
        "document_flags": normalized_flags,
        "status": "conditional" if has_action_required else "under_review",
        "officer_decision": "conditional" if has_action_required else None,
        "officer_remarks": "Document corrections requested." if has_action_required else "",
        "reviewed_by": officer_email,
        "updated_at": reviewed_at,
    }
    def _save_flags():
        _applications_collection().document(app_id).set(payload, merge=True)
    
    _wrap_google_cloud_call(_save_flags)


def get_document_preview_link(document: dict[str, object], expiry_minutes: int = 30) -> str | None:
    storage_provider = str(document.get("storage_provider", "")).strip().lower()
    storage_path = str(document.get("storage_path", "")).strip()
    if storage_provider == "supabase" and storage_path:
        try:
            return get_supabase_signed_url(storage_path, expires=max(60, int(expiry_minutes) * 60))
        except Exception:
            return None

    existing_url = str(document.get("download_url", "")).strip()
    if existing_url:
        return existing_url

    if not storage_path:
        return None

    try:
        bucket = get_storage_bucket()
        blob = bucket.blob(storage_path)
        link = _wrap_google_cloud_call(
            blob.generate_signed_url,
            expiration=timedelta(minutes=max(1, int(expiry_minutes))),
            method="GET",
        )
        return str(link)
    except Exception:
        return None


def migrate_legacy_document_links() -> dict[str, int]:
    """
    One-time migration:
    - Uploads legacy local files (when `local_path` exists) to Supabase Storage and writes
      `storage_provider` + `storage_path` back to Firestore.
    - Leaves old Firebase-based records intact and backward compatible.
    """
    def _perform_migration():
        namespace = _current_namespace()
        apps = _applications_collection().stream()
        
        scanned_apps = 0
        updated_apps = 0
        migrated_docs = 0
        skipped_docs = 0
        failed_docs = 0

        for app_snapshot in apps:
            payload = app_snapshot.to_dict() or {}
            if namespace and str(payload.get("app_namespace", "")).strip() != namespace:
                continue

            scanned_apps += 1
            documents = list(payload.get("documents", []) or [])
            if not documents:
                continue

            app_changed = False
            user_uid = str(payload.get("user_uid", "")).strip() or "legacy-user"
            loan_id = str(payload.get("loan_id", "legacy-loan")).strip() or "legacy-loan"

            for idx, document in enumerate(documents):
                doc_payload = dict(document or {})
                if str(doc_payload.get("download_url", "")).strip():
                    skipped_docs += 1
                    continue

                try:
                    provider = str(doc_payload.get("storage_provider", "")).strip().lower()
                    storage_path = str(doc_payload.get("storage_path", "")).strip()
                    if provider == "supabase" and storage_path:
                        skipped_docs += 1
                        continue

                    if storage_path and provider in {"firebase", "gcs"}:
                        skipped_docs += 1
                        continue

                    if storage_path and provider == "":
                        # Keep old records compatible; treat them as legacy Firebase path.
                        skipped_docs += 1
                        continue

                    local_path_value = str(doc_payload.get("local_path", "")).strip()
                    if local_path_value:
                        local_file = Path(local_path_value)
                        if not local_file.exists():
                            failed_docs += 1
                            continue
                        file_bytes = local_file.read_bytes()
                        safe_name = str(doc_payload.get("name", local_file.name)).replace("\\", "_").replace("/", "_")
                        new_storage_path = upload_to_supabase(
                            user_uid=user_uid,
                            loan_id=loan_id,
                            filename=safe_name,
                            file_bytes=file_bytes,
                            content_type=str(doc_payload.get("content_type", "")),
                        )
                        doc_payload["storage_provider"] = "supabase"
                        doc_payload["storage_path"] = new_storage_path
                        doc_payload["download_url"] = ""
                        doc_payload["storage_status"] = "uploaded"
                        documents[idx] = doc_payload
                        app_changed = True
                        migrated_docs += 1
                        continue

                    skipped_docs += 1
                except SupabaseStorageError:
                    failed_docs += 1
                except Exception:
                    failed_docs += 1

            if app_changed:
                _applications_document(app_snapshot.id).set(
                    {"documents": documents, "updated_at": _utc_now()},
                    merge=True,
                )
                updated_apps += 1

        return {
            "scanned_apps": scanned_apps,
            "updated_apps": updated_apps,
            "migrated_docs": migrated_docs,
            "skipped_docs": skipped_docs,
            "failed_docs": failed_docs,
        }
    
    return _wrap_google_cloud_call(_perform_migration)


def resubmit_flagged_document(
    app_id: str,
    applicant_email: str,
    required_document_name: str,
    file_payload: dict[str, object],
) -> None:
    snapshot = _wrap_google_cloud_call(_applications_document(app_id).get)
    if not snapshot.exists:
        raise FirebaseServiceError("Application not found.")

    application = snapshot.to_dict()
    if str(application.get("user_email", "")).strip().lower() != applicant_email.strip().lower():
        raise FirebaseServiceError("You can only update your own application documents.")

    user_doc = _get_user_document_by_email(applicant_email)
    if not user_doc:
        raise FirebaseServiceError("Company account not found.")

    file_payload = dict(file_payload)
    file_payload["required_document_name"] = required_document_name
    replacement_doc = _store_single_document_for_application(user_doc, str(application.get("loan_id", "loan")), file_payload)

    documents = list(application.get("documents", []) or [])
    updated_documents = []
    replaced = False
    for doc in documents:
        doc_required_name = str(doc.get("required_document_name", "")).strip().lower()
        if doc_required_name == required_document_name.strip().lower():
            updated_documents.append(replacement_doc)
            replaced = True
        else:
            updated_documents.append(doc)
    if not replaced:
        updated_documents.append(replacement_doc)

    uploaded_documents = list(application.get("uploaded_documents", []) or [])
    if required_document_name not in uploaded_documents:
        uploaded_documents.append(required_document_name)

    document_flags = dict(application.get("document_flags", {}) or {})
    flag_payload = dict(document_flags.get(required_document_name, {}) or {})
    flag_payload["status"] = "Resubmitted"
    flag_payload["resubmitted_at"] = _utc_now()
    document_flags[required_document_name] = flag_payload

    extraction_method = dict(application.get("extraction_method", {}) or {})
    extraction_method[required_document_name] = replacement_doc.get(
        "extraction_method", "Direct text extraction (pdfplumber)"
    )

    _wrap_google_cloud_call(
        _applications_document(app_id).set,
        {
            "documents": updated_documents,
            "uploaded_documents": uploaded_documents,
            "document_flags": document_flags,
            "extraction_method": extraction_method,
            "status": "under_review",
            "officer_decision": None,
            "officer_remarks": "",
            "officer_notes": "",
            "decided_at": None,
            "updated_at": _utc_now(),
        },
        merge=True,
    )


def get_officer_profile(email: str) -> dict[str, object]:
    user_doc = _get_user_document_by_email(email)
    if not user_doc:
        raise FirebaseServiceError("Credit officer profile not found.")
    return user_doc


def save_officer_profile(email: str, profile: dict[str, object]) -> dict[str, object]:
    user_doc = _get_user_document_by_email(email)
    if not user_doc:
        raise FirebaseServiceError("Credit officer profile not found.")
    if str(user_doc.get("role", "")).strip() != "credit_officer":
        raise FirebaseServiceError("Only credit officer profiles can be updated here.")

    payload = {
        "full_name": str(profile.get("full_name", "")).strip(),
        "bank_name": "HDFC Bank",
        "branch_location": str(profile.get("branch_location", "")).strip(),
        "employee_id": str(profile.get("employee_id", "")).strip(),
        "designation": str(profile.get("designation", "")).strip(),
        "updated_at": _utc_now(),
    }
    _set_user_profile(str(user_doc.get("uid", "")), payload)
    refreshed = _get_user_document_by_uid(str(user_doc.get("uid", "")))
    return refreshed or {**user_doc, **payload}
