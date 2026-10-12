# ============================================================

# FinancePilot AI - Streamlit Dashboard

# ============================================================

import sys

import sqlite3

from pathlib import Path

# ------------------------------------------------------------

# PROJECT ROOT

# ------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:

    sys.path.insert(0, str(PROJECT_ROOT))

# ------------------------------------------------------------

# IMPORTS

# ------------------------------------------------------------

import pandas as pd

import streamlit as st

from app.agent.agent import FinancePilotAgent

from app.tools.finance_tools import approve_transaction

# ============================================================

# PAGE CONFIGURATION

# ============================================================

st.set_page_config(

    page_title="FinancePilot AI",

    page_icon="💼",

    layout="wide",

    initial_sidebar_state="expanded",

)

# ============================================================

# PROJECT PATHS

# ============================================================

DATABASE = PROJECT_ROOT / "data" / "financepilot.db"

BANK_FILE = (

    PROJECT_ROOT

    / "data"

    / "bank_transactions"

    / "transactions.xlsx"

)

INVOICE_FILE = (

    PROJECT_ROOT

    / "data"

    / "invoice"

    / "invoice.xlsx"

)

POLICY_FILE = (

    PROJECT_ROOT

    / "data"

    / "policies"

    / "finance_policy.txt"

)

# ============================================================

# SESSION STATE

# ============================================================

if "agent_result" not in st.session_state:

    st.session_state.agent_result = None

if "uploaded_datasets" not in st.session_state:

    st.session_state.uploaded_datasets = {}

if "approval_message" not in st.session_state:

    st.session_state.approval_message = None

# ============================================================

# CUSTOM STYLING

# ============================================================

st.markdown(

    """

    <style>

    /* =========================

       MAIN APPLICATION

       ========================= */

    .stApp {

        background-color: #F7F9FC;

    }

    .block-container {

        max-width: 1450px;

        padding-top: 2rem;

        padding-bottom: 3rem;

    }

    /* =========================

       SIDEBAR

       ========================= */

    [data-testid="stSidebar"] {

        background-color: #EEF2FF;

        border-right: 1px solid #D9E2F2;

    }

    /* =========================

       HEADINGS

       ========================= */

    h1 {

        color: #172554 !important;

        font-weight: 800 !important;

    }

    h2 {

        color: #1E3A8A !important;

    }

    h3 {

        color: #3730A3 !important;

    }

    /* =========================

       BUTTONS

       ========================= */

    .stButton > button {

        border-radius: 10px;

        min-height: 42px;

        font-weight: 600;

    }

    /* =========================

       INFO BOX

       ========================= */

    .hero-subtitle {

        color: #64748B;

        font-size: 17px;

        margin-bottom: 20px;

    }

    /* =========================

       DATASET CARD

       ========================= */

    .dataset-card {

        background-color: white;

        border: 1px solid #E2E8F0;

        border-radius: 14px;

        padding: 18px;

        min-height: 150px;

        box-shadow: 0 3px 12px rgba(15, 23, 42, 0.04);

    }

    /* =========================

       TRACE

       ========================= */

    .trace-item {

        background-color: white;

        border-left: 4px solid #6366F1;

        border-radius: 8px;

        padding: 12px 16px;

        margin-bottom: 8px;

    }

    /* =========================

       APPROVAL

       ========================= */

    .approval-card {

        background-color: #FFF7ED;

        border: 1px solid #FED7AA;

        border-radius: 14px;

        padding: 18px;

        margin-bottom: 15px;

    }

    /* =========================

       FOOTER

       ========================= */

    .footer-text {

        color: #94A3B8;

        font-size: 12px;

        text-align: center;

        margin-top: 40px;

    }

    </style>

    """,

    unsafe_allow_html=True,

)

# ============================================================

# DATASET LOADING

# ============================================================

