from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .pipeline import FileIngestionPipeline
from .schema import SchemaMapping
from .storage import FileLedger, SqliteWarehouse


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a schema-mapped CSV or Excel file")
    parser.add_argument("source")
    parser.add_argument("--mapping", default="config/carrier_example.json")
    parser.add_argument("--database", default="ingestion.db")
    parser.add_argument("--sheet")
    parser.add_argument("--quarantine-dir", default="output/quarantine")
    args = parser.parse_args()

    pipeline = FileIngestionPipeline(
        SchemaMapping.from_json(args.mapping),
        FileLedger(args.database),
        SqliteWarehouse(args.database),
        quarantine_dir=args.quarantine_dir,
    )
    stats = pipeline.run(args.source, sheet_name=args.sheet)
    print(json.dumps(asdict(stats), indent=2))


if __name__ == "__main__":
    main()

