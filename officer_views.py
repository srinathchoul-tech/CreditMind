import html
import json
import os
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

from auth import perform_logout
from cam_pdf import build_cam_pdf_bytes
from firebase_service import (
    FirebaseServiceError,
    get_document_preview_link,
    list_officer_applications,
    migrate_legacy_document_links,
    save_officer_profile,
    save_document_review_flags,
    update_application_email_log,
    update_officer_decision,
)
from supabase_notifications import invoke_notification, supabase_email_notifications_enabled
from ui_helpers import render_top_nav, t


def format_loan_amount(amount: float | int | None) -> str:
    numeric_amount = float(amount or 0)
    return t("not_available") if numeric_amount <= 0 else f"Rs.{numeric_amount:,.0f}"


def refresh_officer_applications(show_feedback: bool = True) -> None:
    try:
        if show_feedback:
            with st.spinner("Fetching pending applications..."):
                # Single-bank setup: every officer should see every application.
                st.session_state.officer_applications = list_officer_applications(None)
            st.success("Applications refreshed.")
            return
        # Single-bank setup: every officer should see every application.
        st.session_state.officer_applications = list_officer_applications(None)
    except FirebaseServiceError as exc:
        st.error(str(exc))


def build_officer_sidebar() -> None:
    with st.sidebar:
        st.caption(t("credit_officer_portal"))
        st.caption(f"{t('signed_in_as')}: {st.session_state.user_id}")
        if st.button("Refresh Applications", key="refresh_officer_apps", type="secondary"):
            refresh_officer_applications()
            st.rerun()
        if st.button("Migrate Legacy Document Links", key="migrate_legacy_docs", type="secondary"):
            try:
                with st.spinner("Migrating legacy document links..."):
                    result = migrate_legacy_document_links()
                refresh_officer_applications()
                st.success(
                    "Migration completed. "
                    f"Apps scanned: {result.get('scanned_apps', 0)}, "
                    f"Apps updated: {result.get('updated_apps', 0)}, "
                    f"Docs migrated: {result.get('migrated_docs', 0)}, "
                    f"Docs skipped: {result.get('skipped_docs', 0)}, "
                    f"Docs failed: {result.get('failed_docs', 0)}"
                )
                st.rerun()
            except FirebaseServiceError as exc:
                st.error(str(exc))

        nav_items = [
            (t("dashboard"), "Dashboard"),
            (t("assigned_apps"), "Assigned Applications"),
            (t("app_review"), "Application Review"),
            (t("risk_insights"), "Risk Insights"),
            (t("officer_profile"), "Profile"),
        ]
        for idx, (label, page_key) in enumerate(nav_items):
            is_active = st.session_state.officer_current_page == page_key
            if st.button(label, key=f"officer_nav_{idx}", type="primary" if is_active else "secondary"):
                st.session_state.officer_current_page = page_key
                st.rerun()
        if st.button(t("logout"), key="logout_officer", type="secondary"):
            perform_logout()


def render_officer_dashboard() -> None:
    name = st.session_state.officer_profile.get("full_name", t("default_officer_name"))
    st.markdown(f"<div class='portal-title'>{t('welcome')}, {name}</div>", unsafe_allow_html=True)
    apps = st.session_state.officer_applications
    total = len(apps)
    pending = sum(1 for app in apps if str(app.get("status", "")).lower() == "under_review")
    approved = sum(1 for app in apps if str(app.get("status", "")).lower() == "approved")
    rejected = sum(1 for app in apps if str(app.get("status", "")).lower() == "rejected")
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t("total_apps"), total)
        c2.metric(t("pending_reviews"), pending)
        c3.metric(t("approved"), approved)
        c4.metric(t("rejected"), rejected)


