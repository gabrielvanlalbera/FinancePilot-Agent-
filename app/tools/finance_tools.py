import sqlite3

DATABASE = "data/financepilot.db"


def get_connection():
    return sqlite3.connect(DATABASE)


def get_pending_transactions():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            transaction_id,
            vendor,
            amount,
            reference,
            status
        FROM bank_transactions
        WHERE status = 'Pending'
        ORDER BY transaction_id
    """)

    rows = cursor.fetchall()
    conn.close()

    transactions = []

    for row in rows:
        transactions.append({
            "transaction_id": row[0],
            "vendor": row[1],
            "amount": row[2],
            "reference": row[3],
            "status": row[4]
        })

    return transactions


def get_invoice(invoice_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            invoice_id,
            vendor,
            invoice_date,
            due_date,
            amount,
            status,
            Payment
        FROM invoices
        WHERE invoice_id = ?
    """, (invoice_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "invoice_id": row[0],
        "vendor": row[1],
        "invoice_date": row[2],
        "due_date": row[3],
        "amount": row[4],
        "status": row[5],
        "payment": row[6]
    }

def process_payment(transaction_id):
    """Process a payment only after policy checks, preventing duplicates."""

    conn = get_connection()

    try:
        # Lock the SQLite write transaction while checking and inserting.
        conn.execute("BEGIN IMMEDIATE")
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
                "success": False,
                "transaction_id": transaction_id,
                "message": "Transaction not found",
            }

        txn_id, vendor, amount, reference, status = transaction

        if status != "Pending":
            return {
                "success": False,
                "transaction_id": txn_id,
                "message": f"Transaction is already {status}",
            }

        # Fail closed if a payment record already exists.
        cursor.execute(
            """
            SELECT invoice_id, status, verification_status
            FROM payments
            WHERE transaction_id = ?
            """,
            (txn_id,),
        )
        existing_payment = cursor.fetchone()

        if existing_payment:
            return {
                "success": False,
                "transaction_id": txn_id,
                "message": (
                    "An existing payment record was found. "
                    "Manual review is required; no new payment was created."
                ),
                "existing_payment": {
                    "invoice_id": existing_payment[0],
                    "status": existing_payment[1],
                    "verification_status": existing_payment[2],
                },
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
                "success": False,
                "transaction_id": txn_id,
                "message": f"Invoice {reference} not found",
            }

        invoice_id, invoice_vendor, invoice_amount, invoice_status = invoice

        if str(vendor).strip().casefold() != str(invoice_vendor).strip().casefold():
            return {
                "success": False,
                "transaction_id": txn_id,
                "message": "Vendor mismatch",
            }

        if round(float(amount), 2) != round(float(invoice_amount), 2):
            return {
                "success": False,
                "transaction_id": txn_id,
                "message": "Amount mismatch",
            }

        if str(invoice_status).strip().casefold() != "approved":
            return {
                "success": False,
                "transaction_id": txn_id,
                "message": "Invoice is not approved",
            }

        # High-value payments require an approved human authorization.
        if float(amount) > 50000:
            cursor.execute(
                """
                SELECT status
                FROM approvals
                WHERE transaction_id = ?
                ORDER BY approval_id DESC
                LIMIT 1
                """,
                (txn_id,),
            )
            approval = cursor.fetchone()

            if not approval or approval[0] != "Approved":
                return {
                    "success": False,
                    "transaction_id": txn_id,
                    "message": "Human approval required before processing",
                }

        cursor.execute(
            """
            INSERT INTO payments (
                transaction_id,
                invoice_id,
                vendor,
                amount,
                status,
                verification_status
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                txn_id,
                invoice_id,
                vendor,
                amount,
                "Processed",
                "Pending Verification",
            ),
        )

        cursor.execute(
            """
            UPDATE bank_transactions
            SET status = 'Processed'
            WHERE transaction_id = ? AND status = 'Pending'
            """,
            (txn_id,),
        )

        if cursor.rowcount != 1:
            raise RuntimeError(
                "Transaction status changed unexpectedly; payment rolled back"
            )

        cursor.execute(
            """
            INSERT INTO audit_log (
                transaction_id, action, decision, details
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                txn_id,
                "Payment Processing",
                "PROCESSED",
                f"Invoice {invoice_id}; amount ₹{float(amount):,.2f}; "
                "policy checks passed and payment record created",
            ),
        )
        conn.commit()

        return {
            "success": True,
            "transaction_id": txn_id,
            "invoice_id": invoice_id,
            "amount": amount,
            "message": "Payment processed successfully",
            "verification_status": "Pending Verification",
        }

    except Exception as exc:
        conn.rollback()
        return {
            "success": False,
            "transaction_id": transaction_id,
            "message": f"Payment failed safely: {exc}",
        }

    finally:
        conn.close()

