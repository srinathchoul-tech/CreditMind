import streamlit as st

def initialize_state() -> None:
    defaults = {
        "logged_in": False,
        "role": None,
        "user_email": "",
        "company_profile": {
            "company_name": "",
            "industry": "",
            "location": "",
            "annual_revenue": 0.0,
        },
        "uploaded_files": [],
        "uploaded_files_by_loan": {},
        "uploaded_file_payloads_by_loan": {},
        "applications": [],
        "selected_bank": None,
        "selected_loan_product": None,
        "current_page": "Dashboard",
        "language": "English",
        "theme_mode": "Light",
        "show_signup": False,
        "user_id": "",
        "user_uid": "",
        "officer_profile": {},
        "officer_current_page": "Dashboard",
        "officer_applications": [],
        "selected_officer_app_id": None,
        "firebase": {
            "enabled": False,
            "provider": "firebase",
            "web_config": {},
            "missing_keys": [],
            "project_id": "",
            "auth_domain": "",
            "storage_bucket": "",
            "analytics_enabled": False,
            "auth_ready": False,
            "admin_ready": False,
            "service_account_loaded": False,
            "note": "",
        },
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
