import time

import streamlit as st

from data import OFFICER_BANKS
from firebase_service import (
    FirebaseServiceError,
    get_company_profile,
    get_officer_profile,
    list_company_applications,
    list_officer_applications,
    register_company_user,
    register_officer_user,
    save_company_profile,
    sign_in_user,
)
from ui_helpers import normalize_email, t


def _firebase_ready() -> bool:
    return bool(st.session_state.firebase.get("enabled"))


def _firebase_setup_message() -> str:
    firebase_state = st.session_state.firebase
    missing_web_keys = firebase_state.get("missing_keys", [])
    setup_lines = []

    if missing_web_keys:
        setup_lines.append(
            "Missing Firebase web config keys: " + ", ".join(missing_web_keys)
        )

    if not firebase_state.get("service_account_loaded"):
        setup_lines.append(
            "Missing Firebase service account. Set either FIREBASE_SERVICE_ACCOUNT_JSON or FIREBASE_SERVICE_ACCOUNT_PATH in .env."
        )

    if not setup_lines:
        setup_lines.append("Firebase configuration is incomplete.")

    return " ".join(setup_lines)


def login_success(role: str, email: str, uid: str = "", profile: dict | None = None) -> None:
    normalized_email_value = normalize_email(email)
    st.session_state.logged_in = True
    st.session_state.role = role
    st.session_state.user_email = normalized_email_value
    st.session_state.user_id = normalized_email_value
    st.session_state.user_uid = uid
    st.session_state.company_dashboard_loaded = False
    st.session_state.officer_dashboard_loaded = False
    with st.spinner("Loading your dashboard..."):
        if role == "company":
            st.session_state.page = "applicant"
            st.session_state.current_page = "Dashboard"
            st.session_state.company_profile = (
                profile.get("company_profile", {}) if profile else get_company_profile(normalized_email_value)
            ) or {
                "company_name": "",
                "industry": "",
                "location": "",
                "annual_revenue": 0.0,
            }
            st.session_state.applications = list_company_applications(normalized_email_value)
        else:
            st.session_state.page = "officer"
            st.session_state.officer_current_page = "Dashboard"
            st.session_state.officer_profile = profile or get_officer_profile(normalized_email_value)
            st.session_state.officer_applications = list_officer_applications(None)
    st.session_state.show_signup = False
    st.rerun()


def perform_logout() -> None:
    with st.spinner("Signing you out securely..."):
        st.session_state.logged_in = False
        st.session_state.role = None
        st.session_state.page = "landing"
        st.session_state.auth_mode = "login"
        st.session_state.user_email = ""
        st.session_state.user_id = ""
        st.session_state.user_uid = ""
        st.session_state.company_profile = {
            "company_name": "",
            "industry": "",
            "location": "",
            "annual_revenue": 0.0,
        }
        st.session_state.applications = []
        st.session_state.officer_profile = {}
        st.session_state.officer_applications = []
        st.session_state.company_dashboard_loaded = False
        st.session_state.officer_dashboard_loaded = False
        time.sleep(0.8)
    st.info("You have been logged out.")
    st.rerun()