def render_assigned_applications() -> None:
    st.markdown("<div class='section-title'>Officer Review Queue</div>", unsafe_allow_html=True)
    apps = [app for app in st.session_state.officer_applications if str(app.get("status", "")).lower() == "under_review"]
    if not apps:
        st.info("No applications currently under review.")
        return
    for app in apps:
        ai_analysis = app.get("ai_analysis", {}) or {}
        with st.container(border=True):
            c1, c2 = st.columns([4, 1.2])
            with c1:
                st.subheader(f"{app['company_name']} ({app['id']})")
                st.write(f"**Applicant:** {app.get('company_name', t('not_available'))}")
                st.write(f"**Loan Amount:** {format_loan_amount(app.get('loan_amount'))}")
                st.write(f"**Submission Date:** {str(app.get('created_at', t('not_available'))).replace('T', ' ').replace('Z', ' UTC')}")
                st.write(f"**AI Risk Score:** {ai_analysis.get('shield_score', app.get('risk_score', 0))}/100")
                st.write(f"**AI Recommendation:** {ai_analysis.get('ai_recommendation', app.get('ai_recommendation', t('not_available')))}")
            with c2:
                if st.button("Open Full Review", key=f"review_{app['id']}"):
                    st.session_state.selected_officer_app_id = app["id"]
                    st.session_state.officer_current_page = "Application Review"
                    st.rerun()


def get_selected_officer_application() -> dict | None:
    selected_id = st.session_state.selected_officer_app_id
    for app in st.session_state.officer_applications:
        if app["id"] == selected_id:
            return app
    return st.session_state.officer_applications[0] if st.session_state.officer_applications else None


def save_officer_decision(
    app_id: str,
    decision: str,
    remarks: str,
    sanctioned_amount: float | int | None = None,
) -> None:
    update_officer_decision(app_id, decision, remarks, st.session_state.user_email, sanctioned_amount)
    refresh_officer_applications(show_feedback=False)


def process_decision_and_notify(
    app: dict,
    decision: str,
    remarks: str,
    sanctioned_amount: float | int | None = None,
) -> tuple[bool, str]:
    with st.spinner("Saving your decision..."):
        save_officer_decision(app["id"], decision, remarks, sanctioned_amount)

    seeker_email = str(app.get("user_email", "")).strip()
    notification_sent = False
    notification_attempted = False
    email_status = "failed"
    email_failure_reason = ""

    if supabase_email_notifications_enabled():
        with st.spinner("Sending decision email to applicant..."):
            notify_result = invoke_notification(
                "decision_update",
                {
                    "application_id": app.get("id", ""),
                    "app_namespace": app.get("app_namespace", ""),
                    "seeker_email": seeker_email,
                    "applicant_name": str(app.get("company_name", "")).strip() or "Applicant",
                    "business_name": str(app.get("business_name", "")).strip() or str(app.get("company_name", "")).strip(),
                    "loan_amount": app.get("loan_amount", 0),
                    "decision": decision,
                    "officer_remarks": remarks,
                    "decided_at": datetime.now().strftime("%d %B %Y, %I:%M %p"),
                },
            )
        cloud_ok = bool(notify_result.get("ok"))
        update_application_email_log(app["id"], "seeker", "sent" if cloud_ok else "failed")
        if cloud_ok:
            return True, "Decision saved and applicant notified via email."
        return False, (
            "Decision recorded. Email notification failed - please inform the applicant manually. "
            f"Reason: {str(notify_result.get('error', '')).strip() or 'Supabase function error.'}"
        )

    try:
        if os.getenv("SENDER_EMAIL", "").strip() and seeker_email:
            notification_attempted = True
            with st.spinner("Sending decision email to applicant..."):
                from email_service import get_last_email_error, notify_seeker_decision

                notification_sent = notify_seeker_decision(
                    seeker_email=seeker_email,
                    applicant_name=str(app.get("company_name", "")).strip() or "Applicant",
                    business_name=str(app.get("business_name", "")).strip() or str(app.get("company_name", "")).strip(),
                    loan_amount=app.get("loan_amount", 0),
                    decision=decision,
                    officer_remarks=remarks,
                    decided_at=datetime.now().strftime("%d %B %Y, %I:%M %p"),
                )
            email_status = "sent" if notification_sent else "failed"
            if not notification_sent:
                email_failure_reason = get_last_email_error() or "Unknown SMTP error."
        update_application_email_log(app["id"], "seeker", email_status)
    except Exception:
        try:
            update_application_email_log(app["id"], "seeker", "failed")
        except Exception:
            pass
        notification_sent = False

    if notification_sent:
        return True, "Decision saved and applicant notified via email."
    if notification_attempted:
        return False, (
            "Decision recorded. Email notification failed - please inform the applicant manually. "
            f"Reason: {email_failure_reason or 'Unknown SMTP error.'}"
        )
    return False, "Decision recorded. Email settings are incomplete, so no email was sent."