def load_builtin_datasets():

    datasets = []

    # --------------------------------------------------------

    # Bank Transactions

    # --------------------------------------------------------

    if BANK_FILE.exists():

        try:

            df = pd.read_excel(BANK_FILE)

            datasets.append(

                {

                    "name": "Bank Transactions",

                    "filename": BANK_FILE.name,

                    "type": "Excel",

                    "rows": len(df),

                    "columns": len(df.columns),

                    "data": df,

                }

            )

        except Exception as error:

            st.error(

                f"Unable to read bank transactions: {error}"

            )

    # --------------------------------------------------------

    # Invoices

    # --------------------------------------------------------

    if INVOICE_FILE.exists():

        try:

            df = pd.read_excel(INVOICE_FILE)

            datasets.append(

                {

                    "name": "Invoices",

                    "filename": INVOICE_FILE.name,

                    "type": "Excel",

                    "rows": len(df),

                    "columns": len(df.columns),

                    "data": df,

                }

            )

        except Exception as error:

            st.error(

                f"Unable to read invoices: {error}"

            )

    # --------------------------------------------------------

    # Finance Policy

    # --------------------------------------------------------

    if POLICY_FILE.exists():

        try:

            policy_text = POLICY_FILE.read_text(

                encoding="utf-8"

            )

            datasets.append(

                {

                    "name": "Finance Policy",

                    "filename": POLICY_FILE.name,

                    "type": "Text",

                    "rows": 1,

                    "columns": 1,

                    "data": policy_text,

                }

            )

        except Exception as error:

            st.error(

                f"Unable to read finance policy: {error}"

            )

    return datasets

# ============================================================

# UPLOADED FILE READER

# ============================================================

def read_uploaded_file(uploaded_file):

    extension = Path(

        uploaded_file.name

    ).suffix.lower()

    try:

        # CSV

        if extension == ".csv":

            df = pd.read_csv(uploaded_file)

            return {

                "type": "table",

                "data": df,

                "rows": len(df),

                "columns": len(df.columns),

            }

        # Excel

        if extension in [".xlsx", ".xls"]:

            df = pd.read_excel(uploaded_file)

            return {

                "type": "table",

                "data": df,

                "rows": len(df),

                "columns": len(df.columns),

            }

        # Text

        if extension == ".txt":

            text = uploaded_file.read().decode(

                "utf-8",

                errors="replace",

            )

            return {

                "type": "text",

                "data": text,

                "rows": 1,

                "columns": 1,

            }

    except Exception as error:

        st.error(

            f"Could not read {uploaded_file.name}: {error}"

        )

    return None

# ============================================================

# DATA SEARCH

# ============================================================

def search_dataframe(df, query):

    if not query:

        return df

    query = str(query).strip().lower()

    if not query:

        return df

    string_df = df.astype(str)

    matches = string_df.apply(

        lambda column:

        column.str.lower().str.contains(

            query,

            na=False,

        )

    )

    return df[matches.any(axis=1)]

# ============================================================

# DATABASE - PENDING APPROVALS

# ============================================================

def get_pending_approvals():

    if not DATABASE.exists():

        return []

    try:

        conn = sqlite3.connect(

            str(DATABASE)

        )

        query = """

            SELECT

                a.approval_id,

                a.transaction_id,

                b.vendor,

                b.amount,

                a.status

            FROM approvals a

            JOIN bank_transactions b

                ON a.transaction_id = b.transaction_id

            WHERE a.status = 'Pending'

            AND b.status = 'Pending'

            ORDER BY a.approval_id

        """

        approvals = conn.execute(

            query

        ).fetchall()

        conn.close()

        return approvals

    except Exception:

        return []

# ============================================================

# LOAD BUILT-IN DATA

# ============================================================

builtin_datasets = load_builtin_datasets()

# ============================================================

# SIDEBAR

# ============================================================

with st.sidebar:

    st.markdown("## 💼 FinancePilot")

    st.caption(

        "AUTONOMOUS FINANCE OPERATIONS"

    )

    st.divider()

    st.markdown("### Platform")

    st.markdown(

        """

        🎯 **Goal Understanding**

        🧠 **Task Planning**

        ⚙️ **Tool Execution**

        👤 **Human Approval**

        ✅ **Verification**

        🧾 **Audit Trail**

        """

    )

    st.divider()

    st.markdown("### System Status")

    st.success("Finance Engine Online")

    st.success("ERP Simulator Online")

    st.success("Verification Online")

    st.info("Local Planner Active")

    st.divider()

    st.caption(

        "FinancePilot uses a deterministic "

        "model-agnostic planner."

    )

# ============================================================

# HEADER

# ============================================================

st.title("💼 FinancePilot AI")

st.markdown(

    '<div class="hero-subtitle">'

    'Autonomous Finance Operations Employee'

    '</div>',

    unsafe_allow_html=True,

)

st.write(

    "Turn a business objective into verified finance "

    "operations with approvals, recovery and an "

    "auditable execution trail."

)

# ============================================================

# SECTION 1 - OBJECTIVE

