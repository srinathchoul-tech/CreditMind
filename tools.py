import csv
import io
import json
import os
import re
from typing import Any

from env_loader import load_env_file
from models import CompanyMeta
from parsers import extract_text_metadata
from research_agent import run_research_agent

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    load_dotenv = None


if load_dotenv is not None:
    load_dotenv()
else:
    load_env_file()


def _decode_text(raw_bytes: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return ""


def extract_text_from_upload(name: str, raw_bytes: bytes) -> str:
    lower_name = name.lower()
    if lower_name.endswith((".txt", ".csv", ".json", ".xml")):
        text = _decode_text(raw_bytes)
        if lower_name.endswith(".csv"):
            reader = csv.reader(io.StringIO(text))
            rows = [", ".join(cell.strip() for cell in row if cell.strip()) for row in reader]
            return "\n".join(rows)
        if lower_name.endswith(".json"):
            try:
                parsed = json.loads(text)
                return json.dumps(parsed, indent=2)
            except json.JSONDecodeError:
                return text
        return text
    if lower_name.endswith((".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".docx", ".xlsx", ".xlsm")):
        return extract_text_metadata(raw_bytes, filename=name).get("text", "")
    return ""


def derive_key_fields_for_document(required_document_name: str, text: str) -> dict[str, str]:
    lowered_type = str(required_document_name or "").strip().lower()
    normalized_text = str(text or "")

    def _find_amount(label: str, pattern: str) -> tuple[str, str]:
        match = re.search(pattern, normalized_text, flags=re.IGNORECASE)
        if not match:
            return label, "Not found in document"
        value = match.group(1).strip()
        return label, f"Rs.{value}"

    if "bank" in lowered_type:
        return dict(
            [
                _find_amount("Closing Balance", r"(?:closing\s+balance|balance)\D{0,12}(\d[\d,]*(?:\.\d+)?)"),
                _find_amount("Average Monthly Credit", r"(?:avg|average)\s+(?:monthly\s+)?credit\D{0,12}(\d[\d,]*(?:\.\d+)?)"),
            ]
        )
    if "itr" in lowered_type:
        return dict(
            [
                _find_amount("Total Income", r"(?:total\s+income)\D{0,12}(\d[\d,]*(?:\.\d+)?)"),
                _find_amount("Tax Paid", r"(?:tax\s+paid)\D{0,12}(\d[\d,]*(?:\.\d+)?)"),
            ]
        )
    if "balance" in lowered_type:
        return dict(
            [
                _find_amount("Total Debt", r"(?:total\s+debt|borrowings)\D{0,12}(\d[\d,]*(?:\.\d+)?)"),
                _find_amount("Equity", r"(?:equity|net\s+worth)\D{0,12}(\d[\d,]*(?:\.\d+)?)"),
            ]
        )
    if "pl" in lowered_type or "p&l" in lowered_type:
        return dict(
            [
                _find_amount("Revenue", r"(?:revenue|turnover)\D{0,12}(\d[\d,]*(?:\.\d+)?)"),
                _find_amount("Net Profit", r"(?:net\s+profit|profit\s+after\s+tax)\D{0,12}(\d[\d,]*(?:\.\d+)?)"),
            ]
        )
    if "gst" in lowered_type:
        return {
            "GSTR-2A Value": re.search(r"gstr[\s\-]*2a\D{0,12}(\d[\d,]*(?:\.\d+)?)", normalized_text, flags=re.IGNORECASE).group(1)
            if re.search(r"gstr[\s\-]*2a\D{0,12}(\d[\d,]*(?:\.\d+)?)", normalized_text, flags=re.IGNORECASE)
            else "Not found in document",
            "GSTR-3B Value": re.search(r"gstr[\s\-]*3b\D{0,12}(\d[\d,]*(?:\.\d+)?)", normalized_text, flags=re.IGNORECASE).group(1)
            if re.search(r"gstr[\s\-]*3b\D{0,12}(\d[\d,]*(?:\.\d+)?)", normalized_text, flags=re.IGNORECASE)
            else "Not found in document",
        }
    if "pan" in lowered_type or "kyc" in lowered_type:
        pan_match = re.search(r"\b[A-Z]{5}\d{4}[A-Z]\b", normalized_text)
        return {
            "PAN Number": pan_match.group(0) if pan_match else "Not found in document",
            "KYC Name": "Found" if re.search(r"name", normalized_text, flags=re.IGNORECASE) else "Not found in document",
        }

    return {"Primary Field": "Not found in document"}


def build_upload_payload(uploaded_file) -> dict[str, Any]:
    raw_bytes = uploaded_file.getvalue()
    extraction_metadata = extract_text_metadata(raw_bytes, filename=uploaded_file.name, content_type=uploaded_file.type or "")
    extracted_text = extraction_metadata.get("text", "")
    return {
        "name": uploaded_file.name,
        "content_type": uploaded_file.type or "",
        "size": len(raw_bytes),
        "bytes": raw_bytes,
        "text_excerpt": extracted_text[:2500],
        "extraction_method": extraction_metadata.get("extraction_method", "Direct text extraction (pdfplumber)"),
        "extracted_fields": {},
    }


def _match_uploaded_names(documents: list[dict[str, Any]]) -> set[str]:
    names = set()
    for doc in documents:
        name = str(doc.get("name", "")).lower()
        required_name = str(doc.get("required_document_name", "")).lower()
        names.add(name)
        if required_name:
            names.add(required_name)
    return names


def _find_missing_documents(required_documents: list[str], uploaded_documents: list[dict[str, Any]]) -> list[str]:
    uploaded_names = _match_uploaded_names(uploaded_documents)
    missing = []
    for required in required_documents:
        required_key = required.lower()
        if not any(token in name for name in uploaded_names for token in required_key.split()):
            missing.append(required)
    return missing


def _estimate_financial_summary(application: dict[str, Any]) -> dict[str, Any]:
    amount = float(application.get("loan_amount", 0) or 0)
    annual_income = float(application.get("annual_revenue", 0) or 0)
    estimated_revenue = annual_income if annual_income > 0 else max(amount * 2.25, 500000)
    estimated_profit = max(estimated_revenue * 0.14, amount * 0.08)
    flags = []
    if annual_income and amount > annual_income:
        flags.append("Requested amount exceeds declared annual income.")
    if not application.get("documents"):
        flags.append("Supporting documents are not attached.")
    return {
        "revenue": _format_rupee_crore_string(estimated_revenue),
        "profit": _format_rupee_crore_string(estimated_profit),
        "flags": flags,
    }


def _format_rupee_crore_string(amount: float) -> str:
    crore_value = amount / 10_000_000
    return f"Rs.{amount:,.0f} ({crore_value:.2f} Cr)"


def _build_document_summary(documents: list[dict[str, Any]]) -> str:
    if not documents:
        return "No uploaded documents were available for automated review."
    parts = []
    for doc in documents:
        excerpt = str(doc.get("text_excerpt", "")).strip()
        if excerpt:
            parts.append(f"{doc.get('name', 'document')}: {excerpt[:280]}")
        else:
            parts.append(f"{doc.get('name', 'document')}: uploaded successfully, text extraction unavailable.")
    return "\n".join(parts[:4])


def _heuristic_analysis(application: dict[str, Any]) -> dict[str, Any]:
    documents = application.get("documents", []) or []
    required_documents = application.get("required_documents", []) or []
    missing_documents = application.get("missing_docs", []) or _find_missing_documents(required_documents, documents)

    risk_signals = []
    loan_amount = float(application.get("loan_amount", 0) or 0)
    tenure = int(application.get("tenure", 0) or 0)
    annual_income = float(application.get("annual_revenue", 0) or 0)

    if loan_amount > 1_000_000:
        risk_signals.append("Requested loan amount is above the standard threshold for fast approval.")
    if tenure > 36:
        risk_signals.append("Long repayment tenure increases exposure period.")
    if not str(application.get("purpose", "")).strip():
        risk_signals.append("Application purpose is too brief for reliable underwriting.")
    if missing_documents:
        risk_signals.append("Required supporting documents are incomplete.")
    if annual_income and loan_amount > annual_income:
        risk_signals.append("Requested amount is higher than declared annual income.")
    if not documents:
        risk_signals.append("No documents were available for automated analysis.")

    financial_summary = _estimate_financial_summary(application)
    recommendation = "Approve" if len(risk_signals) <= 1 else "Reject"
    reason = (
        "Document coverage and application inputs look consistent enough for manual review."
        if recommendation == "Approve"
        else "The application needs closer manual validation because of document or affordability risk signals."
    )

    return {
        "financial_summary": financial_summary,
        "risk_signals": risk_signals or ["No major negative signal detected from the submitted data."],
        "ai_recommendation": recommendation,
        "ai_reason": reason,
        "missing_documents": missing_documents,
        "document_summary": _build_document_summary(documents),
        "agent_status": "completed",
    }


DOCUMENT_KEY_MAP = {
    "balance sheet": "balance_sheet",
    "gst returns": "gst_returns",
    "bank statements": "bank_statements",
    "itr filing": "itr",
    "business pan / kyc docs": "pan_kyc",
    "pl statement": "pl_statement",
}


def _build_uploaded_docs_for_agent(application: dict[str, Any]) -> dict[str, bytes]:
    uploaded_docs = {
        "balance_sheet": b"",
        "gst_returns": b"",
        "bank_statements": b"",
        "itr": b"",
        "pan_kyc": b"",
        "pl_statement": b"",
    }
    for document in application.get("documents", []) or []:
        required_name = str(document.get("required_document_name", "")).strip().lower()
        agent_key = DOCUMENT_KEY_MAP.get(required_name)
        if not agent_key:
            continue
        text_excerpt = str(document.get("text_excerpt", "")).strip()
        uploaded_docs[agent_key] = text_excerpt.encode("utf-8")
    return uploaded_docs


def _build_company_meta(application: dict[str, Any]) -> CompanyMeta:
    loan_amount = float(application.get("loan_amount", 0) or 0)
    return CompanyMeta(
        case_id=str(application.get("id", application.get("loan_id", "CAM-LOCAL"))),
        company_name=str(application.get("company_name", "Applicant")),
        loan_amount_cr=round(loan_amount / 10_000_000, 2),
        sector=str(application.get("industry", "Business")),
        rating_grade="BBB",
        company_age_years=5,
        business_name=str(application.get("business_name", application.get("registered_business_name", ""))),
        owner_full_name=str(application.get("owner_full_name", application.get("promoter_name", ""))),
        city=str(application.get("location", application.get("city", ""))),
        business_type=str(application.get("business_type", "")),
        incorporation_date=str(application.get("incorporation_date", "")),
        years_in_business=float(application.get("years_in_business", 0) or 0) if str(application.get("years_in_business", "")).strip() else None,
    )


def analyze_application(application: dict[str, Any]) -> dict[str, Any]:
    heuristic_analysis = _heuristic_analysis(application)
    meta = _build_company_meta(application)
    uploaded_docs = _build_uploaded_docs_for_agent(application)

    risk_result, cam_text, news_summary = run_research_agent(
        meta,
        uploaded_docs,
        gst_applicable=bool(application.get("gst_applicable", True)),
        uploaded_document_count=len(application.get("documents", []) or []),
    )

    reasons = risk_result.reasons or ["SHIELD agent completed the review."]
    risk_signals = list(dict.fromkeys(heuristic_analysis["risk_signals"] + reasons))
    ai_reason = " | ".join(reasons)

    analysis = {
        "financial_summary": heuristic_analysis["financial_summary"],
        "risk_signals": risk_signals,
        "ai_recommendation": risk_result.loan_decision,
        "ai_reason": ai_reason,
        "missing_documents": heuristic_analysis["missing_documents"],
        "document_summary": heuristic_analysis["document_summary"],
        "agent_status": "completed",
        "shield_score": risk_result.shield_score,
        "risk_level": risk_result.risk_level,
        "default_probability": risk_result.default_probability,
        "confidence_score": risk_result.confidence_score,
        "shield_components": risk_result.components,
        "shield_flags": risk_result.flags,
        "news_summary": news_summary,
        "news_signals": news_summary.get("news_signals", {}),
        "cam_text": cam_text.strip(),
    }

    api_provider = ""
    if os.getenv("OPENAI_API_KEY"):
        api_provider = "openai"
    elif os.getenv("ANTHROPIC_API_KEY"):
        api_provider = "anthropic"

    if api_provider:
        analysis["document_summary"] = (
            analysis["document_summary"]
            + f"\nLLM provider detected: {api_provider}. SHIELD analysis adapter is active."
        )

    return analysis
