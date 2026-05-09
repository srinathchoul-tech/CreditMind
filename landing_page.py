import streamlit as st


def _go_auth(mode: str, role: str | None = None) -> None:
    st.session_state.page = "auth"
    st.session_state.auth_mode = mode
    if role:
        st.session_state.auth_role = role
    st.rerun()


def _handle_nav_actions_from_query() -> None:
    action = str(st.query_params.get("lp_action", "")).strip().lower()
    if not action:
        return
    st.query_params.clear()
    if action == "login":
        _go_auth("login")
    if action == "signup":
        _go_auth("signup", "company")


def _inject_landing_css() -> None:
    st.markdown(
        """
        <style>
          #MainMenu {visibility: hidden;}
          footer {visibility: hidden;}
          header {visibility: hidden;}
          .main .block-container{
            max-width: 100%;
            padding-top: 0;
            padding-left: 0;
            padding-right: 0;
            padding-bottom: 2rem;
          }
          html, body, [data-testid="stAppViewContainer"]{
            background: linear-gradient(180deg, #ffffff 0%, #f8fbff 55%, #ffffff 100%);
            color: #111827;
          }
          .cm-shell{
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 24px;
          }
          .cm-navbar{
            position: sticky; top: 0; z-index: 999;
            background: #ffffff; border-bottom: 1px solid #e5e7eb;
            display: flex; justify-content: space-between; align-items: center;
            padding: 14px 36px; margin-top: 0;
            width: 100%;
            box-shadow: 0 2px 10px rgba(15, 23, 42, 0.05);
          }
          .cm-brand{font-size: 26px; font-weight: 800; color: #0f172a; letter-spacing: 0.2px;}
          .cm-links{display:flex; gap: 30px; align-items:center;}
          .cm-links a{color:#334155; text-decoration:none; font-weight:600; font-size:15px;}
          .cm-links a:hover{color:#111827;}
          .cm-hero{padding: 46px 8px 28px 8px; text-align:center;}
          .cm-hero h1{font-size: 50px; color:#0f172a; line-height:1.15; margin-bottom:14px; letter-spacing:-0.6px;}
          .cm-hero p{font-size: 19px; color:#64748b; max-width: 860px; margin: 0 auto; line-height:1.6;}
          .cm-trust{color:#6b7280; font-size:14px; margin-top: 12px;}
          .cm-title{font-size:36px; font-weight:800; text-align:center; color:#0f172a; margin: 22px 0 8px 0; letter-spacing:-0.4px;}
          .cm-subtitle{font-size:17px; color:#64748b; text-align:center; margin-bottom:22px;}
          .cm-card{
            background:#ffffff; border:1px solid #e5e7eb; border-radius:16px; padding:16px;
            box-shadow: 0 6px 20px rgba(15,23,42,0.06); height: 100%;
          }
          .cm-step{font-size:13px; font-weight:700; color:#2563eb; margin-bottom:8px;}
          .cm-card-title{font-size:20px; font-weight:700; color:#0f172a; margin-bottom:8px;}
          .cm-card-text{color:#475569; font-size:15px; line-height:1.5;}
          .cm-signup{
            background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
            color:#ffffff !important;
            border:1px solid #1d4ed8;
            padding:9px 16px;
            border-radius:10px;
            box-shadow: 0 8px 18px rgba(37,99,235,0.28);
          }
          .cm-signup:hover{
            background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%);
            color:#ffffff !important;
          }
          .cm-login{
            border:1px solid #2563eb;
            color:#2563eb !important;
            padding:9px 16px;
            border-radius:10px;
            background:#ffffff;
          }
          .cm-login:hover{
            background:#eff6ff;
          }
          .cm-footer{
            border-top:1px solid #e5e7eb; margin-top:30px; padding-top:16px; color:#6b7280;
            display:flex; justify-content:space-between; gap:10px; flex-wrap:wrap;
          }
          @media (max-width: 900px){
            .cm-navbar{padding: 12px 14px;}
            .cm-links{gap: 14px;}
            .cm-brand{font-size: 22px;}
            .cm-hero h1{font-size: 36px;}
            .cm-title{font-size: 30px;}
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def show_landing_page() -> None:
    _inject_landing_css()
    _handle_nav_actions_from_query()

    st.markdown(
        """
        <div class="cm-navbar">
          <div class="cm-links">
            <span class="cm-brand">CreditMind</span>
            <a href="#home">Home</a>
            <a href="#how-it-works">How It Works</a>
            <a href="#about">About</a>
            <a href="#contact">Contact</a>
          </div>
          <div class="cm-links">
            <a href="?lp_action=login" class="cm-login">Login</a>
            <a href="?lp_action=signup" class="cm-signup">Sign Up</a>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="cm-shell">', unsafe_allow_html=True)
    st.markdown('<div id="home"></div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="cm-hero">
          <h1>AI-Powered Business Loan Assessment</h1>
          <p>Upload your financial documents and get an intelligent credit evaluation in minutes - faster, consistent, and fully explainable.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cta1, cta2 = st.columns(2)
    with cta1:
        if st.button("Apply for a Loan ->", use_container_width=True, type="primary"):
            _go_auth("signup", "company")
    with cta2:
        if st.button("Login as Credit Officer ->", use_container_width=True):
            _go_auth("login", "credit_officer")
    st.markdown(
        '<p class="cm-trust" style="text-align:center;">Trusted evaluation framework · AI-assisted CAM generation · Secure document handling</p>',
        unsafe_allow_html=True,
    )

    st.divider()
    st.markdown('<div id="about"></div>', unsafe_allow_html=True)
    st.markdown('<div class="cm-title">What is a Business Loan?</div>', unsafe_allow_html=True)
    left, right = st.columns(2)
    with left:
        st.markdown(
            """
            A business loan is a financial product where a lender provides capital to a business for purposes such as:
            - Expanding operations or infrastructure
            - Managing working capital and cash flow
            - Purchasing equipment or inventory
            - Funding new projects or hiring

            The lender evaluates the business's financial health, repayment capacity, and creditworthiness before approving the loan.
            """
        )
    with right:
        st.metric("Average processing time", "Traditional: 7-14 days")
        st.metric("With CreditMind", "Under 10 minutes")
        st.metric("Document analysis", "Automated")

    st.divider()
    st.markdown('<div id="how-it-works"></div>', unsafe_allow_html=True)
    st.markdown('<div class="cm-title">How CreditMind Works</div>', unsafe_allow_html=True)
    st.markdown('<div class="cm-subtitle">A simple 4-step process from application to decision</div>', unsafe_allow_html=True)
    step_cols = st.columns(4)
    step_cards = [
        ("Step 1", "Register & Login", "Create your account as a Loan Seeker. Provide basic business details."),
        ("Step 2", "Upload Documents", "Upload your financial documents - bank statements, ITR, balance sheet. All files are securely stored."),
        ("Step 3", "AI Analysis Runs", "Our system extracts financial data, calculates ratios like DSCR and Debt-to-Equity, checks news signals, and generates a risk score automatically."),
        ("Step 4", "Get Your Decision", "A Credit Officer reviews the AI-generated report and makes the final decision. You are notified via email instantly."),
    ]
    for col, (step, title, text) in zip(step_cols, step_cards):
        with col:
            st.markdown(
                f"""
                <div class="cm-card">
                  <div class="cm-step">{step}</div>
                  <div class="cm-card-title">{title}</div>
                  <div class="cm-card-text">{text}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.divider()
    st.markdown('<div class="cm-title">What Does the AI Actually Evaluate?</div>', unsafe_allow_html=True)
    st.markdown('<div class="cm-subtitle">Transparent, explainable risk assessment</div>', unsafe_allow_html=True)
    ai_cols = st.columns(3)
    ai_cards = [
        (
            "Financial Ratios",
            "The system calculates key indicators including:<br>"
            "• DSCR (Debt Service Coverage Ratio)<br>"
            "• Debt-to-Equity Ratio<br>"
            "• Current Ratio<br>"
            "• Net Profit Margin<br>"
            "• Revenue Growth Rate<br>"
            "These ratios determine the business's ability to repay.",
        ),
        (
            "Document Intelligence",
            "Using OCR and NLP, the system:<br>"
            "• Extracts key figures from PDFs automatically<br>"
            "• Cross-validates GST returns vs bank deposits<br>"
            "• Detects inconsistencies across documents<br>"
            "• Flags missing or suspicious data",
        ),
        (
            "External Risk Signals",
            "Beyond financials, the system checks:<br>"
            "• News articles for fraud or legal issues<br>"
            "• Litigation and court case mentions<br>"
            "• Regulatory actions or penalties<br>"
            "• Business age and stability indicators",
        ),
    ]
    for col, (title, text) in zip(ai_cols, ai_cards):
        with col:
            st.markdown(
                f"""
                <div class="cm-card">
                  <div class="cm-card-title">{title}</div>
                  <div class="cm-card-text">{text}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.divider()
    st.markdown('<div class="cm-title">Who Can Apply?</div>', unsafe_allow_html=True)
    who_cols = st.columns(3)
    who_cards = [
        ("Registered Companies", "Pvt Ltd, LLP, OPC with at least 1 year of operations.<br>Required: Bank statement + ITR + PAN"),
        ("Small Businesses & MSMEs", "Sole proprietorships and partnerships.<br>GST registration not mandatory.<br>Required: Bank statement + ITR"),
        ("New / Early-Stage Businesses", "Businesses under 2 years old.<br>Limited documents accepted.<br>Assessed on bank statement and owner's ITR."),
    ]
    for col, (title, text) in zip(who_cols, who_cards):
        with col:
            st.markdown(
                f"""
                <div class="cm-card">
                  <div class="cm-card-title">{title}</div>
                  <div class="cm-card-text">{text}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.divider()
    st.markdown('<div class="cm-title">Documents You May Need</div>', unsafe_allow_html=True)
    d1, d2 = st.columns(2)
    with d1:
        st.success(
            "Mandatory:\n"
            "✓ Bank Statement (last 6 months)\n"
            "✓ Business PAN Card\n"
            "✓ ITR / Income Tax Return (latest)"
        )
    with d2:
        st.info(
            "Optional (if available):\n"
            "○ Balance Sheet\n"
            "○ Profit & Loss Statement\n"
            "○ GST Returns (if registered)"
        )
    st.caption("You can still apply without optional documents. The AI adjusts its analysis based on available data.")

    st.divider()
    st.markdown('<div class="cm-title">Frequently Asked Questions</div>', unsafe_allow_html=True)
    with st.expander("Is my data safe?"):
        st.write(
            "All documents are stored in Firebase secure cloud storage with encrypted access. "
            "Only you and the assigned credit officer can view your documents."
        )
    with st.expander("How long does evaluation take?"):
        st.write(
            "The AI analysis completes in under 2 minutes. The credit officer then reviews and gives a final decision, "
            "typically within 1 business day."
        )
    with st.expander("My business is new - can I still apply?"):
        st.write(
            "Yes. CreditMind supports early-stage businesses. The system adapts its evaluation based on the documents "
            "you are able to provide."
        )
    with st.expander("Do I need a GST number?"):
        st.write(
            "No. GST registration is optional. If your turnover is below Rs.40 lakhs, you can apply without GST documents."
        )
    with st.expander("What happens after I submit?"):
        st.write(
            "Your application goes to a Credit Officer who reviews the AI report and makes the final decision. "
            "You will receive an email with the outcome."
        )

    st.divider()
    st.markdown('<div id="contact"></div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="cm-card" style="text-align:center;">
          <div class="cm-card-title">Ready to apply? It takes less than 5 minutes.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Get Started Now ->", type="primary", use_container_width=True):
        _go_auth("signup", "company")

    st.markdown(
        """
        <div class="cm-footer">
          <div>© 2025 CreditMind. AI-Based Loan Risk Assessment System.</div>
          <div>Built with Python · Streamlit · Firebase · LLM</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)