def _format_uploaded_at(raw_value: str) -> str:
    value = str(raw_value or "").strip()
    if not value:
        return t("not_available")
    return value.replace("T", " ").replace("Z", " UTC")


def _render_light_json(title: str, payload: dict, key_prefix: str) -> None:
    if not payload:
        return
    pretty_json = json.dumps(payload, indent=2, ensure_ascii=False)
    st.write(f"**{title}:**")
    st.markdown(
        (
            f"<div class='light-json-block' id='{key_prefix}'>"
            f"<pre>{html.escape(pretty_json)}</pre>"
            f"</div>"
        ),
        unsafe_allow_html=True,
    )


def _render_light_code_block(title: str, text_value: str, key_prefix: str) -> None:
    content = str(text_value or "").strip()
    if not content:
        return
    st.write(f"**{title}:**")
    st.markdown(
        (
            f"<div class='light-code-block' id='{key_prefix}'>"
            f"<pre>{html.escape(content)}</pre>"
            f"</div>"
        ),
        unsafe_allow_html=True,
    )


def _render_news_litigation_signals(news_signals: dict) -> None:
    st.markdown("### News & Litigation Risk Signals")
    payload = news_signals or {}
    risk_level = str(payload.get("risk_level", "none")).strip().lower()
    case_type = str(payload.get("case_type", "")).strip().lower()
    points = [str(point).strip() for point in payload.get("points", []) if str(point).strip()][:4]

    if risk_level == "insufficient_history" or case_type == "new_company":
        st.info(
            "Business established recently — no news history available. "
            "Risk assessed primarily from financial documents."
        )
        st.caption("Note: News signals are supplementary. Officer must verify independently.")
        return

    if risk_level == "high" and points:
        body = "\n".join(f"• {point}" for point in points)
        st.error(body)
    elif risk_level == "medium" and points:
        body = "\n".join(f"• {point}" for point in points)
        st.warning(body)
    else:
        if case_type == "individual":
            st.success("No adverse news found for this individual.")
            st.caption(
                "Individual applicant — news signals may be limited. "
                "Credit officer to conduct additional background check if needed."
            )
        else:
            st.success("No significant legal or fraud news found for this business.")

    st.caption("Note: News signals are supplementary. Officer must verify independently.")


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return default


def _format_component_name(name: str) -> str:
    return str(name or "").replace("_", " ").title()


def _get_explainability_recommendation(ai_analysis: dict, documents: list[dict]) -> tuple[str, str]:
    score = _to_float(ai_analysis.get("shield_score", 0))
    confidence = _to_float(ai_analysis.get("confidence_score", 0))
    flags = ai_analysis.get("shield_flags", {}) or {}
    risk_level = str(ai_analysis.get("risk_level", "")).strip().upper()
    doc_count = len(documents or [])

    if score <= 35 and confidence >= 70 and not flags.get("gst_anomaly") and not flags.get("high_negative_news"):
        return "Approve candidate", "Low risk score, adequate confidence, and no major automated red flags."
    if score >= 70 or flags.get("high_negative_news"):
        return "Reject candidate", "High risk score or serious external/news signal requires strong caution."
    if confidence < 70 or doc_count < 3:
        return "Conditional candidate", "The automated score has limited confidence because document evidence is incomplete."
    return "Conditional candidate", "Medium risk or mixed signals should be resolved with officer remarks and document review."