# ============================================================

st.divider()

st.header("🎯 1. Define the Objective")

st.caption(

    "Describe the business outcome you want FinancePilot "

    "to accomplish."

)

user_request = st.text_area(

    "Business Objective",

    value=(

        "Reconcile all pending transactions and "

        "handle any approvals required."

    ),

    height=110,

    placeholder=(

        "Example: Reconcile all pending transactions "

        "and handle any approvals required."

    ),

)

button_col1, button_col2, button_col3 = st.columns(

    [1.5, 1.0, 5]

)

with button_col1:

    run_agent = st.button(

        "▶ Run FinancePilot",

        type="primary",

        use_container_width=True,

    )

with button_col2:

    clear_button = st.button(

        "↻ Clear",

        use_container_width=True,

    )

if clear_button:

    st.session_state.agent_result = None

    st.session_state.approval_message = None

    st.rerun()

# ============================================================

# SECTION 2 - DATA SOURCES

# ============================================================

st.divider()

st.header("📂 2. Data Sources")

st.caption(

    "Available business data that FinancePilot can inspect."

)

# ------------------------------------------------------------

# Dataset cards using NATIVE STREAMLIT

# No HTML here.

# ------------------------------------------------------------

if builtin_datasets:

    dataset_columns = st.columns(

        len(builtin_datasets)

    )

    for column, dataset in zip(

        dataset_columns,

        builtin_datasets,

    ):

        with column:

            with st.container(

                border=True

            ):

                if dataset["name"] == "Bank Transactions":

                    st.subheader(

                        "🏦 Bank Transactions"

                    )

                elif dataset["name"] == "Invoices":

                    st.subheader(

                        "📄 Invoices"

                    )

                else:

                    st.subheader(

                        "📋 Finance Policy"

                    )

                st.caption(

                    dataset["filename"]

                )

                if dataset["type"] == "Text":

                    st.metric(

                        "Documents",

                        dataset["rows"],

                    )

                else:

                    st.metric(

                        "Records",

                        dataset["rows"],

                    )

                st.caption(

                    f"{dataset['columns']} "

                    f"{'column' if dataset['columns'] == 1 else 'columns'}"

                )

# ============================================================

# DATASET SEARCH

# ============================================================

st.subheader("🔎 Search Your Data")

st.caption(

    "Search transaction IDs, vendors, invoice IDs, "

    "amounts and other dataset values."

)

search_query = st.text_input(

    "Dataset Search",

    placeholder=(

        "Try: TechCorp, TXN007, INV-1003, 68000..."

    ),

    label_visibility="collapsed",

)

if search_query:

    total_matches = 0

    st.markdown(

        f"### Results for \`{search_query}\`"

    )

    # --------------------------------------------------------

    # Built-in datasets

    # --------------------------------------------------------

    for dataset in builtin_datasets:

        if dataset["type"] == "Excel":

            matches = search_dataframe(

                dataset["data"],

                search_query,

            )

            if not matches.empty:

                total_matches += len(matches)

                st.write(

                    f"**{dataset['name']} — "

                    f"{len(matches)} match(es)**"

                )

                st.dataframe(

                    matches,

                    use_container_width=True,

                    hide_index=True,

                )

        else:

            if (

                search_query.lower()

                in dataset["data"].lower()

            ):

                total_matches += 1

                st.success(

                    f"Match found in "

                    f"{dataset['name']}"

                )

    # --------------------------------------------------------

    # Uploaded datasets

    # --------------------------------------------------------

    for filename, dataset in (

        st.session_state.uploaded_datasets.items()

    ):

        if dataset["type"] == "table":

            matches = search_dataframe(

                dataset["data"],

                search_query,

            )

            if not matches.empty:

                total_matches += len(matches)

                st.write(

                    f"**{filename} — "

                    f"{len(matches)} match(es)**"

                )

                st.dataframe(

                    matches,

                    use_container_width=True,

                    hide_index=True,

                )

        else:

            if (

                search_query.lower()

                in dataset["data"].lower()

            ):

                total_matches += 1

                st.success(

                    f"Match found in {filename}"

                )

    if total_matches > 0:

        st.info(

            f"Total matches found: "

            f"**{total_matches}**"

        )

    else:

        st.warning(

            "No matching records were found."

        )

# ============================================================

# ADD DATASETS

# ============================================================

st.subheader("➕ Add Additional Datasets")

