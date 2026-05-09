import streamlit as st


def inject_theme_styles() -> None:
    if st.session_state.theme_mode == "Dark":
        bg = "#0E2238"
        sidebar = "#0C1B2A"
        panel = "#142F4F"
        border = "#1E3A5F"
        accent = "#2F80ED"
        text = "#EAF3FF"
        muted = "#A8C1E8"
        shadow = "0 10px 24px rgba(4, 16, 30, 0.26)"
        theme_specific_css = """
        .stApp {
            background:
                radial-gradient(circle at top right, rgba(47, 128, 237, 0.08), transparent 33%),
                radial-gradient(circle at bottom left, rgba(21, 101, 192, 0.06), transparent 30%),
                var(--bg);
        }

        div[data-testid="stVerticalBlockBorderWrapper"] > div {
            border-radius: var(--radius);
        }

        [data-testid="stMetric"] {
            background: color-mix(in srgb, var(--card) 95%, var(--accent) 5%);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 0.65rem 0.85rem;
        }

        .stTabs [data-baseweb="tab-list"] {
            margin-bottom: 0.45rem;
        }

        .stTabs [data-baseweb="tab"] {
            border-radius: 8px;
            background: color-mix(in srgb, var(--card) 85%, transparent);
            padding: 0.35rem 0.75rem;
        }

        .stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {
            border-radius: 8px;
            border: 1px solid var(--border);
            background: color-mix(in srgb, var(--accent) 10%, var(--card) 90%);
            padding: 0.38rem 0.92rem;
            color: var(--text);
        }

        .stButton > button:hover, .stFormSubmitButton > button:hover, .stDownloadButton > button:hover {
            box-shadow: 0 7px 16px rgba(21, 101, 192, 0.18);
        }

        [data-testid="stSidebar"] .stButton > button {
            background: color-mix(in srgb, var(--sidebar) 88%, var(--accent) 12%);
        }

        [data-testid="stSidebar"] .stButton > button[kind="primary"] {
            background: color-mix(in srgb, var(--accent) 25%, var(--sidebar) 75%);
        }

        [data-testid="stFileUploader"] {
            border-radius: 10px;
            background: color-mix(in srgb, var(--card) 94%, var(--accent) 6%);
        }

        [data-testid="stFileUploaderDropzone"] {
            border-radius: 8px;
            background: transparent;
        }

        input, textarea, [data-baseweb="select"] > div {
            border-radius: 8px !important;
            background: color-mix(in srgb, var(--card) 95%, transparent) !important;
        }

        [data-testid="stHorizontalBlock"] .stRadio {
            background: linear-gradient(180deg, rgba(20, 47, 79, 0.98), rgba(15, 36, 61, 0.98));
            border: 1px solid var(--border);
            box-shadow: 0 10px 22px rgba(4, 16, 30, 0.26);
        }

        [data-testid="stHorizontalBlock"] .stRadio label,
        [data-testid="stHorizontalBlock"] .stRadio span,
        [data-testid="stHorizontalBlock"] .stRadio div {
            color: var(--text) !important;
        }

        [data-testid="stFileUploaderDropzone"] * {
            color: var(--text) !important;
        }

        .stTabs [data-baseweb="tab"],
        .stTabs [aria-selected="true"],
        .stAlert p,
        .stAlert div,
        .stAlert span,
        .stMarkdown,
        .stMarkdown p {
            color: var(--text) !important;
        }
        """
    else:
        bg = "#EEF3F8"
        sidebar = "#F7FAFD"
        panel = "#FFFFFF"
        border = "#D6E1EE"
        accent = "#0B4F8A"
        text = "#13253A"
        muted = "#5F738A"
        shadow = "0 18px 42px rgba(18, 45, 78, 0.10)"
        theme_specific_css = """
        :root {
            --accent-soft: rgba(11, 79, 138, 0.08);
            --accent-strong: #083B66;
            --hero: rgba(11, 79, 138, 0.12);
            --card-alt: #F3F7FB;
            --navy-wash: #E8F0F8;
        }

        .stApp {
            background:
                linear-gradient(180deg, rgba(255, 255, 255, 0.84), rgba(255, 255, 255, 0) 20%),
                radial-gradient(circle at top right, var(--hero), transparent 33%),
                radial-gradient(circle at top left, rgba(26, 115, 232, 0.05), transparent 28%),
                radial-gradient(circle at bottom left, var(--accent-soft), transparent 30%),
                var(--bg);
        }

        [data-testid="stSidebar"] {
            box-shadow:
                inset -1px 0 0 rgba(255, 255, 255, 0.52),
                16px 0 34px rgba(19, 37, 58, 0.04);
        }

        [data-testid="stSidebar"] > div:first-child {
            background:
                linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(241, 246, 251, 0.96));
        }

        [data-testid="stSidebar"] h1 {
            letter-spacing: 0.02em;
            font-weight: 800;
        }

        .portal-title {
            letter-spacing: -0.02em;
            font-size: 2rem;
            margin-bottom: 0.35rem;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] > div {
            border-radius: 14px;
            border-color: color-mix(in srgb, var(--border) 88%, white 12%);
            box-shadow:
                0 18px 40px rgba(18, 45, 78, 0.08),
                inset 0 1px 0 rgba(255, 255, 255, 0.88);
        }

        [data-testid="stMetric"] {
            background:
                linear-gradient(180deg, rgba(255, 255, 255, 0.98), var(--card-alt));
            border: 1px solid color-mix(in srgb, var(--border) 82%, var(--accent) 18%);
            border-radius: 14px;
            padding: 0.9rem 1rem;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.75);
            position: relative;
            overflow: hidden;
        }

        [data-testid="stMetric"]::before {
            content: "";
            position: absolute;
            inset: 0 auto 0 0;
            width: 4px;
            background: linear-gradient(180deg, var(--accent), #4B92D5);
        }

        .stMetricLabel label {
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.72rem !important;
            color: var(--muted) !important;
        }

        .stMetricValue {
            font-weight: 700 !important;
        }

        .stTabs [data-baseweb="tab-list"] {
            margin-bottom: 0.75rem;
            padding: 0.2rem;
            background: rgba(255, 255, 255, 0.62);
            border: 1px solid rgba(214, 225, 238, 0.9);
            border-radius: 999px;
            width: fit-content;
        }

        .stTabs [data-baseweb="tab"] {
            border-radius: 999px;
            border: none;
            background: transparent;
            padding: 0.42rem 0.95rem;
            font-weight: 600;
        }

        .stTabs [aria-selected="true"] {
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), #E8F1FA) !important;
            color: var(--accent-strong) !important;
            box-shadow:
                0 8px 18px rgba(11, 79, 138, 0.12),
                inset 0 0 0 1px rgba(11, 79, 138, 0.10);
        }

        .stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {
            border-radius: 10px;
            border: 1px solid color-mix(in srgb, var(--border) 84%, var(--accent) 16%);
            background:
                linear-gradient(180deg, rgba(255, 255, 255, 0.98), #E9F1F9);
            padding: 0.48rem 1rem;
            font-weight: 600;
            color: var(--accent-strong) !important;
            box-shadow: 0 8px 20px rgba(18, 45, 78, 0.08);
        }

        .stButton > button:hover, .stFormSubmitButton > button:hover, .stDownloadButton > button:hover {
            box-shadow: 0 12px 26px rgba(11, 79, 138, 0.16);
            background: linear-gradient(180deg, #FFFFFF, #E3EDF8);
        }

        [data-testid="stSidebar"] .stButton > button {
            background:
                linear-gradient(180deg, rgba(255, 255, 255, 0.98), #EDF3F9);
            border-color: rgba(214, 225, 238, 0.92);
            box-shadow: none;
        }

        [data-testid="stSidebar"] .stButton > button[kind="primary"] {
            background:
                linear-gradient(90deg, #E6F0FA, #D8E8F8);
            color: var(--accent-strong);
            border-color: rgba(11, 79, 138, 0.22);
            box-shadow:
                inset 3px 0 0 var(--accent),
                0 10px 20px rgba(11, 79, 138, 0.10);
        }

        [data-testid="stSidebar"] .stRadio label {
            font-weight: 500;
        }

        [data-testid="stFileUploader"] {
            border-radius: 14px;
            background:
                linear-gradient(180deg, rgba(255, 255, 255, 0.99), #F1F6FB);
            border-color: rgba(214, 225, 238, 0.96);
        }

        [data-testid="stFileUploaderDropzone"] {
            border-radius: 12px;
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.65), rgba(232, 240, 248, 0.5));
            border-style: dashed;
        }

        input, textarea, [data-baseweb="select"] > div {
            border-radius: 10px !important;
            background:
                linear-gradient(180deg, rgba(255, 255, 255, 0.99), #F4F8FC) !important;
            border: 1px solid rgba(214, 225, 238, 0.96) !important;
            box-shadow: inset 0 1px 2px rgba(16, 42, 67, 0.04), 0 1px 0 rgba(255, 255, 255, 0.7);
        }

        input:focus, textarea:focus, [data-baseweb="select"] > div:focus-within {
            border-color: var(--accent) !important;
            box-shadow: 0 0 0 3px rgba(11, 79, 138, 0.10) !important;
        }

        [data-baseweb="select"] *,
        [data-baseweb="select"] input {
            color: var(--text) !important;
            caret-color: var(--accent-strong) !important;
        }

        [data-baseweb="popover"],
        [data-baseweb="popover"] > div,
        [data-baseweb="menu"],
        [role="listbox"] {
            color-scheme: light !important;
            background: #FFFFFF !important;
            border: 1px solid rgba(11, 79, 138, 0.22) !important;
            border-radius: 10px !important;
            box-shadow: 0 16px 34px rgba(18, 45, 78, 0.18) !important;
        }

        [data-baseweb="popover"] [role="option"],
        [data-baseweb="popover"] [role="option"] *,
        [data-baseweb="menu"] [role="option"],
        [data-baseweb="menu"] [role="option"] *,
        [role="listbox"] [role="option"],
        [role="listbox"] [role="option"] * {
            color: var(--accent-strong) !important;
            background: transparent !important;
        }

        [data-baseweb="popover"] [role="option"]:hover,
        [data-baseweb="popover"] [role="option"][aria-selected="true"],
        [data-baseweb="menu"] [role="option"]:hover,
        [data-baseweb="menu"] [role="option"][aria-selected="true"],
        [role="listbox"] [role="option"]:hover,
        [role="listbox"] [role="option"][aria-selected="true"] {
            background: #E6F0FA !important;
            color: var(--accent-strong) !important;
        }

        .stAlert {
            border-radius: 12px;
            border: 1px solid var(--border);
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), var(--card-alt));
            box-shadow: 0 10px 24px rgba(18, 45, 78, 0.06);
        }

        h3 {
            letter-spacing: -0.02em;
            color: var(--accent-strong);
        }

        [data-testid="stSidebar"] .stCaption {
            color: var(--muted) !important;
        }

        [data-testid="stSidebar"] .stButton {
            margin-top: 0.2rem;
        }

        hr {
            border-color: rgba(214, 225, 238, 0.85);
        }
        """

    logged_out_css = ""

    st.markdown(
        f"""
        <style>
        :root {{
            --bg: {bg};
            --sidebar: {sidebar};
            --card: {panel};
            --border: {border};
            --accent: {accent};
            --text: {text};
            --muted: {muted};
            --radius: 10px;
            --shadow: {shadow};
        }}

        .stApp {{
            color: var(--text);
        }}

        #MainMenu, footer {{
            display: none !important;
        }}

        header[data-testid="stHeader"] {{
            background: transparent !important;
            border: none !important;
        }}

        [data-testid="stToolbar"],
        [data-testid="stDecoration"] {{
            display: none !important;
        }}

        .block-container {{
            max-width: 1040px;
            margin: 0 auto;
            padding-top: 0.3rem;
            padding-bottom: 2.2rem;
        }}

        .light-json-block {{
            background: color-mix(in srgb, var(--card) 94%, #f3f7fb 6%);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 0.65rem 0.75rem;
            overflow-x: auto;
        }}

        .light-json-block pre {{
            margin: 0;
            color: var(--text);
            background: transparent;
            font-size: 0.86rem;
            line-height: 1.35;
            white-space: pre-wrap;
            word-break: break-word;
        }}

        .light-code-block {{
            background: color-mix(in srgb, var(--card) 95%, #f3f7fb 5%);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 0.7rem 0.8rem;
            max-height: 560px;
            overflow: auto;
        }}

        .light-code-block pre {{
            margin: 0;
            color: var(--text);
            background: transparent;
            font-size: 0.9rem;
            line-height: 1.42;
            white-space: pre-wrap;
            word-break: break-word;
        }}

        [data-testid="stJson"] {{
            background: color-mix(in srgb, var(--card) 95%, #f3f7fb 5%);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 0.4rem;
        }}

        [data-testid="stJson"] * {{
            color: var(--text) !important;
            background: transparent !important;
        }}

        [data-testid="stCodeBlock"] {{
            background: color-mix(in srgb, var(--card) 95%, #f3f7fb 5%) !important;
            border: 1px solid var(--border) !important;
            border-radius: 10px !important;
        }}

        [data-testid="stCodeBlock"] * {{
            color: var(--text) !important;
            background: transparent !important;
        }}

        [data-testid="stSidebar"] {{
            background: var(--sidebar);
            border-right: 1px solid var(--border);
        }}

        section[data-testid="stSidebar"][aria-expanded="true"] {{
            width: 17.5rem !important;
            min-width: 17.5rem !important;
            max-width: 17.5rem !important;
        }}

        section[data-testid="stSidebar"][aria-expanded="true"] > div {{
            width: 17.5rem !important;
        }}

        [data-testid="stSidebar"] .block-container {{
            padding-top: 0.05rem;
            padding-bottom: 0.45rem;
        }}

        [data-testid="stSidebar"] * {{
            color: var(--text);
        }}

        [data-testid="stSidebar"] h1 {{
            margin-top: 0;
            margin-bottom: 0.15rem;
            font-size: 1.45rem;
        }}

        [data-testid="stSidebar"] .stCaption {{
            margin-bottom: 0.2rem;
            line-height: 1.2;
        }}

        [data-testid="stSidebar"] .stRadio {{
            margin-bottom: 0.35rem;
        }}

        [data-testid="stSidebar"] [role="radiogroup"] {{
            gap: 0.2rem;
        }}

        .portal-title {{
            font-size: 1.7rem;
            font-weight: 700;
            color: var(--text);
            margin-bottom: 0.25rem;
        }}

        .topbar-brand {{
            background: linear-gradient(90deg, #0B4F8A, #1565C0);
            color: #FFFFFF !important;
            border-radius: 16px;
            padding: 0.9rem 1.1rem;
            font-size: 1.45rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            margin-bottom: 0.6rem;
            line-height: 1.05;
            text-align: left;
            box-shadow: 0 14px 28px rgba(11, 79, 138, 0.18);
        }}

        .topbar-control-label {{
            background: linear-gradient(180deg, #0B4F8A, #1565C0);
            color: #FFFFFF !important;
            border-radius: 12px 12px 0 0;
            padding: 0.4rem 0.75rem 0.24rem 0.75rem;
            font-size: 0.8rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin-bottom: -0.12rem;
        }}

        [data-testid="stHorizontalBlock"] .stRadio {{
            background: rgba(255, 255, 255, 0.92);
            border: 1px solid rgba(255, 255, 255, 0.28);
            border-radius: 0 0 12px 12px;
            padding: 0.4rem 0.7rem 0.24rem 0.7rem;
            margin-bottom: 0.55rem;
            box-shadow: 0 8px 16px rgba(18, 45, 78, 0.12);
        }}

        [data-testid="stHorizontalBlock"] > div[data-testid="column"] {{
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
        }}

        [data-testid="stHorizontalBlock"] .stRadio [role="radiogroup"] {{
            gap: 0.15rem;
        }}

        [data-testid="stHorizontalBlock"] .stRadio label {{
            margin-bottom: 0 !important;
        }}

        .section-title {{
            font-size: 1.3rem;
            font-weight: 650;
            color: var(--text);
            margin: 0.35rem 0 0.85rem 0;
            letter-spacing: 0.1px;
        }}

        .body-muted {{
            color: var(--muted);
            font-size: 0.95rem;
        }}

        div[data-testid="stVerticalBlockBorderWrapper"] > div {{
            background: var(--card);
            border: 1px solid var(--border);
            padding: 1rem 1.1rem;
            box-shadow: var(--shadow);
        }}

        .stMetricLabel label, .stMetricValue, .stMetricDelta {{
            color: var(--text) !important;
        }}

        .stTabs [data-baseweb="tab-list"] {{
            gap: 0.45rem;
        }}

        .stTabs [data-baseweb="tab"] {{
            border: 1px solid var(--border);
            color: var(--muted);
        }}

        .stTabs [aria-selected="true"] {{
            border-color: var(--accent) !important;
            color: var(--text) !important;
            box-shadow: inset 0 0 0 1px var(--accent);
        }}

        .stButton > button, .stFormSubmitButton > button {{
            color: var(--text);
            transition: all 0.18s ease-in-out;
        }}

        .stButton > button:hover, .stFormSubmitButton > button:hover, .stDownloadButton > button:hover {{
            border-color: var(--accent);
            transform: translateY(-1px);
        }}

        .stDownloadButton > button {{
            color: var(--text) !important;
            border-radius: 10px;
            border: 1px solid var(--border);
            background: color-mix(in srgb, var(--card) 90%, var(--accent) 10%);
            transition: all 0.18s ease-in-out;
        }}

        [data-testid="stSidebar"] .stButton > button {{
            width: 100%;
            text-align: left;
            margin-top: 0.12rem;
            margin-bottom: 0.12rem;
            padding-top: 0.3rem;
            padding-bottom: 0.3rem;
        }}

        [data-testid="stSidebar"] .stButton > button[kind="primary"] {{
            border-color: color-mix(in srgb, var(--accent) 65%, var(--border) 35%);
            box-shadow: inset 3px 0 0 var(--accent);
        }}

        [data-testid="stFileUploader"] {{
            border: 1px solid var(--border);
            padding: 0.65rem;
        }}

        [data-testid="stFileUploaderDropzone"] {{
            border: 1px dashed var(--border);
            padding: 0.6rem 0.75rem;
        }}

        [data-testid="stFileUploaderDropzone"] * {{
            color: var(--muted) !important;
        }}

        input, textarea, [data-baseweb="select"] > div {{
            border-color: var(--border) !important;
            background: color-mix(in srgb, var(--card) 95%, transparent) !important;
            color: var(--text) !important;
        }}

        [data-baseweb="input"][aria-disabled="true"] input,
        input:disabled,
        textarea:disabled {{
            color: color-mix(in srgb, var(--text) 78%, var(--muted) 22%) !important;
            opacity: 1 !important;
            background: color-mix(in srgb, var(--card) 92%, var(--border) 8%) !important;
        }}

        a {{
            color: color-mix(in srgb, var(--accent) 88%, #1a73e8 12%) !important;
            text-decoration: underline;
            text-underline-offset: 2px;
        }}

        label, p, div, span {{
            color: var(--text);
        }}

        .stCaption {{
            color: color-mix(in srgb, var(--muted) 86%, var(--text) 14%) !important;
        }}

        {logged_out_css}

        {theme_specific_css}
        </style>
        """,
        unsafe_allow_html=True,
    )
