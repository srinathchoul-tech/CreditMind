import streamlit as st
from env_loader import load_env_file

# Optional dotenv support for local development
try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover
    load_dotenv = None

from applicant_portal import show_applicant_portal
from auth import show_auth_page
from firebase_config import initialize_firebase
from landing_page import show_landing_page
from officer_portal import show_officer_portal
from state import initialize_state
from styles import inject_theme_styles


# -------------------- PAGE CONFIGURATION --------------------
st.set_page_config(
    page_title="CreditMind Loan Portal",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------- LOAD ENVIRONMENT VARIABLES --------------------
if load_dotenv is not None:
    try:
        loaded = load_dotenv()
        if not loaded:
            load_env_file()
    except Exception:
        load_env_file()
else:
    load_env_file()


# -------------------- INITIALIZE FIREBASE SAFELY --------------------
def setup_firebase():
    """Initialize Firebase and store its status in session state."""
    try:
        st.session_state.firebase = initialize_firebase()
    except Exception as e:
        st.session_state.firebase = {
            "enabled": False,
            "error": str(e),
        }
        st.error("⚠️ Firebase initialization failed. Check your configuration.")
        st.exception(e)


# -------------------- MAIN APPLICATION --------------------
def main() -> None:
    # Initialize session state
    initialize_state()

    # Initialize Firebase
    setup_firebase()

    # Apply UI styles
    inject_theme_styles()

    # Default session values
    st.session_state.setdefault("page", "landing")
    st.session_state.setdefault("auth_mode", "login")
    st.session_state.setdefault("logged_in", False)

    # Determine requested page
    requested_page = str(st.session_state.page).strip().lower()

    # Restrict unauthorized access
    if requested_page in {"applicant", "officer"} and not st.session_state.logged_in:
        st.session_state.page = "auth"
        requested_page = "auth"

    # -------------------- ROUTING --------------------
    if requested_page == "landing":
        show_landing_page()

    elif requested_page == "auth":
        show_auth_page()

    elif requested_page == "officer":
        show_officer_portal()

    elif requested_page == "applicant":
        show_applicant_portal()

    else:
        st.session_state.page = "landing"
        show_landing_page()


# -------------------- ENTRY POINT --------------------
if __name__ == "__main__":
    main()