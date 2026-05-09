import streamlit as st
import time
import os

from auth import perform_logout
from data import COMPANY_UPLOAD_TYPES, LOAN_PRODUCTS
from firebase_service import (
    FirebaseServiceError,
    list_registered_officer_emails,
    list_company_applications,
    resubmit_flagged_document,
    run_agent_analysis_for_application,
    save_company_profile,
    submit_application,
    update_application_email_log,
    upload_application_documents,
)
from tools import build_upload_payload, derive_key_fields_for_document
from ui_helpers import get_loan_label, get_loan_product, render_top_nav, t
from supabase_notifications import invoke_notification, supabase_email_notifications_enabled


def get_required_document_names(product: dict) -> list[str]:
    return [doc["name"] for doc in product["required_documents"]]


def _document_label(doc: dict) -> str:
    suffix = "" if doc.get("mandatory", False) else " (Optional)"
    return f"{doc['name']}{suffix}"


def get_tenure_options(max_tenure_months: int) -> list[int]:
    if max_tenure_months <= 12:
        return list(range(6, max_tenure_months + 1, 1))
    return list(range(12, max_tenure_months + 1, 6))


def get_tenure_year_options(max_tenure_months: int) -> list[int]:
    max_years = max(1, int(max_tenure_months // 12))
    return list(range(1, max_years + 1))


def format_rupee_crore(amount: float | int | None) -> str:
    numeric_amount = float(amount or 0)
    if numeric_amount <= 0:
        return t("not_available")
    crore_value = numeric_amount / 10_000_000
    return f"Rs.{numeric_amount:,.0f} ({crore_value:.2f} Cr)"


def format_loan_amount(amount: float | int | None) -> str:
    numeric_amount = float(amount or 0)
    return t("not_available") if numeric_amount <= 0 else format_rupee_crore(numeric_amount)


def _normalize_status(status: str | None) -> str:
    value = str(status or "").strip().lower()
    if value in {"pending", "under review"}:
        return "under_review"
    if value in {"approved", "rejected", "conditional", "under_review"}:
        return value
    return "under_review"


def _format_datetime(raw_value: object) -> str:
    value = str(raw_value or "").strip()
    return value.replace("T", " ").replace("Z", " UTC") if value else t("not_available")


def _render_application_status_banner(application: dict) -> None:
    status = _normalize_status(application.get("status"))
    remarks = str(application.get("officer_remarks", "") or "").strip()
    decided_at = _format_datetime(application.get("decided_at"))

    if status == "under_review":
        st.warning("Pending: Your application is under review by a Credit Officer.")
        return
    if status == "approved":
        st.success(
            f"Approved. Remarks: {remarks or 'No remarks provided.'} | Decided At: {decided_at}"
        )
        return
    if status == "rejected":
        st.error(
            f"Rejected. Remarks: {remarks or 'No remarks provided.'} | Decided At: {decided_at}"
        )
        return
    if status == "conditional":
        st.info(
            f"Action Required. Officer Note: {remarks or 'Please re-upload requested documents.'} | "
            f"Decided At: {decided_at}"
        )


def render_extraction_transparency(documents: list[dict]) -> None:
    with st.expander("How your documents were read"):
        if not documents:
            st.info("No uploaded documents available for extraction review.")
            return
        for doc in documents:
            doc_type = doc.get("required_document_name", doc.get("name", "Document"))
            st.write(f"**{doc_type}** - {doc.get('name', '-')}")
            st.caption(f"Extraction method: {doc.get('extraction_method', 'Direct text extraction (pdfplumber)')}")
            fields = doc.get("extracted_fields", {}) or {}
            if not fields:
                st.table([{"Field": "Primary Field", "Value": "Not found in document"}])
                continue
            st.table([{"Field": key, "Value": value} for key, value in fields.items()])


def run_analysis_with_progress(application_id: str) -> None:
    progress = st.progress(0)
    status = st.empty()
    try:
        status.text("Reading your documents...")
        progress.progress(20)
        time.sleep(0.35)

        status.text("Calculating financial ratios...")
        progress.progress(45)
        time.sleep(0.35)

        status.text("Checking news and litigation signals...")
        progress.progress(65)
        time.sleep(0.35)

        status.text("Generating risk score...")
        progress.progress(80)
        with st.spinner("Running AI analysis on your documents..."):
            run_agent_analysis_for_application(application_id)

        status.text("Writing Credit Appraisal Memo...")
        progress.progress(95)
        time.sleep(0.35)

        progress.progress(100)
        status.text("Done!")
        time.sleep(0.5)
    finally:
        progress.empty()
        status.empty()


def _render_conditional_resubmission_controls(application: dict, key_prefix: str) -> None:
    status = _normalize_status(application.get("status"))
    if status != "conditional":
        return

    required_documents = application.get("required_documents", []) or []
    if not required_documents:
        required_documents = ["Updated Document"]

    selected_doc_type = st.selectbox(
        "Select document to re-upload",
        required_documents,
        key=f"{key_prefix}_doc_type_{application.get('id', '')}",
    )
    uploader = st.file_uploader(
        f"Upload updated file for {selected_doc_type}",
        type=["pdf", "png", "jpg", "jpeg", "tiff", "bmp", "docx", "xlsx", "xlsm", "csv", "txt", "json"],
        accept_multiple_files=False,
        key=f"{key_prefix}_uploader_{application.get('id', '')}",
    )
    if st.button("Re-upload for Re-Review", key=f"{key_prefix}_resubmit_{application.get('id', '')}"):
        if uploader is None:
            st.error("Please select a file before submitting.")
            return
        try:
            payload = build_upload_payload(uploader)
            with st.spinner("Uploading your documents to secure storage..."):
                resubmit_flagged_document(
                    app_id=application["id"],
                    applicant_email=st.session_state.user_email,
                    required_document_name=selected_doc_type,
                    file_payload=payload,
                )
                st.session_state.applications = list_company_applications(st.session_state.user_email)
            st.success("Document re-uploaded successfully. Application moved back to under review.")
            st.toast("Document resubmitted.")
            st.rerun()
        except FirebaseServiceError as exc:
            st.error(str(exc))


def build_company_sidebar() -> None:
    with st.sidebar:
        st.caption(t("loan_seeker_portal"))
        st.caption(f"{t('signed_in_as')}: {st.session_state.user_id}")

        nav_items = [
            (t("dashboard"), "Dashboard"),
            (t("profile"), "Company Profile"),
            (t("discovery"), "Loan Discovery"),
            (t("apps_results"), "Applications / Results"),
        ]
        for idx, (label, page_key) in enumerate(nav_items):
            is_active = st.session_state.current_page == page_key
            if st.button(label, key=f"company_nav_{idx}", type="primary" if is_active else "secondary"):
                st.session_state.current_page = page_key
                st.rerun()
        if st.button(t("logout"), key="logout_company", type="secondary"):
            perform_logout()


def compute_mock_risk_score(application: dict | None = None) -> int:
    latest = application
    if latest is None and not st.session_state.applications:
        return 0
    if latest is None:
        latest = st.session_state.applications[0]
    amount = latest["loan_amount"]
    base = 72
    if amount > 1_000_000:
        base -= 15
    if latest["tenure"] > 36:
        base -= 8
    return max(35, base)


def render_dashboard() -> None:
    company_name = st.session_state.company_profile.get("company_name", "").strip() or t("default_applicant")
    st.markdown(f"<div class='portal-title'>{t('welcome')}, {company_name}</div>", unsafe_allow_html=True)

    overview_tab, activity_tab, quick_actions_tab = st.tabs(
        [t("overview_tab"), t("activity_tab"), t("quick_actions_tab")]
    )

    with overview_tab, st.container(border=True):
        c1, c2, c3 = st.columns(3)
        c1.metric(t("total_apps"), len(st.session_state.applications))
        c2.metric(t("active_loans"), max(0, len(st.session_state.applications) - 1))
        risk_value = compute_mock_risk_score()
        c3.metric(t("risk_score"), "N/A" if risk_value == 0 else f"{risk_value}/100")

    with activity_tab, st.container(border=True):
        if not st.session_state.applications:
            st.info(t("no_apps"))
        else:
            for idx, app in enumerate(st.session_state.applications, start=1):
                st.write(
                    f"{idx}. {app['loan_name']} | {format_loan_amount(app.get('loan_amount'))} | "
                    f"{len(app.get('uploaded_documents', []))} docs uploaded"
                )

    with quick_actions_tab, st.container(border=True):
        st.write(f"- {t('quick_action_profile')}")
        st.write("- Upload the required loan documents in the application flow")
        st.write(f"- {t('quick_action_discover')}")

    st.markdown("<div class='section-title'>My Applications</div>", unsafe_allow_html=True)
    with st.container(border=True):
        if st.button("Refresh Status", key="refresh_status_dashboard", type="secondary"):
            try:
                with st.spinner("Loading your dashboard..."):
                    st.session_state.applications = list_company_applications(st.session_state.user_email)
                st.rerun()
            except FirebaseServiceError as exc:
                st.error(str(exc))
        if not st.session_state.applications:
            st.info("No applications yet.")
            return
        for app in st.session_state.applications:
            with st.container(border=True):
                st.subheader(f"{app.get('loan_name', 'Loan Application')} ({app.get('id', '')})")
                st.write(f"**Loan Amount:** {format_loan_amount(app.get('loan_amount'))}")
                st.write(f"**Submitted At:** {_format_datetime(app.get('created_at'))}")
                _render_application_status_banner(app)
                _render_conditional_resubmission_controls(app, key_prefix="dashboard")


def render_company_profile() -> None:
    st.markdown(f"<div class='section-title'>{t('profile')}</div>", unsafe_allow_html=True)
    profile = st.session_state.company_profile
    with st.container(border=True):
        company_name = st.text_input(t("company_name"), value=profile["company_name"])
        industry = st.text_input(t("industry"), value=profile["industry"])
        location = st.text_input(t("location"), value=profile["location"])
        annual_revenue = st.number_input(
            t("annual_revenue"),
            min_value=100000.0,
            value=max(100000.0, float(profile["annual_revenue"] or 0.0)),
            step=100000.0,
        )
        if annual_revenue > 0:
            st.caption(f"Annual income display: {format_rupee_crore(annual_revenue)}")
        if st.button(t("save_profile")):
            updated_profile = {
                "company_name": company_name,
                "industry": industry,
                "location": location,
                "annual_revenue": annual_revenue,
            }
            try:
                st.session_state.company_profile = save_company_profile(st.session_state.user_email, updated_profile)
                st.success(t("profile_saved"))
            except FirebaseServiceError as exc:
                st.error(str(exc))
        if st.button("Send Test Email", key="company_test_email_btn", type="secondary"):
            try:
                from email_service import get_last_email_error, send_email

                with st.spinner("Sending test email..."):
                    sent = send_email(
                        st.session_state.user_email,
                        "CreditMind Test Email",
                        "<p>This is a test email from CreditMind.</p>",
                    )
                if sent:
                    st.success("Test email sent successfully.")
                else:
                    st.warning(f"Test email failed. Reason: {get_last_email_error() or 'Unknown SMTP error.'}")
            except Exception as exc:
                st.warning(f"Test email failed. Reason: {str(exc)}")


def render_loan_discovery() -> None:
    st.markdown(f"<div class='section-title'>{t('discovery')}</div>", unsafe_allow_html=True)
    for idx, product in enumerate(LOAN_PRODUCTS):
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            with c1:
                st.subheader(get_loan_label(product))
                st.write(f"**{t('bank')}:** {product['bank_name']}")
                st.write(f"**{t('loan_description')}:** {product['description']}")
                st.write(f"**{t('loan_purpose')}:** {product['purpose']}")
                st.write(f"**{t('typical_amount')}:** {product['typical_amount']}")
                st.write(f"**{t('interest_rate')}:** {product['interest_rate']}")
                st.write(f"**{t('max_loan')}:** {format_rupee_crore(product['max_amount'])}")
                st.write(f"**{t('tenure')}:** {product['tenure_text']}")
                st.write(f"**{t('key_features')}:**")
                for feature in product["features"]:
                    st.write(f"- {feature}")
                st.write(f"**{t('required_documents')}:**")
                for doc in product["required_documents"]:
                    st.write(f"- {_document_label(doc)}")
            with c2:
                if st.button(t("apply"), key=f"apply_btn_{idx}"):
                    st.session_state.selected_loan_product = product["id"]
                    st.session_state.current_page = "Applications / Results"
                    st.rerun()


def build_application_analysis(application: dict) -> tuple[list[str], str]:
    risk_signals = []
    if application["loan_amount"] > 1_000_000:
        risk_signals.append(t("risk_high_amount"))
    if application["tenure"] > 36:
        risk_signals.append(t("risk_long_tenure"))
    if not application["purpose"].strip():
        risk_signals.append(t("risk_purpose_limited"))
    if len(application.get("uploaded_documents", [])) < len(application.get("required_documents", [])):
        risk_signals.append(t("risk_docs_incomplete"))
    recommendation = t("approve") if len(risk_signals) < 2 else t("reject")
    if not risk_signals:
        risk_signals.append(t("risk_none"))
    return risk_signals, recommendation


def render_notifications_section() -> None:
    st.write("**Notifications:**")
    applications = st.session_state.applications or []
    if not applications:
        st.info("No applications found.")
        return

    actionable_statuses = {"Incorrect", "Missing", "Needs Resubmission"}
    any_notification = False

    for app in applications:
        document_flags = app.get("document_flags", {}) or {}
        if not document_flags:
            continue

        flagged_items = []
        for doc_type, flag_payload in document_flags.items():
            status = str((flag_payload or {}).get("status", "")).strip()
            if status in actionable_statuses or status == "Resubmitted":
                flagged_items.append((doc_type, flag_payload))
        if not flagged_items:
            continue

        any_notification = True
        with st.container(border=True):
            st.subheader(f"{app.get('loan_name', 'Loan Application')} ({app.get('id', '')})")
            st.write(f"**Current Status:** {app.get('status', 'Pending')}")
            for idx, (doc_type, flag_payload) in enumerate(flagged_items):
                status = str((flag_payload or {}).get("status", "")).strip() or "Action Required"
                note = str((flag_payload or {}).get("note", "")).strip() or "No officer note added."
                st.write(f"- **{doc_type}** | Status: {status}")
                st.caption(f"Officer Note: {note}")

                if status == "Resubmitted":
                    st.info(f"{doc_type} has been resubmitted and is pending officer re-review.")
                    continue

                upload_key = f"resubmit_doc_{app['id']}_{idx}"
                file_uploader = st.file_uploader(
                    f"Re-upload {doc_type}",
                    type=["pdf", "png", "jpg", "jpeg", "tiff", "bmp", "docx", "xlsx", "xlsm", "csv", "txt", "json"],
                    accept_multiple_files=False,
                    key=upload_key,
                )
                if st.button("Submit Re-upload", key=f"submit_resubmission_{app['id']}_{idx}"):
                    if file_uploader is None:
                        st.error("Please select a file before submitting.")
                    else:
                        try:
                            payload = build_upload_payload(file_uploader)
                            with st.spinner("Uploading your documents to secure storage..."):
                                resubmit_flagged_document(
                                    app_id=app["id"],
                                    applicant_email=st.session_state.user_email,
                                    required_document_name=doc_type,
                                    file_payload=payload,
                                )
                                st.session_state.applications = list_company_applications(st.session_state.user_email)
                            st.success(f"{doc_type} resubmitted successfully.")
                            st.toast("Application saved.")
                            st.rerun()
                        except FirebaseServiceError as exc:
                            st.error(str(exc))

    if not any_notification:
        st.info("No document flags at the moment.")


def render_applications_and_results() -> None:
    st.markdown(f"<div class='section-title'>{t('apps_results')}</div>", unsafe_allow_html=True)
    history_tab, analysis_tab = st.tabs([t("history_tab"), t("analysis_tab")])

    with history_tab, st.container(border=True):
        selected_product = get_loan_product(st.session_state.selected_loan_product)
        if selected_product:
            st.subheader(t("application_form"))
            st.write(f"**{t('selected_loan')}:** {get_loan_label(selected_product)}")
            st.write(f"**Document Set:** {', '.join(_document_label(doc) for doc in selected_product['required_documents'])}")
            with st.form("loan_application_form", clear_on_submit=True):
                requested_amount = st.number_input(
                    t("loan_amount"),
                    min_value=500000.0,
                    max_value=float(selected_product["max_amount"]),
                    value=min(float(selected_product["max_amount"]) * 0.25, float(selected_product["max_amount"])),
                    step=500000.0,
                )
                tenure_year_options = get_tenure_year_options(int(selected_product["tenure_months"]))
                selected_tenure_years = st.selectbox(
                    f"{t('tenure')} (Years)",
                    tenure_year_options,
                    index=len(tenure_year_options) - 1,
                    format_func=lambda years: f"{years} year{'s' if years != 1 else ''}",
                )
                purpose_text = st.text_area(
                    t("purpose"),
                    value=selected_product["purpose"],
                    height=90,
                )
                gst_applicable = not st.checkbox(
                    "Business is not GST registered (turnover below Rs.40L threshold)",
                    value=False,
                    key=f"gst_not_applicable_{selected_product['id']}",
                )
                document_payloads = []
                for doc in selected_product["required_documents"]:
                    if doc["name"] == "GST returns" and not gst_applicable:
                        continue
                    uploaded_file = st.file_uploader(
                        f"{_document_label(doc)} ({', '.join(doc['allowed_types']).upper()})",
                        type=doc["allowed_types"],
                        accept_multiple_files=False,
                        key=f"application_doc_{selected_product['id']}_{doc['name'].lower().replace('/', '_').replace(' ', '_')}",
                    )
                    if uploaded_file is not None:
                        payload = build_upload_payload(uploaded_file)
                        payload["required_document_name"] = doc["name"]
                        payload["extracted_fields"] = derive_key_fields_for_document(
                            doc["name"],
                            str(payload.get("text_excerpt", "")),
                        )
                        document_payloads.append(payload)
                submitted = st.form_submit_button(t("submit_app"))
                if submitted:
                    uploaded_docs = {file["required_document_name"] for file in document_payloads}
                    all_documents = [doc["name"] for doc in selected_product["required_documents"]]
                    mandatory_documents = [doc["name"] for doc in selected_product["required_documents"] if doc.get("mandatory")]
                    optional_documents = [doc["name"] for doc in selected_product["required_documents"] if not doc.get("mandatory")]
                    if not gst_applicable and "GST returns" in optional_documents:
                        optional_documents.remove("GST returns")
                    missing_mandatory = [name for name in mandatory_documents if name not in uploaded_docs]
                    if missing_mandatory:
                        st.error("Please upload all mandatory documents: " + ", ".join(missing_mandatory))
                    else:
                        try:
                            with st.spinner("Uploading your documents to secure storage..."):
                                stored_documents = upload_application_documents(
                                    st.session_state.user_email,
                                    selected_product["id"],
                                    document_payloads,
                                )
                            missing_docs = [name for name in optional_documents if name not in uploaded_docs]
                            extraction_method = {
                                doc["required_document_name"]: doc.get("extraction_method", "Direct text extraction (pdfplumber)")
                                for doc in stored_documents
                            }
                            application_payload = {
                                "loan_id": selected_product["id"],
                                "loan_name": get_loan_label(selected_product),
                                "loan_amount": requested_amount,
                                "purpose": purpose_text.strip() or selected_product["purpose"],
                                "tenure": int(selected_tenure_years) * 12,
                                "required_documents": all_documents,
                                "uploaded_documents": [doc["required_document_name"] for doc in stored_documents],
                                "documents": stored_documents,
                                "missing_docs": missing_docs,
                                "gst_applicable": gst_applicable,
                                "extraction_method": extraction_method,
                                "assigned_bank_name": selected_product["bank_name"],
                                "annual_revenue": st.session_state.company_profile.get("annual_revenue", 0.0),
                                "business_type": st.session_state.company_profile.get("business_type", ""),
                                "incorporation_date": st.session_state.company_profile.get("incorporation_date", ""),
                                "years_in_business": st.session_state.company_profile.get("years_in_business", None),
                                "owner_full_name": st.session_state.company_profile.get("owner_full_name", ""),
                                "business_name": st.session_state.company_profile.get("company_name", ""),
                                "financial_summary": {
                                    "revenue": t("not_available"),
                                    "profit": t("not_available"),
                                    "flags": [],
                                },
                                "risk_signals": [],
                                "ai_recommendation": "",
                                "ai_reason": "",
                                "document_summary": "",
                                "missing_documents": [],
                                "agent_status": "processing",
                                "risk_score": 0,
                                "document_flags": {},
                                "officer_notes": "",
                                "officer_decision": None,
                                "officer_remarks": "",
                                "decided_at": None,
                                "status": "under_review",
                                "ai_analysis": {},
                            }
                            application_payload["risk_score"] = compute_mock_risk_score(application_payload)
                            saved_application = submit_application(
                                st.session_state.user_email,
                                application_payload,
                                st.session_state.company_profile,
                            )
                            configured_officer_email = os.getenv("OFFICER_EMAIL", "").strip().lower()
                            officer_recipients = set(list_registered_officer_emails())
                            if configured_officer_email:
                                officer_recipients.add(configured_officer_email)

                            notification_sent = False
                            notification_note = ""
                            if supabase_email_notifications_enabled():
                                with st.spinner("Notifying credit officer..."):
                                    notify_result = invoke_notification(
                                        "new_application",
                                        {
                                            "application_id": saved_application["id"],
                                            "app_namespace": saved_application.get("app_namespace", ""),
                                            "applicant_name": st.session_state.company_profile.get("company_name", "") or st.session_state.user_email,
                                            "business_name": application_payload.get("business_name", ""),
                                            "loan_amount": application_payload.get("loan_amount", 0),
                                            "officer_recipients": sorted(officer_recipients),
                                            "officer_email_fallback": configured_officer_email,
                                        },
                                    )
                                notification_sent = bool(notify_result.get("ok"))
                                notification_note = str(notify_result.get("error", "")).strip()
                                update_application_email_log(
                                    saved_application["id"],
                                    "officer",
                                    "sent" if notification_sent else "failed",
                                )
                            elif os.getenv("SENDER_EMAIL", "").strip() and officer_recipients:
                                with st.spinner("Notifying credit officer..."):
                                    from email_service import get_last_email_error, notify_officer_new_application

                                    sent_count = 0
                                    for officer_email in sorted(officer_recipients):
                                        if notify_officer_new_application(
                                            officer_email=officer_email,
                                            applicant_name=st.session_state.company_profile.get("company_name", "") or st.session_state.user_email,
                                            business_name=application_payload.get("business_name", ""),
                                            loan_amount=application_payload.get("loan_amount", 0),
                                            application_id=saved_application["id"],
                                        ):
                                            sent_count += 1
                                    notification_sent = sent_count > 0
                                    if not notification_sent:
                                        notification_note = get_last_email_error() or "Unable to send notification email."
                                update_application_email_log(
                                    saved_application["id"],
                                    "officer",
                                    "sent" if notification_sent else "failed",
                                )
                            else:
                                update_application_email_log(saved_application["id"], "officer", "failed")
                                if not officer_recipients:
                                    notification_note = "No credit officer email found in Firestore users collection."
                                else:
                                    notification_note = "Sender email credentials are not configured."

                            run_analysis_with_progress(saved_application["id"])
                            with st.spinner("Loading your dashboard..."):
                                st.session_state.applications = list_company_applications(st.session_state.user_email)
                            st.success(
                                "Application submitted successfully. Your application is under review by a Credit Officer."
                            )
                            st.toast("Application saved.")
                            if notification_sent:
                                st.toast("Credit officer has been notified.")
                            else:
                                st.caption(
                                    "Email notification could not be sent. Officer will still see your application in the portal. "
                                    f"Reason: {notification_note or 'Unknown SMTP error.'}"
                                )
                        except FirebaseServiceError as exc:
                            st.error(str(exc))
        else:
            st.info(t("no_loan_selected"))

        if st.session_state.applications:
            st.markdown(f"### {t('saved_applications')}")
            for i, app in enumerate(st.session_state.applications, start=1):
                st.write(
                    f"{i}. {app['loan_name']} | {format_loan_amount(app.get('loan_amount'))} | "
                    f"{len(app.get('uploaded_documents', []))} docs uploaded"
                )
        else:
            st.info(t("no_apps"))

    with analysis_tab, st.container(border=True):
        if not st.session_state.applications:
            st.warning(t("no_apps"))
            return
        if st.button("Refresh Status", key="refresh_status_analysis", type="secondary"):
            try:
                with st.spinner("Loading your dashboard..."):
                    st.session_state.applications = list_company_applications(st.session_state.user_email)
                st.rerun()
            except FirebaseServiceError as exc:
                st.error(str(exc))

        render_notifications_section()
        st.divider()
        latest = st.session_state.applications[0]
        st.subheader(f"{latest.get('loan_name', 'Application')} ({latest.get('id', '')})")
        st.write(f"**Loan Amount:** {format_loan_amount(latest.get('loan_amount'))}")
        st.write(f"**Submitted At:** {_format_datetime(latest.get('created_at'))}")
        _render_application_status_banner(latest)
        _render_conditional_resubmission_controls(latest, key_prefix="analysis")
        st.write("**Uploaded Documents:**")
        for doc in latest.get("documents", []) or []:
            st.write(f"- {doc.get('required_document_name', doc.get('name', 'Document'))}: {doc.get('name', '-')}")
        if latest.get("missing_docs"):
            st.write(f"**Missing Optional Documents:** {', '.join(latest.get('missing_docs', []))}")
        render_extraction_transparency(latest.get("documents", []) or [])


def render_company_ui() -> None:
    if not st.session_state.get("company_dashboard_loaded", False):
        try:
            with st.spinner("Loading your dashboard..."):
                st.session_state.applications = list_company_applications(st.session_state.user_email)
                st.session_state.company_dashboard_loaded = True
            st.success("Dashboard loaded.")
        except FirebaseServiceError as exc:
            st.error(str(exc))
    render_top_nav()
    build_company_sidebar()
    renderers = {
        "Dashboard": render_dashboard,
        "Company Profile": render_company_profile,
        "Loan Discovery": render_loan_discovery,
        "Applications / Results": render_applications_and_results,
    }
    renderers.get(st.session_state.current_page, render_dashboard)()
