# app_streamlit.py

import streamlit as st
from models import CompanyMeta
from research_agent import run_research_agent


st.set_page_config(page_title="Intelli-Credit Demo", layout="wide")


def loan_seeker_portal():
    st.header("Loan Seeker Portal")

    company_name = st.text_input("Company Name", "Arvind Steel & Alloys Pvt. Ltd.")
    sector = st.text_input("Sector", "Steel")
    loan_amount_cr = st.number_input("Requested Loan Amount (Cr)", value=18.0, step=0.5)
    company_age_years = st.number_input("Company Age (years)", value=10, step=1)
    rating_grade = st.text_input("Existing Rating Grade (if any)", "BBB")

    st.subheader("Upload Documents (Demo)")
    bs_file = st.file_uploader("Balance Sheet (PDF)", type=["pdf"], key="bs")
    pl_file = st.file_uploader("P&L Statement (PDF)", type=["pdf"], key="pl")
    bank_file = st.file_uploader("Bank Statements (PDF)", type=["pdf"], key="bank")
    gst_file = st.file_uploader("GST Returns (PDF)", type=["pdf"], key="gst")
    itr_file = st.file_uploader("ITR Filing (PDF)", type=["pdf"], key="itr")
    mca_file = st.file_uploader("MCA/COI (PDF)", type=["pdf"], key="mca")
    ar_file = st.file_uploader("Annual Report (PDF)", type=["pdf"], key="ar")
    legal_file = st.file_uploader("Legal Documents (PDF)", type=["pdf"], key="legal")
    rating_file = st.file_uploader("Rating Report (PDF)", type=["pdf"], key="rating")

    if st.button("Submit Application"):
        st.success("Application submitted. (In this prototype, we directly use it in Credit Officer Portal.)")


def credit_officer_portal():
    st.header("Credit Officer Portal")

    company_name = st.text_input("Company Name", "Arvind Steel & Alloys Pvt. Ltd.", key="co_company")
    sector = st.text_input("Sector", "Steel", key="co_sector")
    loan_amount_cr = st.number_input("Loan Amount (Cr)", value=18.0, step=0.5, key="co_loan")
    company_age_years = st.number_input("Company Age (years)", value=10, step=1, key="co_age")
    rating_grade = st.text_input("Rating Grade", "BBB", key="co_rating")

    bs_file = st.file_uploader("Balance Sheet (PDF)", type=["pdf"], key="co_bs")
    pl_file = st.file_uploader("P&L Statement (PDF)", type=["pdf"], key="co_pl")
    bank_file = st.file_uploader("Bank Statements (PDF)", type=["pdf"], key="co_bank")
    gst_file = st.file_uploader("GST Returns (PDF)", type=["pdf"], key="co_gst")
    itr_file = st.file_uploader("ITR Filing (PDF)", type=["pdf"], key="co_itr")
    mca_file = st.file_uploader("MCA/COI (PDF)", type=["pdf"], key="co_mca")
    ar_file = st.file_uploader("Annual Report (PDF)", type=["pdf"], key="co_ar")
    legal_file = st.file_uploader("Legal Documents (PDF)", type=["pdf"], key="co_legal")
    rating_file = st.file_uploader("Rating Report (PDF)", type=["pdf"], key="co_rating_file")

    if st.button("Run Research Agent & Generate CAM"):
        missing = [
            f for f in [bs_file, pl_file, bank_file, gst_file, rating_file]
            if f is None
        ]
        if missing:
            st.error("Please upload at least Balance Sheet, P&L, Bank, GST, and Rating Report.")
            return

        meta = CompanyMeta(
            case_id="CAM-2026-0001",
            company_name=company_name,
            loan_amount_cr=loan_amount_cr,
            sector=sector,
            rating_grade=rating_grade,
            company_age_years=int(company_age_years),
        )

        uploaded_docs = {
            "balance_sheet": bs_file.read(),
            "pl_statement": pl_file.read(),
            "bank_statements": bank_file.read(),
            "gst_returns": gst_file.read(),
            "itr": itr_file.read() if itr_file else b"",
            "mca_coi": mca_file.read() if mca_file else b"",
            "annual_report": ar_file.read() if ar_file else b"",
            "legal_docs": legal_file.read() if legal_file else b"",
            "rating_report": rating_file.read(),
        }

        risk_result, cam_text, news_summary = run_research_agent(meta, uploaded_docs)

        st.subheader("SHIELD Risk Summary")
        st.write(f"Risk Score: **{risk_result.shield_score} / 100**")
        st.write(f"Risk Level: **{risk_result.risk_level}**")
        st.write(f"Default Probability: **{risk_result.default_probability:.2f}**")
        st.write(f"Loan Decision: **{risk_result.loan_decision}**")

        st.subheader("Component Breakdown")
        st.json(risk_result.components)
        st.subheader("Flags")
        st.json(risk_result.flags)
        st.subheader("News and Litigation Signals")
        st.json(news_summary)
        st.subheader("Reasons")
        for r in risk_result.reasons:
            st.markdown(f"- {r}")

        st.subheader("Generated CAM")
        st.text(cam_text)


def main():
    st.sidebar.title("Intelli-Credit Prototype")
    portal = st.sidebar.radio("Choose Portal", ["Loan Seeker", "Credit Officer"])

    if portal == "Loan Seeker":
        loan_seeker_portal()
    else:
        credit_officer_portal()


if __name__ == "__main__":
    main()
