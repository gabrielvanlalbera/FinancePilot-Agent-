
import sqlite3

DATABASE = "data/financepilot.db"


def get_connection():
    return sqlite3.connect(DATABASE)


def write_audit(cursor, transaction_id, action, decision, details):
    """Write an audit event using the current database transaction."""
    cursor.execute(
        """
        INSERT INTO audit_log (
            transaction_id, action, decision, details
        )
        VALUES (?, ?, ?, ?)
        """,
        (transaction_id, action, decision, details),
    )


def verify_payment(transaction_id):
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT transaction_id, status
            FROM bank_transactions
            WHERE transaction_id = ?
            """,
            (transaction_id,),
        )
        transaction = cursor.fetchone()

        if not transaction:
            write_audit(
                cursor, transaction_id, "Verification",
                "FAILED", "Transaction not found",
            )
            conn.commit()
            return {
                "verified": False,
                "transaction_id": transaction_id,
                "reason": "Transaction not found",
            }

        txn_id, transaction_status = transaction

        cursor.execute(
            """
            SELECT transaction_id, invoice_id, amount,
                   status, verification_status
            FROM payments
            WHERE transaction_id = ?
            """,
            (transaction_id,),
        )
        payment = cursor.fetchone()

        if not payment:
            write_audit(
                cursor, txn_id, "Verification",
                "FAILED", "Payment record not found",
            )
            conn.commit()
            return {
                "verified": False,
                "transaction_id": txn_id,
                "reason": "Payment record not found",
            }

        payment_txn, invoice_id, amount, payment_status, verification_status = payment

        if transaction_status != "Processed":
            reason = "Bank transaction is not marked as Processed"
        elif payment_status != "Processed":
            reason = "Payment record is not marked as Processed"
        else:
            reason = None

        if reason:
            write_audit(
                cursor, txn_id, "Verification", "FAILED", reason
            )
            conn.commit()
            return {
                "verified": False,
                "transaction_id": txn_id,
                "reason": reason,
            }

        cursor.execute(
            """
            UPDATE payments
            SET verification_status = 'Verified'
            WHERE transaction_id = ?
            """,
            (txn_id,),
        )

        write_audit(
            cursor,
            txn_id,
            "Payment Verification",
            "VERIFIED",
            (
                f"Invoice {invoice_id}; amount ₹{float(amount):,.2f}; "
                "bank and payment records both marked Processed"
            ),
        )

        conn.commit()

        return {
            "verified": True,
            "transaction_id": txn_id,
            "invoice_id": invoice_id,
            "amount": amount,
            "reason": "Payment independently verified",
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    print(verify_payment("TXN001"))
