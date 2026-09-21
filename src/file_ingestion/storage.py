from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class FileLedger:
    def __init__(self, database: str | Path) -> None:
        self.database = str(database)
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS file_ledger (
                    file_hash TEXT PRIMARY KEY,
                    source_file TEXT NOT NULL,
                    status TEXT NOT NULL,
                    accepted_rows INTEGER NOT NULL,
                    rejected_rows INTEGER NOT NULL,
                    processed_at_utc TEXT NOT NULL
                )
                """
            )

    def succeeded(self, file_hash: str) -> bool:
        with sqlite3.connect(self.database) as connection:
            row = connection.execute(
                "SELECT 1 FROM file_ledger WHERE file_hash = ? AND status = 'success'",
                (file_hash,),
            ).fetchone()
        return row is not None

    def record(
        self,
        *,
        file_hash: str,
        source_file: str,
        status: str,
        accepted_rows: int,
        rejected_rows: int,
    ) -> None:
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                """
                INSERT INTO file_ledger VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_hash) DO UPDATE SET
                    source_file = excluded.source_file,
                    status = excluded.status,
                    accepted_rows = excluded.accepted_rows,
                    rejected_rows = excluded.rejected_rows,
                    processed_at_utc = excluded.processed_at_utc
                """,
                (
                    file_hash,
                    source_file,
                    status,
                    accepted_rows,
                    rejected_rows,
                    datetime.now(UTC).isoformat(),
                ),
            )


class SqliteWarehouse:
    def __init__(self, database: str | Path) -> None:
        self.database = str(database)
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS policy_payments (
                    record_key TEXT PRIMARY KEY,
                    policy_id TEXT NOT NULL,
                    member_name TEXT,
                    payment_date TEXT NOT NULL,
                    payment_amount TEXT NOT NULL,
                    agent_id TEXT,
                    payment_detail TEXT,
                    carrier TEXT,
                    row_hash TEXT NOT NULL,
                    source_file TEXT NOT NULL,
                    source_file_hash TEXT NOT NULL,
                    loaded_at_utc TEXT NOT NULL
                )
                """
            )

    def upsert(self, frame: pd.DataFrame, *, source_file: str, source_hash: str) -> int:
        now = datetime.now(UTC).isoformat()
        rows = [
            (
                row.record_key,
                row.policy_id,
                row.member_name,
                row.payment_date,
                str(row.payment_amount),
                row.agent_id,
                row.payment_detail,
                row.carrier,
                row.row_hash,
                source_file,
                source_hash,
                now,
            )
            for row in frame.itertuples(index=False)
        ]
        with sqlite3.connect(self.database) as connection:
            connection.executemany(
                """
                INSERT INTO policy_payments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(record_key) DO UPDATE SET
                    member_name = excluded.member_name,
                    payment_amount = excluded.payment_amount,
                    agent_id = excluded.agent_id,
                    carrier = excluded.carrier,
                    row_hash = excluded.row_hash,
                    source_file = excluded.source_file,
                    source_file_hash = excluded.source_file_hash,
                    loaded_at_utc = excluded.loaded_at_utc
                """,
                rows,
            )
        return len(rows)

    def row_count(self) -> int:
        with sqlite3.connect(self.database) as connection:
            return int(connection.execute("SELECT COUNT(*) FROM policy_payments").fetchone()[0])

