"""Verify that a PostgreSQL restore reproduces all application data and sequence state."""

from __future__ import annotations

import argparse
import json
import subprocess
from decimal import Decimal
from typing import Any

REQUIRED_DATA_TABLES = ("invoices", "invoice_payments", "invoice_audit_events")


def _query(database: str, statement: str) -> str:
    try:
        result = subprocess.run(
            [
                "psql",
                "--no-psqlrc",
                "--set=ON_ERROR_STOP=1",
                "--tuples-only",
                "--no-align",
                "--host",
                "localhost",
                "--username",
                "afm",
                "--dbname",
                database,
                "--command",
                statement,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        details = (error.stderr or "").strip() or f"exit code {error.returncode}"
        raise RuntimeError(f"psql query failed for {database}: {details}") from error
    return result.stdout.strip()


def _json_loads(value: str) -> Any:
    return json.loads(value, parse_float=Decimal)


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _tables(database: str) -> list[dict[str, str]]:
    statement = """
        SELECT COALESCE(
            jsonb_agg(
                jsonb_build_object('schema', table_schema, 'name', table_name)
                ORDER BY table_schema, table_name
            ),
            '[]'::jsonb
        )::text
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE'
          AND table_schema <> ALL (ARRAY['information_schema', 'pg_catalog'])
          AND table_schema NOT LIKE 'pg_temp_%'
          AND table_schema NOT LIKE 'pg_toast%'
    """
    return _json_loads(_query(database, statement))


def _table_rows(database: str, schema: str, table: str) -> list[dict[str, Any]]:
    relation = f"{_quote_identifier(schema)}.{_quote_identifier(table)}"
    statement = (
        "SELECT COALESCE(jsonb_agg(to_jsonb(row_data)), '[]'::jsonb)::text "
        f"FROM {relation} AS row_data"
    )
    rows = _json_loads(_query(database, statement))
    return sorted(
        rows,
        key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":"), default=str),
    )


def _sequences(database: str) -> list[dict[str, Any]]:
    statement = """
        SELECT COALESCE(
            jsonb_agg(to_jsonb(sequence_data) ORDER BY schemaname, sequencename),
            '[]'::jsonb
        )::text
        FROM pg_catalog.pg_sequences AS sequence_data
        WHERE schemaname <> ALL (ARRAY['information_schema', 'pg_catalog'])
          AND schemaname NOT LIKE 'pg_temp_%'
          AND schemaname NOT LIKE 'pg_toast%'
    """
    return _json_loads(_query(database, statement))


def _snapshot(
    database: str,
) -> tuple[dict[tuple[str, str], list[dict[str, Any]]], list[dict[str, Any]]]:
    tables = _tables(database)
    rows_by_table = {
        (table["schema"], table["name"]): _table_rows(database, table["schema"], table["name"])
        for table in tables
    }
    sequences = _sequences(database)
    return rows_by_table, sequences


def verify_restore(source: str, restored: str) -> tuple[int, int]:
    if source == restored:
        raise SystemExit("Source and restored database names must be different")

    source_tables, source_sequences = _snapshot(source)
    restored_tables, restored_sequences = _snapshot(restored)

    if source_tables.keys() != restored_tables.keys():
        missing = sorted(source_tables.keys() - restored_tables.keys())
        unexpected = sorted(restored_tables.keys() - source_tables.keys())
        raise SystemExit(
            f"Restored schema differs; missing tables: {missing}; unexpected tables: {unexpected}"
        )

    mismatched_tables = [key for key in source_tables if source_tables[key] != restored_tables[key]]
    if mismatched_tables:
        raise SystemExit(f"Restored table data differs for: {sorted(mismatched_tables)}")

    if source_sequences != restored_sequences:
        raise SystemExit("Restored PostgreSQL sequence definitions or values differ from source")

    missing_required = sorted(
        name for name in REQUIRED_DATA_TABLES if ("public", name) not in source_tables
    )
    empty_required = sorted(
        name
        for name in REQUIRED_DATA_TABLES
        if ("public", name) in source_tables and not source_tables[("public", name)]
    )
    if missing_required or empty_required:
        raise SystemExit(
            "Source database does not contain the expected browser-journey data; "
            f"missing tables: {missing_required}; empty tables: {empty_required}"
        )

    row_count = sum(len(rows) for rows in source_tables.values())
    return len(source_tables), row_count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Database name containing the journey data")
    parser.add_argument("--restored", required=True, help="Database name restored from the dump")
    args = parser.parse_args()

    table_count, row_count = verify_restore(args.source, args.restored)
    print(
        f"Restore verified: all {row_count} rows across {table_count} tables "
        "and PostgreSQL sequence states match."
    )


if __name__ == "__main__":
    main()
