from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .schema import SchemaMapping
from .storage import FileLedger, SqliteWarehouse, sha256_file
from .transform import transform


@dataclass(frozen=True)
class FileRunStats:
    source_rows: int
    accepted_rows: int
    rejected_rows: int
    deduplicated_rows: int
    skipped: bool = False


class FileIngestionPipeline:
    def __init__(
        self,
        mapping: SchemaMapping,
        ledger: FileLedger,
        warehouse: SqliteWarehouse,
        *,
        quarantine_dir: str | Path,
    ) -> None:
        self.mapping = mapping
        self.ledger = ledger
        self.warehouse = warehouse
        self.quarantine_dir = Path(quarantine_dir)

    def run(self, source_path: str | Path, *, sheet_name: str | None = None) -> FileRunStats:
        source_path = Path(source_path)
        file_hash = sha256_file(source_path)
        if self.ledger.succeeded(file_hash):
            return FileRunStats(0, 0, 0, 0, skipped=True)

        source = self._read(source_path, sheet_name=sheet_name)
        mapped = self.mapping.apply(source)
        accepted, rejected, deduplicated = transform(mapped)

        if not rejected.empty:
            self.quarantine_dir.mkdir(parents=True, exist_ok=True)
            rejected.to_csv(
                self.quarantine_dir / f"{source_path.stem}_rejected.csv",
                index=False,
            )

        self.warehouse.upsert(
            accepted,
            source_file=source_path.name,
            source_hash=file_hash,
        )
        self.ledger.record(
            file_hash=file_hash,
            source_file=source_path.name,
            status="success",
            accepted_rows=len(accepted),
            rejected_rows=len(rejected),
        )
        return FileRunStats(
            source_rows=len(source),
            accepted_rows=len(accepted),
            rejected_rows=len(rejected),
            deduplicated_rows=deduplicated,
        )

    @staticmethod
    def _read(path: Path, *, sheet_name: str | None) -> pd.DataFrame:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(path, dtype="string", keep_default_na=False)
        if suffix in {".xlsx", ".xlsm"}:
            return pd.read_excel(
                path,
                sheet_name=sheet_name or 0,
                dtype="string",
                keep_default_na=False,
            )
        raise ValueError(f"unsupported file type: {suffix}")

