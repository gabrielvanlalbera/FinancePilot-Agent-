import sqlite3

DATABASE = "data/financepilot.db"


def check_database():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    print("\n--- BANK TRANSACTIONS ---")

    cursor.execute("SELECT * FROM bank_transactions")
    transactions = cursor.fetchall()

    for transaction in transactions:
        print(transaction)

    print("\n--- INVOICES ---")

    cursor.execute("SELECT * FROM invoices")
    invoices = cursor.fetchall()

    for invoice in invoices:
        print(invoice)

    print("\n--- PAYMENT TABLE ---")

    cursor.execute("SELECT * FROM payments")
    payments = cursor.fetchall()

    for payment in payments:
        print(payment)

    conn.close()


if __name__ == "__main__":
    check_database()