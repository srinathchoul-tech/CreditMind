# scoring.py

from typing import Dict
from models import FinancialRatios, GSTFeatures, NewsLegalFeatures, ShieldRiskResult


def calc_financial_risk(r: FinancialRatios) -> float:
    risk = 0.0

    # DSCR (lower is worse)
    if r.dscr < 1.0:
        risk += 25
    elif r.dscr < 1.2:
        risk += 18
    elif r.dscr < 1.5:
        risk += 10

    # Debt-to-equity (higher is worse)
    if r.debt_to_equity > 3:
        risk += 10
    elif r.debt_to_equity > 2:
        risk += 6
    elif r.debt_to_equity > 1:
        risk += 3

    # Current ratio (too low is bad)
    if r.current_ratio < 1:
        risk += 5

    # Profit margin (very low margin is riskier)
    if r.profit_margin < 0.03:
        risk += 5
    elif r.profit_margin < 0.10:
        risk += 3

    return min(risk, 40.0)


def calc_gst_risk(gst: GSTFeatures) -> float:
    risk = 0.0
    if gst.gstr_gap_percent > 35:
        risk += 15
    elif gst.gstr_gap_percent > 20:
        risk += 8

    if gst.circular_trading_flag:
        risk += 5

    return min(risk, 20.0)


def calc_news_legal_risk(n: NewsLegalFeatures) -> float:
    risk = 0.0
    risk += n.negative_news_score * 0.15  # 0–15 points approx.

    if n.legal_case_count > 10:
        risk += 10
    elif n.legal_case_count > 3:
        risk += 5

    return min(risk, 25.0)


def calc_rating_risk(rating_grade: str) -> float:
    mapping = {
        "AAA": 0,
        "AA": 3,
        "A": 6,
        "BBB": 10,
        "BB": 13,
        "B": 15,
    }
    return float(mapping.get(rating_grade.upper(), 8))


def compute_shield_risk_score(
    ratios: FinancialRatios,
    gst: GSTFeatures,
    news_legal: NewsLegalFeatures,
    rating_grade: str,
    extra_flags: Dict[str, float] | None = None,
    gst_applicable: bool = True,
    uploaded_document_count: int = 0,
    non_bank_financial_docs_count: int = 0,
) -> ShieldRiskResult:
    financial_risk = calc_financial_risk(ratios)
    bank_weight = 0.35
    if non_bank_financial_docs_count == 0:
        # For early-stage profiles with missing financial statements, bank cashflow is weighted higher.
        bank_weight = 0.50
        financial_risk = min(40.0, financial_risk + 4.0)
    elif non_bank_financial_docs_count == 1:
        bank_weight = 0.45
        financial_risk = min(40.0, financial_risk + 2.0)

    gst_risk = calc_gst_risk(gst) if gst_applicable else 0.0
    news_legal_risk = calc_news_legal_risk(news_legal)
    rating_risk = calc_rating_risk(rating_grade)

    extra_risk = 0.0
    if extra_flags:
        extra_risk = sum(extra_flags.values())

    raw_score = financial_risk + gst_risk + news_legal_risk + rating_risk + extra_risk
    shield_score = int(min(raw_score, 100))

    # Risk level bands (higher score = higher risk)
    if shield_score <= 30:
        risk_level = "LOW"
    elif shield_score <= 60:
        risk_level = "MEDIUM"
    else:
        risk_level = "HIGH"

    default_probability = round(shield_score / 100.0, 2)

    confidence_score = 90
    if uploaded_document_count < 3:
        confidence_score = min(confidence_score, 70)
    if uploaded_document_count < 2:
        confidence_score = min(confidence_score, 60)
    if non_bank_financial_docs_count == 0:
        confidence_score = min(confidence_score, 68)

    # Simple decision logic
    if shield_score > 70:
        loan_decision = "REJECT"
    elif shield_score > 40:
        loan_decision = "CONDITIONAL APPROVAL"
    else:
        loan_decision = "APPROVE"

    reasons = []

    if ratios.dscr < 1.2:
        reasons.append(f"Low DSCR ({ratios.dscr:.2f}x) versus comfort level.")
    if gst_applicable and gst.gstr_gap_percent > 20:
        reasons.append(f"High GSTR-2A/3B gap ({gst.gstr_gap_percent:.1f}%).")
    if gst_applicable and gst.circular_trading_flag:
        reasons.append("Circular trading suspected from GST pattern.")
    if non_bank_financial_docs_count == 0:
        reasons.append("Limited documentation - early-stage business profile.")
    if news_legal.negative_news_score > 50:
        reasons.append("Multiple negative news/legal references.")
    if rating_grade.upper() in ["BB", "B"]:
        reasons.append(f"Weak external rating ({rating_grade}).")

    components = {
        "financial_risk": financial_risk,
        "gst_risk": gst_risk,
        "news_legal_risk": news_legal_risk,
        "rating_risk": rating_risk,
        "extra_risk": extra_risk,
        "bank_document_weight": bank_weight,
    }

    flags = {
        "gst_anomaly": gst.gstr_gap_percent > 20 if gst_applicable else False,
        "circular_trading": gst.circular_trading_flag if gst_applicable else False,
        "gst_applicable": gst_applicable,
        "high_negative_news": news_legal.negative_news_score > 50,
    }

    return ShieldRiskResult(
        shield_score=shield_score,
        risk_level=risk_level,
        default_probability=default_probability,
        confidence_score=confidence_score,
        components=components,
        flags=flags,
        loan_decision=loan_decision,
        reasons=reasons,
    )
