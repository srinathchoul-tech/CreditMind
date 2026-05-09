# research_agent.py

from models import CompanyMeta, ShieldRiskResult
from news_agent import fetch_news_legal_features
from parsers import (
    parse_balance_sheet,
    parse_pl_statement,
    parse_bank_statements,
    parse_gst_returns,
    build_financial_ratios,
    build_gst_features,
)
from scoring import compute_shield_risk_score
from cam_generator import generate_cam_text


def run_research_agent(
    meta: CompanyMeta,
    uploaded_docs: dict[str, bytes],
    gst_applicable: bool = True,
    uploaded_document_count: int = 0,
) -> tuple[ShieldRiskResult, str, dict[str, object]]:
    """
    uploaded_docs keys (you decide these in Streamlit):
      - 'balance_sheet'
      - 'pl_statement'
      - 'bank_statements'
      - 'gst_returns'
      - 'itr'
      - 'pan_kyc'
    """

    # 1. Parse core financial docs
    bs_raw = parse_balance_sheet(uploaded_docs["balance_sheet"])
    pl_raw = parse_pl_statement(uploaded_docs["pl_statement"])
    bank_raw = parse_bank_statements(uploaded_docs["bank_statements"])

    ratios = build_financial_ratios(bs_raw, pl_raw, bank_raw)

    # 2. GST features
    gst_raw = parse_gst_returns(uploaded_docs["gst_returns"]) if gst_applicable else {"gstr_2a": 0.0, "gstr_3b": 0.0}
    gst_features = build_gst_features(gst_raw)

    # 3. Use provided rating (defaulted by app metadata).
    rating_grade = meta.rating_grade

    # 4. News & legal features from a fast cached adapter.
    news_legal, news_signals = fetch_news_legal_features(meta)

    non_bank_financial_docs_count = sum(
        1 for key in ("itr", "balance_sheet", "pl_statement", "gst_returns") if uploaded_docs.get(key)
    )
    if not gst_applicable and uploaded_docs.get("gst_returns"):
        non_bank_financial_docs_count = max(non_bank_financial_docs_count - 1, 0)

    # 5. Compute SHIELD risk score
    risk_result = compute_shield_risk_score(
        ratios=ratios,
        gst=gst_features,
        news_legal=news_legal,
        rating_grade=rating_grade,
        extra_flags=None,
        gst_applicable=gst_applicable,
        uploaded_document_count=uploaded_document_count,
        non_bank_financial_docs_count=non_bank_financial_docs_count,
    )

    # 6. Generate CAM text
    cam_text = generate_cam_text(
        meta=meta,
        ratios=ratios,
        gst=gst_features,
        news_legal=news_legal,
        risk=risk_result,
        gst_applicable=gst_applicable,
        limited_docs_note=uploaded_document_count < 3 or non_bank_financial_docs_count == 0,
    )

    news_summary = {
        "negative_news_score": news_legal.negative_news_score,
        "legal_case_count": news_legal.legal_case_count,
        "major_events": news_legal.major_events,
        "confidence_score": risk_result.confidence_score,
        "news_signals": news_signals,
    }

    return risk_result, cam_text, news_summary