st.caption(

    "Upload CSV, Excel or TXT files for inspection "

    "and search. Uploaded files do not modify the ERP."

)

uploaded_files = st.file_uploader(

    "Upload additional datasets",

    type=[

        "csv",

        "xlsx",

        "xls",

        "txt",

    ],

    accept_multiple_files=True,

    label_visibility="collapsed",

)

if uploaded_files:

    for uploaded_file in uploaded_files:

        filename = uploaded_file.name

        if (

            filename

            not in st.session_state.uploaded_datasets

        ):

            parsed_dataset = read_uploaded_file(

                uploaded_file

            )

            if parsed_dataset:

                st.session_state.uploaded_datasets[

                    filename

                ] = parsed_dataset

# ------------------------------------------------------------

# Uploaded dataset display

# ------------------------------------------------------------

if st.session_state.uploaded_datasets:

    st.markdown(

        "### Uploaded Datasets"

    )

    for filename, dataset in (

        st.session_state.uploaded_datasets.items()

    ):

        with st.expander(

            f"📄 {filename}"

        ):

            if dataset["type"] == "table":

                col1, col2 = st.columns(2)

                with col1:

                    st.metric(

                        "Records",

                        dataset["rows"],

                    )

                with col2:

                    st.metric(

                        "Columns",

                        dataset["columns"],

                    )

                st.dataframe(

                    dataset["data"].head(20),

                    use_container_width=True,

                    hide_index=True,

                )

            else:

                st.metric(

                    "Documents",

                    dataset["rows"],

                )

                st.text(

                    dataset["data"][:2000]

                )

# ============================================================

# RUN FINANCEPILOT

# ============================================================

if run_agent:

    if not user_request.strip():

        st.warning(

            "Please enter a business objective first."

        )

    else:

        with st.spinner(

            "FinancePilot is understanding the goal "

            "and executing the task..."

        ):

            try:

                # IMPORTANT:

                # FinancePilotAgent does NOT accept

                # user_request in __init__.

                agent = FinancePilotAgent()

                # The request is passed to run_ai_task().

                execution_result = (

                    agent.run_ai_task(

                        user_request

                    )

                )

                st.session_state.agent_result = (

                    execution_result

                )

                st.success(

                    "FinancePilot completed the execution cycle."

                )

            except Exception as error:

                st.error(

                    "FinancePilot could not complete the task."

                )

                st.error(

                    f"{type(error).__name__}: {error}"

                )

                with st.expander(

                    "Technical Error Details"

                ):

                    st.exception(error)

# ============================================================

# RESULTS

# ============================================================

result = st.session_state.agent_result

