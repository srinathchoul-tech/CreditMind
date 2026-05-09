import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from models import CompanyMeta, NewsLegalFeatures


RISK_QUERY_TERMS = [
    "fraud",
    "court case",
    "insolvency",
    "RBI penalty",
    "SEBI action",
    "NPA",
    "loan default",
    "GST evasion",
    "ED raid",
    "bankruptcy",
    "cheque bounce",
    "money laundering",
    "regulatory violation",
]

HIGH_RISK_TERMS = {
    "fraud",
    "default",
    "insolvency",
    "npa",
    "ed raid",
    "sebi penalty",
    "rbi action",
    "gst evasion",
    "money laundering",
    "cheque dishonour",
    "cheque bounce",
    "bankruptcy",
}

MEDIUM_RISK_TERMS = {
    "court case",
    "legal dispute",
    "arbitration",
    "tax evasion notice",
    "regulatory warning",
    "licence cancelled",
}

INDIVIDUAL_TYPES = {"sole_proprietor", "sole proprietor", "partnership", "proprietorship", "individual"}
REGISTERED_TYPES = {"pvt_ltd", "private limited", "llp", "limited", "company", "public limited"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _parse_years(meta: CompanyMeta) -> float | None:
    if meta.years_in_business is not None:
        try:
            return float(meta.years_in_business)
        except (TypeError, ValueError):
            return None
    raw_date = str(meta.incorporation_date or "").strip()
    if not raw_date:
        return None
    date_candidates = [raw_date, raw_date.split("T")[0]]
    for candidate in date_candidates:
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                dt = datetime.strptime(candidate, fmt)
                days = (datetime.now() - dt).days
                return max(0.0, days / 365.25)
            except ValueError:
                continue
    return None


def _detect_case_type(meta: CompanyMeta) -> str:
    business_type = str(meta.business_type or "").strip().lower()
    years = _parse_years(meta)
    if business_type in INDIVIDUAL_TYPES:
        return "individual"
    if years is not None and years < 2:
        return "new_company"
    if business_type in REGISTERED_TYPES:
        return "registered_company"
    return "registered_company"


def _fetch_json(url: str, timeout: int = 6) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "CreditMind/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _fetch_text(url: str, timeout: int = 6) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "CreditMind/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def _build_keyword_clause() -> str:
    return " OR ".join(f'"{term}"' if " " in term else term for term in RISK_QUERY_TERMS)


def _fetch_newsapi_articles(query: str, api_key: str) -> list[dict]:
    encoded_query = urllib.parse.quote(query)
    url = (
        "https://newsapi.org/v2/everything"
        f"?q={encoded_query}&language=en&pageSize=20&sortBy=publishedAt&apiKey={api_key}"
    )
    payload = _fetch_json(url)
    articles = []
    for item in payload.get("articles", [])[:20]:
        articles.append(
            {
                "title": _normalize_space(str(item.get("title", ""))),
                "description": _normalize_space(str(item.get("description", ""))),
                "content": _normalize_space(str(item.get("content", ""))),
                "url": str(item.get("url", "")).strip(),
                "source": str((item.get("source", {}) or {}).get("name", "NewsAPI")).strip() or "NewsAPI",
                "published_at": str(item.get("publishedAt", "")).strip(),
            }
        )
    return articles


def _fetch_google_rss_articles(query: str) -> list[dict]:
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
    xml_text = _fetch_text(url)
    root = ET.fromstring(xml_text)
    articles = []
    for item in root.findall(".//item")[:20]:
        title = _normalize_space(item.findtext("title") or "")
        description = _normalize_space(re.sub(r"<[^>]+>", " ", item.findtext("description") or ""))
        link = _normalize_space(item.findtext("link") or "")
        published_at = _normalize_space(item.findtext("pubDate") or "")
        source = "Google News"
        articles.append(
            {
                "title": title,
                "description": description,
                "content": description,
                "url": link,
                "source": source,
                "published_at": published_at,
            }
        )
    return articles


def _article_text(article: dict) -> str:
    return _normalize_space(f"{article.get('title', '')} {article.get('description', '')} {article.get('content', '')}")


def _headline_matches(headline: str, names: list[str]) -> bool:
    lowered = headline.lower()
    for name in names:
        candidate = _normalize_space(name).lower()
        if len(candidate) >= 3 and candidate in lowered:
            return True
    return False


def _classify_risk(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in HIGH_RISK_TERMS):
        return "high"
    if any(term in lowered for term in MEDIUM_RISK_TERMS):
        return "medium"
    return "ignore"


def _short_date(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "Date unavailable"
    return raw.split("T")[0] if "T" in raw else raw


def _format_point(article: dict) -> str:
    source = article.get("source", "Source")
    title = _normalize_space(article.get("title", ""))
    if len(title) > 140:
        title = title[:137].rstrip() + "..."
    date_value = _short_date(str(article.get("published_at", "")))
    return f"[{source}] {title} — {date_value}"


def _dedupe_articles(articles: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for article in articles:
        key = (
            str(article.get("url", "")).strip().lower(),
            str(article.get("title", "")).strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(article)
    return deduped


def _collect_articles(queries: list[str]) -> list[dict]:
    articles: list[dict] = []
    news_api_key = ""
    try:
        import os

        news_api_key = os.getenv("NEWSAPI_KEY", "").strip()
    except Exception:
        news_api_key = ""

    for query in queries:
        try:
            if news_api_key:
                articles.extend(_fetch_newsapi_articles(query, news_api_key))
        except Exception:
            pass
        try:
            articles.extend(_fetch_google_rss_articles(query))
        except Exception:
            pass
    return _dedupe_articles(articles)


def _build_insufficient_history_output() -> tuple[NewsLegalFeatures, dict[str, object]]:
    message = (
        "Business established recently — no news history available. "
        "Risk assessed primarily from financial documents."
    )
    features = NewsLegalFeatures(
        negative_news_score=0,
        legal_case_count=0,
        major_events=[message],
    )
    signals = {
        "case_type": "new_company",
        "risk_level": "insufficient_history",
        "points": [],
        "sources": [],
        "searched_on": _utc_now_iso(),
    }
    return features, signals


def fetch_news_legal_features(meta: CompanyMeta) -> tuple[NewsLegalFeatures, dict[str, object]]:
    case_type = _detect_case_type(meta)
    if case_type == "new_company":
        return _build_insufficient_history_output()

    company_name = _normalize_space(meta.company_name)
    business_name = _normalize_space(meta.business_name)
    owner_name = _normalize_space(meta.owner_full_name)
    city = _normalize_space(meta.city)
    keyword_clause = _build_keyword_clause()

    if case_type == "individual":
        base_name = owner_name or company_name or business_name
        if not base_name:
            base_name = "Applicant"
        queries = [
            f"\"{base_name}\" \"{city}\" ({keyword_clause})" if city else f"\"{base_name}\" ({keyword_clause})",
            f"\"{base_name}\" court",
            f"\"{base_name}\" fraud",
        ]
        name_filters = [base_name]
    else:
        entity_names = [name for name in [company_name, business_name] if name]
        if not entity_names:
            entity_names = [company_name or "Applicant"]
        base = " OR ".join(f'"{name}"' for name in entity_names)
        queries = [f"({base}) ({keyword_clause})"]
        name_filters = entity_names

    raw_articles = _collect_articles(queries)
    filtered_high = []
    filtered_medium = []

    for article in raw_articles:
        headline = _normalize_space(str(article.get("title", "")))
        if not _headline_matches(headline, name_filters):
            continue
        level = _classify_risk(_article_text(article))
        if level == "high":
            filtered_high.append(article)
        elif level == "medium":
            filtered_medium.append(article)

    selected_articles = (filtered_high + filtered_medium)[:4]
    points = [_format_point(article) for article in selected_articles]
    sources = [article.get("url", "") for article in selected_articles if article.get("url")]

    if filtered_high:
        risk_level = "high"
    elif filtered_medium:
        risk_level = "medium"
    else:
        risk_level = "none"

    if case_type == "individual" and not points:
        fallback = "No adverse news found for this individual."
    elif not points:
        fallback = "No significant legal or fraud news found for this business."
    else:
        fallback = ""

    if risk_level == "high":
        negative_score = min(100, 65 + len(filtered_high) * 10)
    elif risk_level == "medium":
        negative_score = min(60, 25 + len(filtered_medium) * 8)
    else:
        negative_score = 5

    major_events = points[:]
    if fallback:
        major_events = [fallback]
    if case_type == "individual":
        major_events.append(
            "Individual applicant — news signals may be limited. Credit officer to conduct additional background check if needed."
        )

    features = NewsLegalFeatures(
        negative_news_score=negative_score,
        legal_case_count=len(points),
        major_events=major_events,
    )

    signals = {
        "case_type": case_type,
        "risk_level": risk_level,
        "points": points,
        "sources": sources,
        "searched_on": _utc_now_iso(),
    }
    return features, signals
