import pandas as pd
import sqlite3

DATABASE = "data/financepilot.db"

BANK_FILE = "data/bank_transactions/transactions.xlsx"
INVOICE_FILE = "data/invoice/invoice.xlsx"


def load_data():
    conn = sqlite3.connect(DATABASE)

    # Read Excel files
    transactions = pd.read_excel(BANK_FILE)
    invoices = pd.read_excel(INVOICE_FILE)

    print("Bank columns:", list(transactions.columns))
    print("Invoice columns:", list(invoices.columns))

    # Store transactions
    transactions.to_sql(
        "bank_transactions",
        conn,
        if_exists="replace",
        index=False
    )

    # Store invoices
    invoices.to_sql(
        "invoices",
        conn,
        if_exists="replace",
        index=False
    )

    conn.commit()
    conn.close()

    print("Bank transactions loaded:", len(transactions))
    print("Invoices loaded:", len(invoices))
    print("Data loading completed successfully.")


if __name__ == "__main__":
    load_data()