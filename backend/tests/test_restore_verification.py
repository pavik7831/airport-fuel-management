from decimal import Decimal

import pytest

from scripts.verify_postgres_restore import _json_loads, verify_restore


def test_verify_restore_compares_all_rows_and_sequences(monkeypatch):
    snapshot = {
        ("public", "invoices"): [{"id": 1}],
        ("public", "invoice_payments"): [{"id": 1, "amount": "50.00"}],
        ("public", "invoice_audit_events"): [{"id": 1}],
    }
    sequences = [{"sequencename": "invoices_id_seq", "last_value": 1}]
    monkeypatch.setattr(
        "scripts.verify_postgres_restore._snapshot",
        lambda database: (snapshot, sequences),
    )

    assert verify_restore("source", "restored") == (3, 3)


def test_verify_restore_rejects_different_table_data(monkeypatch):
    source = {
        ("public", "invoices"): [{"id": 1}],
        ("public", "invoice_payments"): [{"id": 1, "amount": "50.00"}],
        ("public", "invoice_audit_events"): [{"id": 1}],
    }
    restored = {**source, ("public", "invoice_payments"): [{"id": 1, "amount": "49.00"}]}
    monkeypatch.setattr(
        "scripts.verify_postgres_restore._snapshot",
        lambda database: (source if database == "source" else restored, []),
    )

    with pytest.raises(SystemExit, match="Restored table data differs"):
        verify_restore("source", "restored")


def test_verify_restore_rejects_different_sequence_state(monkeypatch):
    tables = {
        ("public", "invoices"): [{"id": 1}],
        ("public", "invoice_payments"): [{"id": 1}],
        ("public", "invoice_audit_events"): [{"id": 1}],
    }
    monkeypatch.setattr(
        "scripts.verify_postgres_restore._snapshot",
        lambda database: (
            tables,
            [{"sequencename": "invoices_id_seq", "last_value": 1 if database == "source" else 2}],
        ),
    )

    with pytest.raises(SystemExit, match="sequence definitions or values differ"):
        verify_restore("source", "restored")


def test_verify_restore_requires_browser_journey_data(monkeypatch):
    tables = {
        ("public", "invoices"): [{"id": 1}],
        ("public", "invoice_payments"): [],
        ("public", "invoice_audit_events"): [{"id": 1}],
    }
    monkeypatch.setattr(
        "scripts.verify_postgres_restore._snapshot",
        lambda database: (tables, []),
    )

    with pytest.raises(SystemExit, match="expected browser-journey data"):
        verify_restore("source", "restored")


def test_verify_restore_rejects_same_database():
    with pytest.raises(SystemExit, match="must be different"):
        verify_restore("same", "same")


def test_json_loads_preserves_exact_decimal_values():
    assert _json_loads('{"amount": 123456789012.34}') == {"amount": Decimal("123456789012.34")}