def request_approval(transaction_id):
    """Request approval without creating duplicate active requests."""

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT transaction_id, amount, status
            FROM bank_transactions
            WHERE transaction_id = ?
            """,
            (transaction_id,),
        )
        transaction = cursor.fetchone()

        if not transaction:
            return {
                "success": False,
                "transaction_id": transaction_id,
                "message": "Transaction not found",
            }

        txn_id, amount, status = transaction

        if status != "Pending":
            return {
                "success": False,
                "transaction_id": txn_id,
                "message": f"Transaction is already {status}",
            }

        # Reuse the latest approval instead of duplicating it.
        cursor.execute(
            """
            SELECT approval_id, status, approver
            FROM approvals
            WHERE transaction_id = ?
            ORDER BY approval_id DESC
            LIMIT 1
            """,
            (transaction_id,),
        )
        existing = cursor.fetchone()

        if existing:
            approval_id, approval_status, approver = existing

            if approval_status == "Pending":
                return {
                    "success": True,
                    "transaction_id": txn_id,
                    "approval_id": approval_id,
                    "status": "Pending",
                    "message": "Approval already requested",
                }

            if approval_status == "Approved":
                return {
                    "success": True,
                    "transaction_id": txn_id,
                    "approval_id": approval_id,
                    "status": "Approved",
                    "approver": approver,
                    "message": "Existing approval reused",
                }

            # Do not silently create another request after a
            # rejected or otherwise closed approval.
            return {
                "success": False,
                "transaction_id": txn_id,
                "approval_id": approval_id,
                "status": approval_status,
                "message": (
                    "Previous approval is closed; "
                    "manual review is required"
                ),
            }

        cursor.execute(
            """
            INSERT INTO approvals (transaction_id, status)
            VALUES (?, ?)
            """,
            (transaction_id, "Pending"),
        )

        approval_id = cursor.lastrowid
        conn.commit()

        return {
            "success": True,
            "transaction_id": txn_id,
            "approval_id": approval_id,
            "amount": amount,
            "status": "Pending",
            "message": "Human approval requested",
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def approve_transaction(transaction_id, approver):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT approval_id, status
        FROM approvals
        WHERE transaction_id = ?
        ORDER BY approval_id DESC
        LIMIT 1
    """, (transaction_id,))

    approval = cursor.fetchone()

    if not approval:
        conn.close()
        return {
            "success": False,
            "transaction_id": transaction_id,
            "message": "No approval request found"
        }

    approval_id, status = approval

    if status != "Pending":
        conn.close()
        return {
            "success": False,
            "transaction_id": transaction_id,
            "message": f"Approval is already {status}"
        }

    cursor.execute("""
        UPDATE approvals
        SET status = 'Approved',
            approved_at = CURRENT_TIMESTAMP,
            approver = ?
        WHERE approval_id = ?
    """, (approver, approval_id))
    
    cursor.execute(
            """
        INSERT INTO audit_log (
                transaction_id, action, decision, details
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                txn_id,
                "Payment Processing",
                "PROCESSED",
                (
                    f"Invoice {invoice_id}; amount ₹{float(amount):,.2f}; "
                    "policy checks passed and payment record created"
                ),
            ),
        )

    conn.commit()
    conn.close()

    return {
        "success": True,
        "transaction_id": transaction_id,
        "approval_id": approval_id,
        "status": "Approved",
        "approver": approver,
        "message": "Transaction approved successfully"
    }