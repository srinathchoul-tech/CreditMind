import json
import os
from pathlib import Path
import streamlit as st
from env_loader import load_env_file

# Optional dotenv support for local development
try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None

if load_dotenv is not None:
    try:
        loaded = load_dotenv()
        if not loaded:
            load_env_file()
    except Exception:
        load_env_file()
else:
    load_env_file()


REQUIRED_FIREBASE_ENV_VARS = {
    "apiKey": "FIREBASE_API_KEY",
    "authDomain": "FIREBASE_AUTH_DOMAIN",
    "projectId": "FIREBASE_PROJECT_ID",
    "storageBucket": "FIREBASE_STORAGE_BUCKET",
    "messagingSenderId": "FIREBASE_MESSAGING_SENDER_ID",
    "appId": "FIREBASE_APP_ID",
    "measurementId": "FIREBASE_MEASUREMENT_ID",
}


def _get_config_value(key: str) -> str:
    """Retrieve configuration from Streamlit secrets or environment variables."""
    try:
        if key in st.secrets:
            return str(st.secrets[key]).strip()
    except Exception:
        pass

    return os.getenv(key, "").strip()


def get_firebase_web_config() -> dict[str, str]:
    """Retrieve Firebase Web SDK configuration."""
    return {
        config_key: _get_config_value(env_key)
        for config_key, env_key in REQUIRED_FIREBASE_ENV_VARS.items()
    }


def get_missing_firebase_env_vars() -> list[str]:
    """Identify missing Firebase configuration keys."""
    config = get_firebase_web_config()
    return [key for key, value in config.items() if not value]


def get_app_namespace() -> str:
    """Retrieve application namespace."""
    return _get_config_value("APP_NAMESPACE")


def get_firebase_service_account() -> dict | None:
    """Retrieve Firebase service account credentials."""
    # Priority 1: Streamlit Secrets
    try:
        if "FIREBASE_SERVICE_ACCOUNT_JSON" in st.secrets:
            service_account = st.secrets["FIREBASE_SERVICE_ACCOUNT_JSON"]

            # If already parsed as a dictionary
            if isinstance(service_account, dict):
                return service_account

            # If stored as a string
            if isinstance(service_account, str):
                return json.loads(service_account)
    except Exception:
        # No Streamlit secrets file or invalid secret format.
        pass

    # Priority 2: Environment variable (for local development)
    raw_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    if raw_json:
        try:
            return json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "FIREBASE_SERVICE_ACCOUNT_JSON is not valid JSON. Verify the service account payload in your .env file."
            ) from exc

    # Priority 3: Local file path (for local development only)
    service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "").strip()
    if service_account_path:
        candidate_paths = []
        expanded_path = os.path.expanduser(service_account_path)
        candidate_paths.append(Path(expanded_path))
        if not Path(expanded_path).is_absolute():
            candidate_paths.append(Path.cwd() / expanded_path)
            candidate_paths.append(Path(__file__).resolve().parent / expanded_path)

        for candidate in candidate_paths:
            try:
                if candidate.exists():
                    with open(candidate, "r", encoding="utf-8") as file:
                        return json.load(file)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Service account file {candidate} contains invalid JSON."
                ) from exc
            except Exception:
                continue

    return None


def initialize_firebase() -> dict[str, object]:
    """Initialize Firebase configuration status."""
    web_config = get_firebase_web_config()
    missing = get_missing_firebase_env_vars()
    service_account = get_firebase_service_account()

    auth_ready = not missing
    admin_ready = service_account is not None

    return {
        "enabled": auth_ready and admin_ready,
        "provider": "firebase",
        "web_config": web_config,
        "missing_keys": missing,
        "project_id": web_config.get("projectId", ""),
        "auth_domain": web_config.get("authDomain", ""),
        "storage_bucket": web_config.get("storageBucket", ""),
        "analytics_enabled": bool(web_config.get("measurementId")),
        "auth_ready": auth_ready,
        "admin_ready": admin_ready,
        "service_account_loaded": admin_ready,
        "service_account": service_account,
        "note": (
            "Firebase web config and service account are loaded."
            if auth_ready and admin_ready
            else "Firebase is missing required configuration for full auth and Firestore access."
        ),
    }