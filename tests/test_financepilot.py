
import sqlite3

import pytest


from app.tools import finance_tools, reconciliation, verification


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Create an isolated database for every test."""
    db_path = tmp_path / "financepilot_test.db"

    for module in (finance_tools, reconciliation, verification):
        monkeypatch.setattr(module, "DATABASE", str(db_path))

    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE bank_transactions (
            transaction_id TEXT PRIMARY KEY,
            date TEXT,
            vendor TEXT,
            amount REAL,
            reference TEXT,
            status TEXT DEFAULT 'Pending'
        );

        CREATE TABLE invoices (
            invoice_id TEXT PRIMARY KEY,
            vendor TEXT,
            invoice_date TEXT,
            due_date TEXT,
            amount REAL,
            status TEXT,
            payment TEXT
        );

        CREATE TABLE payments (
            transaction_id TEXT PRIMARY KEY,
            invoice_id TEXT,
            vendor TEXT,
            amount REAL,
            status TEXT,
            verification_status TEXT
        );

        CREATE TABLE approvals (
            approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT,
            requested_at TEXT DEFAULT CURRENT_TIMESTAMP,
            approved_at TEXT,
            status TEXT,
            approver TEXT
        );

        CREATE TABLE audit_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT,
            action TEXT,
            decision TEXT,
            details TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    conn.executemany(
        """
        INSERT INTO bank_transactions
        (transaction_id, date, vendor, amount, reference, status)
        VALUES (?, ?, ?, ?, ?, 'Pending')
        """,
        [
            ("TXN001", "2026-10-01", "TechCorp", 42500, "INV-1001"),
            ("TXN002", "2026-10-01", "DataSystems", 72000, "INV-1002"),
            ("TXN003", "2026-10-02", "CloudWorks", 150000, "INV-1003"),
            ("TXN010", "2026-10-05", "OfficeMart", 12000, "INV-1010"),
        ],
    )

    conn.executemany(
        """
        INSERT INTO invoices
        (invoice_id, vendor, invoice_date, due_date, amount, status, payment)
        VALUES (?, ?, ?, ?, ?, 'Approved', 'Net 30')
        """,
        [
            ("INV-1001", "TechCorp", "2026-09-28", "2026-10-10", 42500),
            ("INV-1002", "DataSystems", "2026-09-29", "2026-10-12", 75000),
            ("INV-1003", "CloudWorks", "2026-09-30", "2026-10-15", 150000),
        ],
    )

    conn.commit()
    conn.close()

    return db_path


def query_db(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_matching_low_value_transaction_can_be_processed(test_db):
    result = reconciliation.reconcile_transaction("TXN001")

    assert result["decision"] == "AUTO_PROCESS"
    assert result["policy_checklist"]["vendor_match"] is True
    assert result["policy_checklist"]["amount_match"] is True

    payment = finance_tools.process_payment("TXN001")

    assert payment["success"] is True
    assert payment["verification_status"] == "Pending Verification"


def test_amount_mismatch_is_blocked(test_db):
    result = reconciliation.reconcile_transaction("TXN002")

    assert result["decision"] == "REVIEW"
    assert result["policy_checklist"]["amount_match"] is False

    payment = finance_tools.process_payment("TXN002")

    assert payment["success"] is False
    assert "mismatch" in payment["message"].lower()

    assert query_db(
        test_db,
        "SELECT COUNT(*) FROM payments WHERE transaction_id = ?",
        ("TXN002",),
    )[0][0] == 0


def test_missing_invoice_is_blocked(test_db):
    result = reconciliation.reconcile_transaction("TXN010")

    assert result["decision"] == "REVIEW"
    assert "not found" in result["reason"].lower()

    payment = finance_tools.process_payment("TXN010")

    assert payment["success"] is False
    assert query_db(
        test_db,
        "SELECT COUNT(*) FROM payments WHERE transaction_id = ?",
        ("TXN010",),
    )[0][0] == 0


def test_high_value_payment_requires_approval(test_db):
    result = reconciliation.reconcile_transaction("TXN003")

    assert result["decision"] == "APPROVAL_REQUIRED"

    payment = finance_tools.process_payment("TXN003")

    assert payment["success"] is False
    assert "approval" in payment["message"].lower()

    assert query_db(
        test_db,
        "SELECT COUNT(*) FROM payments WHERE transaction_id = ?",
        ("TXN003",),
    )[0][0] == 0


def test_approved_high_value_payment_can_be_processed(test_db):
    conn = sqlite3.connect(test_db)
    conn.execute(
        """
        INSERT INTO approvals (transaction_id, status, approver, approved_at)
        VALUES (?, 'Approved', ?, CURRENT_TIMESTAMP)
        """,
        ("TXN003", "Finance Manager"),
    )
    conn.commit()
    conn.close()

    result = finance_tools.process_payment("TXN003")

    assert result["success"] is True

    payment = query_db(
        test_db,
        "SELECT status, verification_status FROM payments WHERE transaction_id = ?",
        ("TXN003",),
    )

    assert payment == [("Processed", "Pending Verification")]


def test_duplicate_payment_is_prevented(test_db):
    first = finance_tools.process_payment("TXN001")
    second = finance_tools.process_payment("TXN001")

    assert first["success"] is True
    assert second["success"] is False

    assert query_db(
        test_db,
        "SELECT COUNT(*) FROM payments WHERE transaction_id = ?",
        ("TXN001",),
    )[0][0] == 1


def test_verification_updates_payment_and_audit(test_db):
    finance_tools.process_payment("TXN001")

    result = verification.verify_payment("TXN001")

    assert result["verified"] is True

    payment = query_db(
        test_db,
        "SELECT verification_status FROM payments WHERE transaction_id = ?",
        ("TXN001",),
    )

    assert payment == [("Verified",)]

    audit = query_db(
        test_db,
        """
        SELECT action, decision FROM audit_log
        WHERE transaction_id = ?
        """,
        ("TXN001",),
    )

    assert ("Payment Processing", "PROCESSED") in audit
    assert ("Payment Verification", "VERIFIED") in audit


def test_approval_request_does_not_duplicate_pending_request(test_db):
    first = finance_tools.request_approval("TXN003")
    second = finance_tools.request_approval("TXN003")

    assert first["success"] is True
    assert second["success"] is True
    assert first["approval_id"] == second["approval_id"]

    assert query_db(
        test_db,
        "SELECT COUNT(*) FROM approvals WHERE transaction_id = ?",
        ("TXN003",),
    )[0][0] == 1
