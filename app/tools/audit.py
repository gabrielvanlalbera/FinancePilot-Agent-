import sqlite3

DATABASE = "data/financepilot.db"


def get_connection():
    return sqlite3.connect(DATABASE)


def log_action(transaction_id, action, decision, details):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO audit_log (
            transaction_id,
            action,
            decision,
            details
        )
        VALUES (?, ?, ?, ?)
    """, (
        transaction_id,
        action,
        decision,
        details
    ))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "transaction_id": transaction_id,
        "action": action,
        "decision": decision,
        "details": details
    }