def render_xai_decision_panel(app: dict, ai_analysis: dict) -> None:
    documents = app.get("documents", []) or []
    components = ai_analysis.get("shield_components", {}) or {}
    flags = ai_analysis.get("shield_flags", {}) or {}
    risk_signals = [str(item).strip() for item in ai_analysis.get("risk_signals", []) if str(item).strip()]
    confidence = _to_float(ai_analysis.get("confidence_score", 0))
    score = _to_float(ai_analysis.get("shield_score", app.get("risk_score", 0)))
    recommendation = str(ai_analysis.get("ai_recommendation", app.get("ai_recommendation", "Not available")) or "Not available")
    guidance_title, guidance_reason = _get_explainability_recommendation(ai_analysis, documents)

    st.markdown("### Explainable Decision View")
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("SHIELD Score", f"{score:.0f}/100")
        c2.metric("Risk Level", str(ai_analysis.get("risk_level", "N/A") or "N/A"))
        c3.metric("Confidence", f"{confidence:.0f}%")
        c4.metric("AI Recommendation", recommendation)

        if confidence < 70:
            st.warning(
                "Confidence is capped because documentation is limited. Treat this as assisted review, not final approval evidence."
            )
        else:
            st.success("Confidence is sufficient for officer review, subject to document verification.")

        st.write(f"**Decision Guidance:** {guidance_title}")
        st.caption(guidance_reason)

    c1, c2 = st.columns([1.1, 1])
    with c1, st.container(border=True):
        st.write("**Risk Score Breakdown:**")
        if components:
            chart_rows = {
                _format_component_name(key): _to_float(value)
                for key, value in components.items()
                if isinstance(value, (int, float)) and key != "bank_document_weight"
            }
            if chart_rows:
                st.bar_chart(chart_rows)
            for key, value in components.items():
                if key == "bank_document_weight":
                    st.write(f"- **Bank document weight:** {_to_float(value) * 100:.0f}%")
                else:
                    st.write(f"- **{_format_component_name(key)}:** {_to_float(value):.1f} risk points")
        else:
            st.info("Risk component breakdown is not available for this application.")

    with c2, st.container(border=True):
        st.write("**Top Explanation Reasons:**")
        if risk_signals:
            for signal in risk_signals[:6]:
                st.write(f"- {signal}")
        else:
            st.success("No major negative explanation signal was generated.")

        st.write("**Automated Flags:**")
        if flags:
            for key, value in flags.items():
                label = _format_component_name(key)
                if isinstance(value, bool):
                    st.write(f"- {label}: {'Yes' if value else 'No'}")
                else:
                    st.write(f"- {label}: {value}")
        else:
            st.caption("No structured flags available.")

    with st.expander("Evidence used by the model", expanded=True):
        rows = []
        for doc in documents:
            fields = doc.get("extracted_fields", {}) or {}
            rows.append(
                {
                    "Document": doc.get("required_document_name", doc.get("name", "Document")),
                    "Extraction Method": doc.get("extraction_method", "Direct text extraction (pdfplumber)"),
                    "Key Fields Found": ", ".join(
                        f"{key}: {value}" for key, value in fields.items() if str(value).strip()
                    )
                    or "No key field found",
                }
            )
        if rows:
            st.table(rows)
        else:
            st.info("No document evidence is attached.")

    st.caption(
        "XAI note: This panel explains the automated SHIELD recommendation. "
        "The final decision remains with the Credit Officer."
    )


def _render_local_document_download(document: dict, key: str) -> None:
    local_path_value = str(document.get("local_path", "")).strip()
    if not local_path_value:
        return
    local_file = Path(local_path_value)
    if not local_file.exists():
        st.caption("Local file path recorded, but file is not available on disk.")
        return
    try:
        file_bytes = local_file.read_bytes()
    except Exception:
        st.caption("Unable to read local document file.")
        return
    mime = str(document.get("content_type", "")).strip() or "application/octet-stream"
    st.download_button(
        label="Open / Download (legacy local file)",
        data=file_bytes,
        file_name=str(document.get("name", local_file.name)),
        mime=mime,
        key=key,
    )


