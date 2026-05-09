import streamlit as st

from data import LOAN_PRODUCTS
from translations import TRANSLATIONS


def t(key: str) -> str:
    lang = st.session_state.language
    return TRANSLATIONS.get(lang, {}).get(key, TRANSLATIONS["English"].get(key, key))


def normalize_email(value: str) -> str:
    return value.strip().lower()


def update_language() -> None:
    st.session_state.language = st.session_state.language_selector


def update_theme_mode() -> None:
    st.session_state.theme_mode = st.session_state.theme_selector


def get_loan_product(loan_id: str | None) -> dict | None:
    if not loan_id:
        return None
    for product in LOAN_PRODUCTS:
        if product["id"] == loan_id:
            return product
    return None


def get_loan_label(product: dict) -> str:
    return t(product["name_key"])


def render_preferences(label_visibility: str = "visible") -> None:
    language_options = ["English", "Hindi"]
    theme_options = ["Light", "Dark"]

    st.radio(
        t("language"),
        language_options,
        horizontal=True,
        key="language_selector",
        index=language_options.index(st.session_state.language),
        on_change=update_language,
        label_visibility=label_visibility,
    )
    st.radio(
        t("theme"),
        theme_options,
        format_func=lambda option: t("theme_light") if option == "Light" else t("theme_dark"),
        horizontal=True,
        key="theme_selector",
        index=theme_options.index(st.session_state.theme_mode),
        on_change=update_theme_mode,
        label_visibility=label_visibility,
    )


def render_top_nav() -> None:
    brand_col, language_col, theme_col = st.columns([5.0, 1.5, 1.5], vertical_alignment="top")
    with brand_col:
        st.markdown("<div class='topbar-brand'>CreditMind</div>", unsafe_allow_html=True)
    with language_col:
        st.markdown(f"<div class='topbar-control-label'>{t('language').upper()}</div>", unsafe_allow_html=True)
        st.radio(
            "LANGUAGE",
            ["English", "Hindi"],
            horizontal=True,
            key="language_selector",
            index=["English", "Hindi"].index(st.session_state.language),
            on_change=update_language,
            label_visibility="collapsed",
        )
    with theme_col:
        st.markdown(f"<div class='topbar-control-label'>{t('theme').upper()}</div>", unsafe_allow_html=True)
        st.radio(
            "THEME",
            ["Light", "Dark"],
            format_func=lambda option: t("theme_light") if option == "Light" else t("theme_dark"),
            horizontal=True,
            key="theme_selector",
            index=["Light", "Dark"].index(st.session_state.theme_mode),
            on_change=update_theme_mode,
            label_visibility="collapsed",
        )
