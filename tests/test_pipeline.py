from __future__ import annotations

import json

import pandas as pd

from file_ingestion.pipeline import FileIngestionPipeline
from file_ingestion.schema import SchemaMapping
from file_ingestion.storage import FileLedger, SqliteWarehouse
from file_ingestion.transform import clean_money


def build_mapping(path) -> SchemaMapping:
    payload = {
        "columns": {
            "policy_id": ["policy number"],
            "member_name": ["member name"],
            "payment_date": ["paid date"],
            "payment_amount": ["commission"],
            "agent_id": ["writing agent"],
            "payment_detail": ["transaction type"],
            "carrier": ["carrier"],
        },
        "required": ["policy_id", "payment_date", "payment_amount"],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return SchemaMapping.from_json(path)


def test_pipeline_validates_deduplicates_and_skips_processed_file(tmp_path) -> None:
    source = tmp_path / "commissions.csv"
    pd.DataFrame(
        [
            ["0001", "Avery", "2026-01-01", "$10.00", "A1", "Initial", "Demo"],
            ["0002", "Jordan", "2026-01-02", "$20.00", "A2", "Renewal", "Demo"],
            ["0002", "Jordan", "2026-01-02", "$22.00", "A2", "Renewal", "Demo"],
            ["", "Taylor", "2026-01-03", "$30.00", "A3", "Initial", "Demo"],
            ["0004", "Casey", "bad-date", "$40.00", "A4", "Initial", "Demo"],
        ],
        columns=[
            "Policy Number",
            "Member Name",
            "Paid Date",
            "Commission",
            "Writing Agent",
            "Transaction Type",
            "Carrier",
        ],
    ).to_csv(source, index=False)

    database = tmp_path / "ingestion.db"
    warehouse = SqliteWarehouse(database)
    pipeline = FileIngestionPipeline(
        build_mapping(tmp_path / "mapping.json"),
        FileLedger(database),
        warehouse,
        quarantine_dir=tmp_path / "quarantine",
    )

    first = pipeline.run(source)
    second = pipeline.run(source)

    assert first.source_rows == 5
    assert first.accepted_rows == 2
    assert first.rejected_rows == 2
    assert first.deduplicated_rows == 1
    assert warehouse.row_count() == 2
    assert second.skipped is True
    assert (tmp_path / "quarantine" / "commissions_rejected.csv").exists()


def test_parenthesized_money_is_negative() -> None:
    assert str(clean_money("($25.10)")) == "-25.10"

