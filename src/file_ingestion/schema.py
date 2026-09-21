from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


@dataclass(frozen=True)
class SchemaMapping:
    columns: dict[str, list[str]]
    required: list[str]

    @classmethod
    def from_json(cls, path: str | Path) -> SchemaMapping:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(columns=payload["columns"], required=payload["required"])

    def apply(self, frame: pd.DataFrame) -> pd.DataFrame:
        source_by_normalized = {normalize_header(column): column for column in frame.columns}
        selected: dict[str, pd.Series] = {}
        for canonical, aliases in self.columns.items():
            candidates = [canonical, *aliases]
            source = next(
                (
                    source_by_normalized[normalize_header(candidate)]
                    for candidate in candidates
                    if normalize_header(candidate) in source_by_normalized
                ),
                None,
            )
            selected[canonical] = (
                frame[source].astype("string") if source else pd.Series(pd.NA, index=frame.index)
            )
        missing = [name for name in self.required if selected[name].isna().all()]
        if missing:
            raise ValueError(f"required source columns were not mapped: {', '.join(missing)}")
        return pd.DataFrame(selected)

