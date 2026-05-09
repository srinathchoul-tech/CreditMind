# cam_generator.py

from models import CompanyMeta, FinancialRatios, GSTFeatures, NewsLegalFeatures, ShieldRiskResult


def generate_cam_text(
    meta: CompanyMeta,
    ratios: FinancialRatios,
    gst: GSTFeatures,
    news_legal: NewsLegalFeatures,
    risk: ShieldRiskResult,
    gst_applicable: bool = True,
    limited_docs_note: bool = False,
) -> str:
    events_text = ""
    if news_legal.major_events:
        events_text = "\n  Key Events:\n  - " + "\n  - ".join(news_legal.major_events)

    reasons_text = ""
    if risk.reasons:
        reasons_text = "\n  Reasons:\n  - " + "\n  - ".join(risk.reasons)

    gst_validation_line = (
        "GST validation: Not applicable (below threshold or exempted)"
        if not gst_applicable
        else f"GSTR-2A/3B Gap: {gst.gstr_gap_percent:.1f}%"
    )
    limited_docs_line = (
        "\n  Note: Limited documentation — early-stage business profile"
        if limited_docs_note
        else ""
    )

    return f"""
SHIELD - Credit Appraisal Memo (CAM)
Case ID: {meta.case_id}
Company: {meta.company_name}
Loan Amount: Rs.{meta.loan_amount_cr:.1f} Cr

Company Profile
  Sector: {meta.sector}
  Company Age: {meta.company_age_years} years
  Rating Grade: {meta.rating_grade}

Financial Ratios
  Debt To Equity: {ratios.debt_to_equity:.2f}
  Current Ratio: {ratios.current_ratio:.2f}
  Profit Margin: {ratios.profit_margin:.2f}
  Dscr: {ratios.dscr:.2f}

Risk Assessment
  SHIELD Risk Score: {risk.shield_score}/100
  Risk Level: {risk.risk_level}
  Default Probability: {risk.default_probability}
  Confidence Score: {risk.confidence_score}%

Fraud / GST Analysis
  GST Anomaly Detected: {risk.flags.get('gst_anomaly')}
  {gst_validation_line}
  Circular Trading Suspected: {risk.flags.get('circular_trading')}

News & Legal Signals
  Negative News Score: {news_legal.negative_news_score}/100
  Legal Case Count: {news_legal.legal_case_count}{events_text}

Loan Decision
  Decision: {risk.loan_decision}{reasons_text}{limited_docs_line}
  (Automated decision based on SHIELD risk score and rule-based thresholds.)
"""
