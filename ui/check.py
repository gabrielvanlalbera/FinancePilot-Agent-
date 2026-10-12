import sqlite3

conn = sqlite3.connect("data/financepilot.db")

result = conn.execute(
    "SELECT transaction_id, status FROM bank_transactions WHERE transaction_id = ?",
    ("TXN007",)
).fetchone()

print(result)

conn.close()