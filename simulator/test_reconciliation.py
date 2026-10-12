import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.tools.reconciliation import reconcile_transaction


TRANSACTIONS = [
    "TXN001",
    "TXN002",
    "TXN003",
    "TXN004",
    "TXN005",
    "TXN006",
    "TXN007",
    "TXN008",
    "TXN009",
    "TXN010",
]


def run_tests():
    print("\n===== FINANCEPILOT RECONCILIATION TEST =====\n")

    for transaction_id in TRANSACTIONS:
        result = reconcile_transaction(transaction_id)

        print(
            f"{transaction_id} -> "
            f"{result['decision']} | "
            f"{result['reason']}"
        )

    print("\n===== TEST COMPLETED =====")


if __name__ == "__main__":
    run_tests()