
import sqlite3

DATABASE = "data/financepilot.db"
AUTO_PROCESS_LIMIT = 50000


def get_connection():
    return sqlite3.connect(DATABASE)


def build_policy_checklist(
    vendor_match=None,
    amount_match=None,
    invoice_approved=None,
    amount=None,
):
    return {
        "vendor_match": vendor_match,
        "amount_match": amount_match,
        "invoice_approved": invoice_approved,
        "within_auto_process_limit": (
            amount is not None and float(amount) <= AUTO_PROCESS_LIMIT
        ),
        "auto_process_limit": AUTO_PROCESS_LIMIT,
    }


def reconcile_transaction(transaction_id):
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT transaction_id, vendor, amount, reference, status
            FROM bank_transactions
            WHERE transaction_id = ?
            """,
            (transaction_id,),
        )
        transaction = cursor.fetchone()

        if not transaction:
            return {
                "transaction_id": transaction_id,
                "decision": "REVIEW",
                "reason": "Transaction not found",
                "policy_checklist": build_policy_checklist(),
            }

        txn_id, vendor, amount, reference, status = transaction

        checklist = build_policy_checklist(amount=amount)

        if status != "Pending":
            return {
                "transaction_id": txn_id,
                "decision": "REVIEW",
                "reason": f"Transaction status is {status}, not Pending",
                "policy_checklist": checklist,
            }

        cursor.execute(
            """
            SELECT invoice_id, vendor, amount, status
            FROM invoices
            WHERE invoice_id = ?
            """,
            (reference,),
        )
        invoice = cursor.fetchone()

        if not invoice:
            return {
                "transaction_id": txn_id,
                "decision": "REVIEW",
                "reason": f"Invoice {reference} not found",
                "policy_checklist": checklist,
            }

        invoice_id, invoice_vendor, invoice_amount, invoice_status = invoice

        vendor_match = (
            str(vendor).strip().casefold()
            == str(invoice_vendor).strip().casefold()
        )

        checklist = build_policy_checklist(
            vendor_match=vendor_match,
            amount=amount,
        )

        if not vendor_match:
            return {
                "transaction_id": txn_id,
                "invoice_id": invoice_id,
                "decision": "REVIEW",
                "reason": "Vendor mismatch",
                "policy_checklist": checklist,
            }

        amount_match = float(amount) == float(invoice_amount)

        checklist = build_policy_checklist(
            vendor_match=True,
            amount_match=amount_match,
            amount=amount,
        )

        if not amount_match:
            return {
                "transaction_id": txn_id,
                "invoice_id": invoice_id,
                "decision": "REVIEW",
                "reason": "Amount mismatch",
                "transaction_amount": amount,
                "invoice_amount": invoice_amount,
                "difference": float(amount) - float(invoice_amount),
                "policy_checklist": checklist,
            }

        invoice_approved = (
            str(invoice_status).strip().casefold() == "approved"
        )

        checklist = build_policy_checklist(
            vendor_match=True,
            amount_match=True,
            invoice_approved=invoice_approved,
            amount=amount,
        )

        if not invoice_approved:
            return {
                "transaction_id": txn_id,
                "invoice_id": invoice_id,
                "decision": "REVIEW",
                "reason": "Invoice is not approved",
                "policy_checklist": checklist,
            }

        if float(amount) > AUTO_PROCESS_LIMIT:
            return {
                "transaction_id": txn_id,
                "invoice_id": invoice_id,
                "decision": "APPROVAL_REQUIRED",
                "reason": (
                    "Transaction exceeds automatic processing limit "
                    f"of ₹{AUTO_PROCESS_LIMIT:,.0f}"
                ),
                "amount": amount,
                "policy_checklist": checklist,
            }

        return {
            "transaction_id": txn_id,
            "invoice_id": invoice_id,
            "decision": "AUTO_PROCESS",
            "reason": "All finance policy checks passed",
            "amount": amount,
            "policy_checklist": checklist,
        }

    finally:
        conn.close()