def _build_review_rows(app: dict) -> list[dict]:
    documents = app.get("documents", []) or []
    required_documents = app.get("required_documents", []) or []
    docs_by_required = {}
    for doc in documents:
        key = str(doc.get("required_document_name", "")).strip().lower()
        if key and key not in docs_by_required:
            docs_by_required[key] = doc

    rows = []
    seen = set()
    for required_name in required_documents:
        normalized = str(required_name).strip().lower()
        matched_doc = docs_by_required.get(normalized)
        rows.append(
            {
                "required_document_name": required_name,
                "document": matched_doc,
            }
        )
        seen.add(normalized)

    for doc in documents:
        required_name = str(doc.get("required_document_name", doc.get("name", "Document"))).strip()
        normalized = required_name.lower()
        if normalized in seen:
            continue
        rows.append(
            {
                "required_document_name": required_name,
                "document": doc,
            }
        )
    return rows


def render_review_documents_section(app: dict) -> None:
    st.write("**Review Documents:**")
    rows = _build_review_rows(app)
    existing_flags = app.get("document_flags", {}) or {}
    status_options = ["OK", "Incorrect", "Missing", "Needs Resubmission"]

    if not rows:
        st.info("No document records found for this application.")
        return

    for idx, row in enumerate(rows):
        required_document_name = row["required_document_name"]
        document = row["document"] or {}
        doc_name = str(document.get("name", "")).strip() or "-"
        uploaded_at = _format_uploaded_at(str(document.get("uploaded_at", "")).strip())
        doc_type = required_document_name
        existing = existing_flags.get(required_document_name, {}) or {}
        default_status = str(existing.get("status", "OK")).strip()
        if default_status not in status_options:
            default_status = "OK"
        default_note = str(existing.get("note", "")).strip()

        with st.container(border=True):
            c1, c2 = st.columns([4, 1.8])
            with c1:
                st.write(f"**File Name:** {doc_name}")
                st.write(f"**Document Type:** {doc_type}")
                st.write(f"**Upload Date:** {uploaded_at}")
                preview_link = get_document_preview_link(document) if document else None
                if preview_link:
                    st.markdown(f"[Open Document]({preview_link})")
                elif document.get("local_path"):
                    _render_local_document_download(document, key=f"legacy_doc_download_{app['id']}_{idx}")
                else:
                    st.caption("Preview unavailable")
            with c2:
                selected_status = st.selectbox(
                    "Status",
                    status_options,
                    index=status_options.index(default_status),
                    key=f"doc_status_{app['id']}_{idx}",
                )
                note_value = st.text_area(
                    "Reason / Note",
                    value=default_note,
                    key=f"doc_note_{app['id']}_{idx}",
                    height=90,
                )
                st.session_state[f"doc_review_payload_{app['id']}_{idx}"] = {
                    "required_document_name": required_document_name,
                    "status": selected_status,
                    "note": note_value.strip(),
                }

    if st.button("Save Document Review", key=f"save_doc_review_{app['id']}"):
        try:
            review_payload = {}
            for idx, row in enumerate(rows):
                payload = st.session_state.get(f"doc_review_payload_{app['id']}_{idx}", {})
                required_document_name = payload.get("required_document_name", row["required_document_name"])
                review_payload[required_document_name] = {
                    "status": str(payload.get("status", "OK")).strip(),
                    "note": str(payload.get("note", "")).strip(),
                }
            with st.spinner("Saving your decision..."):
                save_document_review_flags(app["id"], review_payload, st.session_state.user_email)
            refresh_officer_applications()
            st.success("Document review saved.")
            st.toast("Review flags updated.")
            st.rerun()
        except FirebaseServiceError as exc:
            st.error(str(exc))

    with st.expander("How your documents were read"):
        documents = app.get("documents", []) or []
        if not documents:
            st.info("No uploaded documents available for extraction review.")
        for doc in documents:
            doc_type = doc.get("required_document_name", doc.get("name", "Document"))
            st.write(f"**{doc_type}** - {doc.get('name', '-')}")
            st.caption(f"Extraction method: {doc.get('extraction_method', 'Direct text extraction (pdfplumber)')}")
            fields = doc.get("extracted_fields", {}) or {}
            if not fields:
                st.table([{"Field": "Primary Field", "Value": "Not found in document"}])
            else:
                st.table([{"Field": key, "Value": value} for key, value in fields.items()])


