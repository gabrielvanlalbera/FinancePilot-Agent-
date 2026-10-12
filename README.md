# FinancePilot — Autonomous AI Finance & Reconciliation Employee

FinancePilot is a prototype finance operations assistant that helps review bank transactions against invoice records, identify exceptions, apply payment-policy rules, request human approval when required, and verify completed payments. It includes a Streamlit dashboard, local Excel datasets, a SQLite-backed ERP simulator, and automated tests.

> **Prototype status:** FinancePilot currently uses a deterministic, rule-based local planner. Live OpenAI planning is not enabled because the API request was blocked by insufficient API credits. Do not interpret the prototype as a production payment system.

## Key capabilities

- **Company-data search:** Search the supplied bank-transaction and invoice datasets for vendors, transaction IDs, invoice references, amount mismatches, and missing invoice references.
- **Policy-based reconciliation:** Compare vendor, invoice reference, amount, and invoice approval status.
- **Payment guardrails:** The current sample policy allows eligible matched payments of ₹50,000 or less to be auto-processed. Payments above ₹50,000 require human approval.
- **Exception handling:** Transactions with amount mismatches, vendor mismatches, or missing invoices are held for review.
- **Independent verification:** Successful payments are checked after processing.
- **Audit trail:** Important reconciliation, payment, approval, recovery, and verification actions are logged.
- **Dashboard:** Streamlit interface for submitting requests and viewing decisions, approvals, and outcomes.

## Architecture

```text
User request
    |
    v
Streamlit dashboard (ui/dashboard.py)
    |
    v
FinancePilot agent (app/agent/agent.py)
    |
    +--> Local rule-based planner (app/agent/llm_agent.py)
    |
    +--> File search (app/tools/file_search.py)
    |
    +--> Reconciliation and policy checks (app/tools/reconciliation.py)
    |
    +--> Finance / payment tools (app/tools/finance_tools.py)
    |
    +--> Independent verification (app/tools/verification.py)
    |
    +--> Audit logging (app/tools/audit.py)
    |
    v
SQLite ERP simulator (simulator/erp.py; data/financepilot.db)
```

## Project structure

```text
financepilot/
├── app/
│   ├── agent/
│   │   ├── agent.py
│   │   └── llm_agent.py
│   └── tools/
│       ├── audit.py
│       ├── file_search.py
│       ├── finance_tools.py
│       ├── reconciliation.py
│       └── verification.py
├── data/
│   ├── bank_transactions/transactions.xlsx
│   ├── invoice/invoice.xlsx
│   ├── policies/finance_policy.txt
│   └── financepilot.db
├── simulator/
├── tests/
│   └── test_financepilot.py
├── ui/
│   └── dashboard.py
├── requirements.txt
└── README.md
```

## Requirements

- Python 3.13 (the project has been tested in a Python 3.13 virtual environment)
- The dependencies listed in `requirements.txt`

## Setup

Run these commands from the project root.

### 1. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can run the environment's Python directly using `.\.venv\Scripts\python.exe`.

### 2. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 3. Start the dashboard

```powershell
streamlit run ui\dashboard.py
```

Streamlit will print a local URL in the terminal. Open that URL in your browser.

## Example prompts

Try these prompts in the dashboard:

**Search company data**
- `Find all transactions associated with TechCorp`
- `Identify transactions with amount mismatches`
- `Find all bank transactions whose invoice references do not exist`

**Read-only review**
- `Review all pending transactions without changing anything`
- `Explain which transactions require approval`

**Finance operation**
- `Reconcile all pending transactions`

Search and read-only review requests should not execute payments. A finance-operation request can process policy-eligible transactions and request approvals for transactions over the configured limit. Review the decisions before running finance operations against the local database.

## Sample policy behavior

The policy and sample datasets are designed to demonstrate common reconciliation outcomes:

| Condition | Expected handling |
|---|---|
| Vendor, reference, amount, and invoice status match; amount is ₹50,000 or less | Eligible for automatic processing |
| Amount exceeds ₹50,000 | Human approval required |
| Amount mismatch | Hold for review; do not process |
| Vendor mismatch | Hold for review; do not process |
| Invoice reference does not exist | Hold for review; do not process |
| Payment processed successfully | Independently verify and record the result |

The policy limit is a prototype configuration, not financial or legal advice.

## Automated tests

Run the test suite:

```powershell
python -m pytest tests/ -v
```

The current test suite has **8 passing tests** covering:
1. Processing an eligible low-value transaction.
2. Blocking an amount mismatch.
3. Blocking a transaction with a missing invoice.
4. Requiring approval for a high-value payment.
5. Processing an approved high-value payment.
6. Preventing duplicate payments.
7. Updating verification status and writing an audit entry.
8. Preventing duplicate pending approval requests.

Most recently reported test result: `8 passed in 0.27s`. Run the command again in your own environment to confirm the current result.

## Safety and limitations

- This is a local prototype with a simulated ERP/database, not a live bank or production accounting integration.
- The current planner is deterministic and rule-based; it is **not currently using a live LLM API**.
- Search and review are intended to be read-only. Payment execution should only occur through an explicit finance-operation request and must follow policy.
- Approval is simulated locally; it does not represent a real organization's approval identity or authorization infrastructure.
- The provided datasets are sample project data. Results are only as reliable as those records and the reconciliation rules.
- The current test suite covers eight scenarios and does not prove correctness for every possible input or production failure mode.
- Before production use, add stronger authentication and authorization, durable audit controls, transaction-safe idempotency, secrets management, broader automated tests, monitoring, and integration testing with the actual finance system.

## Suggested demo walkthrough (3–5 minutes)

1. Introduce the goal: reconcile bank transactions against invoices safely.
2. Search for a vendor such as TechCorp and show the source records.
3. Run a read-only review and explain the mismatch, vendor exception, and missing-invoice cases.
4. Run reconciliation and show automatic-processing eligibility versus approval-required decisions.
5. Demonstrate the human-approval flow using an eligible high-value transaction in the local simulator.
6. Show independent verification and the audit trail.
7. End by explaining the current limitation: deterministic local planning rather than live LLM orchestration.

## Security note

Do not commit `.env`, API keys, virtual environments, caches, or a local database containing sensitive operational data. Review `.gitignore` and `git status` before pushing the project to a public repository.