if result is not None:

    # ========================================================
    # READ-ONLY SEARCH RESULTS
    # ========================================================

    if result.get("mode") == "read_only_search":

        st.divider()
        st.header("🔎 FinancePilot Intelligence Report")
        st.caption(
            "Evidence-based search across available company records."
        )

        file_search = result.get("file_search", {})
        raw_result = file_search.get("result", {})
        matches = raw_result.get("matches", []) or []
        answer = result.get("answer", "")

        # The unique key lets CSS style this report without affecting other cards.
        st.markdown(
            """
            <style>
            .st-key-financepilot-search-report {
                background: linear-gradient(135deg, #EAF2FF 0%, #F4F7FF 100%);
                border: 1px solid #B7CCF8;
                border-left: 6px solid #3157C8;
                border-radius: 16px;
                padding: 1.25rem 1.4rem;
                margin: 0.5rem 0 1rem 0;
                box-shadow: 0 4px 14px rgba(49, 87, 200, 0.08);
            }
            .st-key-financepilot-search-report h3,
            .st-key-financepilot-search-report h4 {
                color: #1E3A8A;
            }
            .st-key-financepilot-search-report [data-testid="stMarkdownContainer"] p {
                margin-bottom: 0.55rem;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        with st.container(key="financepilot-search-report"):
            st.markdown("### 📋 Search Summary")

            if matches:
                st.success(
                    f"Search completed successfully — {len(matches)} matching record(s) found."
                )
                st.divider()

                for index, match in enumerate(matches, start=1):
                    source = match.get("source", "Company records")
                    reason = match.get("reason", "")
                    data = match.get("data", {})

                    st.markdown(f"#### 🔹 Finding {index}")
                    st.markdown(f"**Source**\n\n{source}")

                    if reason:
                        st.markdown(f"**Finding**\n\n{reason}")

                    if isinstance(data, dict) and data:
                        for key, value in data.items():
                            label = str(key).replace("_", " ").title()
                            st.markdown(f"**{label}**")
                            st.write(str(value))
                    elif data:
                        st.markdown("**Record details**")
                        st.write(str(data))

                    if index < len(matches):
                        st.divider()

            else:
                st.info(
                    "No matching records were found in the available datasets."
                )
                if answer:
                    st.markdown("### Search Details")
                    for paragraph in answer.splitlines():
                        paragraph = paragraph.strip()
                        if paragraph:
                            st.markdown(paragraph)

        with st.expander("🛠️ Execution trace"):
            for entry in result.get("execution_log", []):
                st.markdown(f"- {entry}")

    else:

        st.divider()

    st.header(

        "🤖 3. FinancePilot Execution"

    )

    # ========================================================

    # GOAL

    # ========================================================

    st.subheader("🎯 Goal")

    goal = result.get(

        "goal",

        "Goal not available",

    )

    st.info(goal)

    # ========================================================

    # PLAN

    # ========================================================

    st.subheader("🧠 Execution Plan")

    plan = result.get(

        "plan",

        [],

    )

    if isinstance(plan, list):

        for number, step in enumerate(

            plan,

            start=1,

        ):

            st.write(

                f"**{number}.** {step}"

            )

    elif isinstance(plan, dict):

        for key, value in plan.items():

            st.write(

                f"**{key}:** {value}"

            )

    else:

        st.write(plan)

    # ========================================================

    # SUMMARY

    # ========================================================

    st.subheader(

        "📊 Execution Summary"

    )

    summary = result.get(

        "execution_summary",

        {},

    )

    total = summary.get(

        "total",

        0,

    )

    processed = summary.get(

        "processed",

        0,

    )

    approval_required = summary.get(

        "approval_required",

        0,

    )

    review_required = summary.get(

        "review_required",

        0,

    )

    verified = summary.get(

        "verified",

        0,

    )

    verification_failed = summary.get(

        "verification_failed",

        0,

    )

    row1 = st.columns(3)

    row2 = st.columns(3)

    with row1[0]:

        st.metric(

            "Transactions",

            total,

        )

    with row1[1]:

        st.metric(

            "Processed",

            processed,

        )

    with row1[2]:

        st.metric(

            "Approval Required",

            approval_required,

        )

    with row2[0]:

        st.metric(

            "Review Required",

            review_required,

        )

    with row2[1]:

        st.metric(

            "Verified",

            verified,

        )

    with row2[2]:

        st.metric(

            "Verification Failed",

            verification_failed,

        )

    # ========================================================

    # TRANSACTION DECISIONS

    # ========================================================

    st.subheader(

        "💳 Transaction Decisions"

    )

    reconciliation = result.get(

        "reconciliation",

        [],

    )

    if reconciliation:

        transaction_rows = []

        for item in reconciliation:

            transaction_rows.append(

                {

                    "Transaction":

                        item.get(

                            "transaction_id",

                            "-",

                        ),

                    "Vendor":

                        item.get(

                            "vendor",

                            "-",

                        ),

                    "Amount":

                        item.get(

                            "amount",

                            "-",

                        ),

                    "Decision":

                        item.get(

                            "decision",

                            "-",

                        ),

                    "Reason":

                        item.get(

                            "reason",

                            "-",

                        ),

                }

            )

        transaction_df = pd.DataFrame(

            transaction_rows

        )

        st.dataframe(

            transaction_df,

            use_container_width=True,

            hide_index=True,

        )

    else:

        st.info(

            "No reconciliation results were returned."

        )

    # ========================================================

    # HUMAN APPROVAL

    # ========================================================

    st.subheader(

        "👤 Human Approval"

    )

    pending_approvals = (

        get_pending_approvals()

    )

    if pending_approvals:

        for approval in pending_approvals:

            approval_id = approval[0]

            transaction_id = approval[1]

            vendor = approval[2]

            amount = approval[3]

            status = approval[4]

            with st.container(

                border=True

            ):

                st.markdown(

                    "### ⚠️ Approval Required"

                )

                left, right = st.columns(2)

                with left:

                    st.write(

                        f"**Approval ID:** "

                        f"{approval_id}"

                    )

                    st.write(

                        f"**Transaction:** "

                        f"{transaction_id}"

                    )

                    st.write(

                        f"**Vendor:** "

                        f"{vendor}"

                    )

                with right:

                    st.write(

                        f"**Amount:** "

                        f"₹{amount:,.2f}"

                    )

                    st.write(

                        f"**Status:** "

                        f"{status}"

                    )

                approve_button = st.button(

                    f"✓ Approve {transaction_id}",

                    key=f"approve_{transaction_id}",

                    type="primary",

                    use_container_width=True,

                )

                if approve_button:
                    try:
                        approval_result = approve_transaction(
                            transaction_id,
                            "Finance Manager",
                        )

                        if approval_result.get("success", False):
                            st.success(
                                f"Approval recorded for {transaction_id}."
                            )

                            agent = FinancePilotAgent()
                            processing_results = (
                                agent.check_approved_transactions(transaction_id)
                            )

                            st.subheader(
                                f"{transaction_id} — Processing Results"
                            )

                            payment_processed = any(
                                item.get("success") is True
                                and item.get("action") == "Payment"
                                for item in processing_results
                            )
                            verified = any(
                                item.get("verified") is True
                                for item in processing_results
                            )

                            if verified:
                                st.success(
                                    "Payment processed and independently verified."
                                )
                            elif payment_processed:
                                st.warning(
                                    "Payment processing succeeded, but independent "
                                    "verification did not confirm success."
                                )
                            else:
                                st.error(
                                    "Payment was not confirmed as successfully processed."
                                )

                            for item in processing_results:
                                if item.get("reason"):
                                    st.write(
                                        f"**{item.get('action', 'Result')}:** "
                                        f"{item['reason']}"
                                    )

                            with st.expander("Technical results"):
                                st.json(processing_results)
                        else:
                            st.error(
                                approval_result.get(
                                    "reason",
                                    approval_result.get("message", "Approval failed."),
                                )
                            )
                    except Exception as error:
                        st.error(
                            f"Approval workflow error: {type(error).__name__}: {error}"
                        )

    else:

        st.success(

            "No pending human approvals."

        )

    # ========================================================

    # VERIFICATION

    # ========================================================

    st.subheader(

        "✅ Independent Verification"

    )

    verification_results = result.get(

        "verification",

        [],

    )

    if verification_results:

        for verification in (

            verification_results

        ):

            transaction_id = (

                verification.get(

                    "transaction_id",

                    "-",

                )

            )

            verified_status = (

                verification.get(

                    "verified",

                    False,

                )

            )

            reason = (

                verification.get(

                    "reason",

                    "-",

                )

            )

            if verified_status:

                st.success(

                    f"✓ {transaction_id}: "

                    f"VERIFIED — {reason}"

                )

            else:

                st.error(

                    f"✗ {transaction_id}: "

                    f"VERIFICATION FAILED — "

                    f"{reason}"

                )

    else:

        st.info(

            "No completed transactions required "

            "verification in this execution."

        )

    # ========================================================

    # RECOVERY

    # ========================================================

    st.subheader(

        "🔄 Recovery & Exceptions"

    )

    recovery = result.get(

        "recovery",

        [],

    )

    if recovery:

        for item in recovery:

            transaction_id = item.get(

                "transaction_id",

                "-",

            )

            reason = item.get(

                "reason",

                "-",

            )

            st.warning(

                f"{transaction_id}: {reason}"

            )

    else:

        st.success(

            "No recovery actions were required."

        )

# ============================================================

# LANDING PAGE

# ============================================================

else:

    st.divider()

    st.header(

        "How FinancePilot Works"

    )

    step1, step2, step3 = st.columns(3)

    with step1:

        with st.container(

            border=True

        ):

            st.subheader(

                "🎯 Understand"

            )

            st.write(

                "FinancePilot interprets the business "

                "objective and determines the required work."

            )

    with step2:

        with st.container(

            border=True

        ):

            st.subheader(

                "⚙️ Execute"

            )

            st.write(

                "It retrieves data, reconciles transactions, "

                "applies finance policies and requests "

                "human approval when required."

            )

    with step3:

        with st.container(

            border=True

        ):

            st.subheader(

                "✅ Verify"

            )

            st.write(

                "Completed transactions are independently "

                "verified before FinancePilot considers "

                "the task complete."

            )

    st.info(

        "Enter an objective above and click "

        "**Run FinancePilot** to begin."

    )

# ============================================================

# FOOTER

# ============================================================

st.markdown(

    '<div class="footer-text">'

    'FinancePilot AI • Autonomous Finance Operations'

    '</div>',

    unsafe_allow_html=True,

)