import sqlite3

DATABASE = "data/financepilot.db"


def get_connection():
    return sqlite3.connect(DATABASE)


def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()

    # Payment records
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            transaction_id TEXT PRIMARY KEY,
            invoice_id TEXT,
            vendor TEXT,
            amount REAL,
            status TEXT,
            verification_status TEXT
        )
    """)

    # Human approval records
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS approvals (
            approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT,
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approved_at TIMESTAMP,
            status TEXT,
            approver TEXT
        )
    """)
        # Audit log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT,
            action TEXT,
            decision TEXT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    initialize_database()
    print("ERP database initialized successfully.")