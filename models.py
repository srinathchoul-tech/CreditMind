# models.py

from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class FinancialRatios:
    dscr: float
    debt_to_equity: float
    current_ratio: float
    profit_margin: float


@dataclass
class GSTFeatures:
    gstr_gap_percent: float
    circular_trading_flag: bool


@dataclass
class NewsLegalFeatures:
    negative_news_score: int        # 0-100 higher = more negative
    legal_case_count: int
    major_events: List[str]


@dataclass
class CompanyMeta:
    case_id: str
    company_name: str
    loan_amount_cr: float
    sector: str
    rating_grade: str
    company_age_years: int
    business_name: str = ""
    owner_full_name: str = ""
    city: str = ""
    business_type: str = ""
    incorporation_date: str = ""
    years_in_business: Optional[float] = None


@dataclass
class ShieldRiskResult:
    shield_score: int               # 0-100, higher = riskier
    risk_level: str                 # LOW / MEDIUM / HIGH
    default_probability: float      # 0-1
    confidence_score: int           # 0-100, confidence in automated assessment
    components: Dict[str, float]
    flags: Dict[str, Any]
    loan_decision: str              # APPROVE / CONDITIONAL APPROVAL / REJECT
    reasons: List[str]