def render_application_review() -> None:
    st.markdown(f"<div class='section-title'>{t('app_review')}</div>", unsafe_allow_html=True)
    app = get_selected_officer_application()
    if not app:
        st.info(t("no_assigned"))
        return

    with st.container(border=True):
        st.subheader(app["company_name"])
        st.write(f"**{t('application_id')}:** {app['id']}")
        st.write(f"**{t('company_details')}:**")
        st.write(f"- {t('company_name')}: {app['company_name']}")
        st.write(f"- {t('industry')}: {app['industry']}")
        st.write(f"- {t('location')}: {app['location']}")

    ai_analysis = app.get("ai_analysis", {}) or {}
    if not ai_analysis:
        ai_analysis = {
            "shield_score": app.get("risk_score", 0),
            "ai_recommendation": app.get("ai_recommendation", ""),
            "ai_reason": app.get("ai_reason", ""),
            "risk_level": app.get("risk_level", ""),
            "default_probability": app.get("default_probability", 0),
            "confidence_score": app.get("confidence_score", 0),
            "shield_components": app.get("shield_components", {}),
            "shield_flags": app.get("shield_flags", {}),
            "risk_signals": app.get("risk_signals", []),
            "financial_summary": app.get("financial_summary", {}),
            "document_summary": app.get("document_summary", ""),
            "news_summary": app.get("news_summary", {}),
            "news_signals": app.get("news_signals", {}),
            "cam_text": app.get("cam_text", ""),
        }

    render_xai_decision_panel(app, ai_analysis)

    with st.container(border=True):
        st.write("**AI Full Analysis:**")
        st.write(f"**SHIELD Score:** {ai_analysis.get('shield_score', 0)}/100")
        st.write(f"**AI Recommendation:** {ai_analysis.get('ai_recommendation', t('not_available'))}")
        st.write(f"**AI Reason:** {ai_analysis.get('ai_reason', t('not_available'))}")
        if ai_analysis.get("risk_level"):
            st.write(f"**Risk Level:** {ai_analysis.get('risk_level')}")
        if "default_probability" in ai_analysis:
            st.write(f"**Default Probability:** {float(ai_analysis.get('default_probability', 0) or 0):.2f}")
        if "confidence_score" in ai_analysis:
            st.write(f"**Confidence Score:** {float(ai_analysis.get('confidence_score', 0) or 0):.0f}%")
        if ai_analysis.get("risk_signals"):
            st.write("**Risk Signals:**")
            for signal in ai_analysis.get("risk_signals", []):
                st.write(f"- {signal}")
        _render_light_json("Financial Summary", ai_analysis.get("financial_summary", {}), key_prefix=f"fin_json_{app['id']}")
        _render_news_litigation_signals(ai_analysis.get("news_signals", {}) or ai_analysis.get("news_summary", {}).get("news_signals", {}))
        if ai_analysis.get("cam_text"):
            cam_text = str(ai_analysis.get("cam_text", ""))
            _render_light_code_block("CAM Report", cam_text, key_prefix=f"cam_block_{app['id']}")
            cam_pdf = build_cam_pdf_bytes(cam_text, title=f"CAM_{app.get('id', 'application')}")
            st.download_button(
                "Download CAM Report (PDF)",
                data=cam_pdf,
                file_name=f"CAM_{app.get('id', 'application')}.pdf",
                mime="application/pdf",
                key=f"cam_pdf_download_{app['id']}",
            )

    with st.container(border=True):
        st.write("**Uploaded Documents:**")
        render_review_documents_section(app)

    with st.container(border=True):
        remarks = st.text_area(
            "Officer Remarks (required)",
            value=str(app.get("officer_remarks", "") or ""),
            key=f"remarks_{app['id']}",
            height=120,
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("Approve", key=f"approve_{app['id']}"):
                try:
                    if not remarks.strip():
                        st.error("Remarks are required.")
                    else:
                        email_sent, message = process_decision_and_notify(
                            app,
                            "approved",
                            remarks,
                            app.get("loan_amount", 0),
                        )
                        if email_sent:
                            st.success(message)
                        else:
                            st.warning(message)
                        time.sleep(1)
                        st.rerun()
                except FirebaseServiceError as exc:
                    st.error(str(exc))
        with c2:
            if st.button("Reject", key=f"reject_{app['id']}"):
                try:
                    if not remarks.strip():
                        st.error("Remarks are required.")
                    else:
                        email_sent, message = process_decision_and_notify(
                            app,
                            "rejected",
                            remarks,
                            0,
                        )
                        if email_sent:
                            st.success(message)
                        else:
                            st.warning(message)
                        time.sleep(1)
                        st.rerun()
                except FirebaseServiceError as exc:
                    st.error(str(exc))
        with c3:
            if st.button("Conditional", key=f"conditional_{app['id']}"):
                try:
                    if not remarks.strip():
                        st.error("Remarks are required.")
                    else:
                        email_sent, message = process_decision_and_notify(
                            app,
                            "conditional",
                            remarks,
                            0,
                        )
                        if email_sent:
                            st.success(message)
                        else:
                            st.warning(message)
                        time.sleep(1)
                        st.rerun()
                except FirebaseServiceError as exc:
                    st.error(str(exc))


def render_risk_insights() -> None:
    st.markdown(f"<div class='section-title'>{t('risk_insights')}</div>", unsafe_allow_html=True)
    apps = st.session_state.officer_applications
    if not apps:
        st.info(t("no_assigned"))
        return
    avg_risk = sum(a["risk_score"] for a in apps) / len(apps)
    high_risk = sum(1 for a in apps if a["risk_score"] < 50)
    with st.container(border=True):
        c1, c2 = st.columns(2)
        c1.metric(t("avg_risk"), f"{avg_risk:.1f}/100")
        c2.metric(t("high_risk_count"), high_risk)
        chart_data = [app["risk_score"] for app in apps]
        st.bar_chart(chart_data)


def render_officer_profile() -> None:
    st.markdown(f"<div class='section-title'>{t('officer_profile')}</div>", unsafe_allow_html=True)
    profile = st.session_state.officer_profile
    with st.container(border=True):
        full_name = st.text_input(t("full_name"), value=profile.get("full_name", ""))
        bank_name = st.text_input(t("bank_name"), value="HDFC Bank", disabled=True)
        branch_location = st.text_input(t("branch_location"), value=profile.get("branch_location", ""))
        email = profile.get("email", st.session_state.user_email)
        st.write(f"**{t('email')}:** {email}")
        designation = st.text_input(t("designation"), value=profile.get("designation", ""))
        employee_id = st.text_input(t("employee_id"), value=profile.get("employee_id", ""))

        if st.button("Save Officer Profile", key="save_officer_profile_btn"):
            try:
                st.session_state.officer_profile = save_officer_profile(
                    st.session_state.user_email,
                    {
                        "full_name": full_name,
                        "bank_name": bank_name,
                        "branch_location": branch_location,
                        "designation": designation,
                        "employee_id": employee_id,
                    },
                )
                st.success("Officer profile updated.")
                st.rerun()
            except FirebaseServiceError as exc:
                st.error(str(exc))

        if st.button("Send Test Email", key="officer_test_email_btn", type="secondary"):
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


def render_officer_ui() -> None:
    if not st.session_state.get("officer_dashboard_loaded", False):
        try:
            with st.spinner("Loading your dashboard..."):
                st.session_state.officer_applications = list_officer_applications(None)
                st.session_state.officer_dashboard_loaded = True
            st.success("Dashboard loaded.")
        except FirebaseServiceError as exc:
            st.error(str(exc))
    render_top_nav()
    build_officer_sidebar()
    renderers = {
        "Dashboard": render_officer_dashboard,
        "Assigned Applications": render_assigned_applications,
        "Application Review": render_application_review,
        "Risk Insights": render_risk_insights,
        "Profile": render_officer_profile,
    }
    renderers.get(st.session_state.officer_current_page, render_officer_dashboard)()