def render_login() -> None:
    if "auth_inflight" not in st.session_state:
        st.session_state.auth_inflight = False
    if "auth_error_message" not in st.session_state:
        st.session_state.auth_error_message = ""
    if "auth_request" not in st.session_state:
        st.session_state.auth_request = {}
    if "auth_mode" not in st.session_state:
        st.session_state.auth_mode = "login"
    if "auth_role" not in st.session_state:
        st.session_state.auth_role = "company"

    st.markdown(f"<div class='portal-title'>{t('portal_title')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='section-title'>{t('login_title')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='body-muted'>{t('login_help')}</div>", unsafe_allow_html=True)

    if st.session_state.auth_error_message:
        st.error(st.session_state.auth_error_message)
        st.session_state.auth_error_message = ""

    if not _firebase_ready():
        st.warning(_firebase_setup_message())
        with st.expander("Firebase setup needed", expanded=True):
            st.markdown(
                "Add one of these to `.env` and restart Streamlit:\n"
                "1. `FIREBASE_SERVICE_ACCOUNT_PATH=C:\\path\\to\\serviceAccount.json`\n"
                "2. `FIREBASE_SERVICE_ACCOUNT_JSON={...full json...}`"
            )
            st.caption(
                "You already have the Firebase web config. The only missing piece right now is the service account credential for Firestore and Storage access."
            )

    _, mid, _ = st.columns([0.9, 1.7, 0.9])
    login_mount = mid.empty()

    if st.session_state.auth_inflight and st.session_state.auth_request:
        login_mount.empty()
        request_payload = st.session_state.auth_request
        with login_mount.container(border=True):
            with st.spinner("Verifying credentials, please wait..."):
                time.sleep(0.35)
            try:
                with st.spinner("Logging you in..."):
                    signed_in = sign_in_user(
                        str(request_payload.get("email", "")),
                        str(request_payload.get("password", "")),
                        str(request_payload.get("role", "company")),
                    )
            except FirebaseServiceError as exc:
                st.session_state.auth_inflight = False
                st.session_state.auth_request = {}
                st.session_state.auth_error_message = str(exc)
                st.rerun()
            st.success("Login successful! Redirecting...")
            time.sleep(1)
            st.session_state.auth_inflight = False
            st.session_state.auth_request = {}
            login_success(
                str(request_payload.get("role", "company")),
                str(request_payload.get("email", "")),
                signed_in["uid"],
                signed_in.get("profile"),
            )
        return

    with login_mount.container(border=True):
        default_role_index = 1 if st.session_state.auth_role == "credit_officer" else 0
        role_label = st.radio(
            t("role"),
            [t("role_company"), t("role_officer")],
            horizontal=True,
            index=default_role_index,
        )
        selected_role = "company" if role_label == t("role_company") else "credit_officer"
        st.session_state.auth_role = selected_role
        st.session_state.show_signup = st.session_state.auth_mode == "signup"
        email = st.text_input(t("email"), placeholder="name@email.com")
        password = st.text_input(t("password"), type="password")

        c1, c2 = st.columns(2)
        with c1:
            login_clicked = st.button(
                t("login_btn"),
                disabled=(not _firebase_ready()) or st.session_state.auth_inflight,
            )
        with c2:
            signup_clicked = st.button(
                t("signup_btn"),
                disabled=((not _firebase_ready()) and selected_role == "company") or st.session_state.auth_inflight,
            )

        if signup_clicked:
            st.session_state.show_signup = True
            st.session_state.auth_mode = "signup"

        if login_clicked:
            normalized_email_value = normalize_email(email)
            if not _firebase_ready():
                st.error("Firebase is not ready. Add a service account and try again.")
            elif not normalized_email_value or not password.strip():
                st.error(t("login_error"))
            else:
                st.session_state.auth_mode = "login"
                st.session_state.auth_inflight = True
                st.session_state.auth_request = {
                    "role": selected_role,
                    "email": normalized_email_value,
                    "password": password.strip(),
                }
                st.rerun()

        if st.session_state.show_signup and selected_role == "company":
            st.markdown("---")
            st.markdown("<div class='section-title'>Loan Seeker Sign Up</div>", unsafe_allow_html=True)
            with st.form("company_signup_form", clear_on_submit=True):
                applicant_name = st.text_input(t("company_name"))
                industry = st.text_input(t("industry"))
                location = st.text_input(t("location"))
                annual_revenue = st.number_input(
                    t("annual_revenue"),
                    min_value=100000.0,
                    value=1000000.0,
                    step=100000.0,
                )
                signup_email = st.text_input(t("email"))
                signup_password = st.text_input(t("password"), type="password")
                created = st.form_submit_button(t("signup_btn"), disabled=not _firebase_ready())
                if created:
                    normalized_signup_email = normalize_email(signup_email)
                    if not _firebase_ready():
                        st.error(" Service account is required before loan seeker sign up can work.")
                    elif (
                        applicant_name.strip()
                        and industry.strip()
                        and location.strip()
                        and normalized_signup_email
                        and signup_password.strip()
                    ):
                        try:
                            with st.spinner("Creating your account..."):
                                registered = register_company_user(normalized_signup_email, signup_password.strip())
                                save_company_profile(
                                    normalized_signup_email,
                                    {
                                        "company_name": applicant_name.strip(),
                                        "industry": industry.strip(),
                                        "location": location.strip(),
                                        "annual_revenue": annual_revenue,
                                    },
                                )
                            st.success("Loan seeker profile created. You can now log in.")
                            time.sleep(1)
                            st.session_state.auth_mode = "login"
                            login_success("company", registered["email"], registered["uid"])
                        except FirebaseServiceError as exc:
                            st.error(str(exc))
                    else:
                        st.error("Please fill all required fields.")

        if st.session_state.show_signup and selected_role == "credit_officer":
            st.markdown("---")
            st.markdown(f"<div class='section-title'>{t('officer_signup_title')}</div>", unsafe_allow_html=True)
            with st.form("officer_signup_form", clear_on_submit=True):
                full_name = st.text_input(t("full_name"))
                su_email = st.text_input(t("email"))
                su_password = st.text_input(t("password"), type="password")
                bank_name = OFFICER_BANKS[0]
                st.caption(f"{t('bank_name')}: {bank_name}")
                branch = st.text_input(t("branch_location"))
                employee_id = st.text_input(t("employee_id"))
                designation = st.text_input(t("designation"))
                created = st.form_submit_button(t("signup_btn"), disabled=not _firebase_ready())
                if created:
                    normalized_signup_email = normalize_email(su_email)
                    if not _firebase_ready():
                        st.error(" Service account is required before officer sign up can work.")
                    elif full_name.strip() and normalized_signup_email and su_password.strip() and branch.strip():
                        try:
                            with st.spinner("Creating your account..."):
                                register_officer_user(
                                    normalized_signup_email,
                                    su_password.strip(),
                                    full_name.strip(),
                                    bank_name,
                                    branch.strip(),
                                    employee_id.strip(),
                                    designation.strip(),
                                )
                            st.success(t("officer_created"))
                            st.toast("Officer account created.")
                            st.session_state.auth_mode = "login"
                        except FirebaseServiceError as exc:
                            st.error(str(exc))
                    else:
                        st.error(t("fill_required_fields"))


def show_auth_page() -> None:
    render_login()
