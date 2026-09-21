from __future__ import annotations

import hashlib
import re
from decimal import Decimal, InvalidOperation

import pandas as pd


def clean_identifier(value: object) -> str | None:
    if pd.isna(value):
        return None
    cleaned = str(value).strip()
    return cleaned or None


def clean_money(value: object) -> Decimal | None:
    if pd.isna(value):
        return None
    raw = str(value).strip()
    negative = raw.startswith("(") and raw.endswith(")")
    normalized = re.sub(r"[^0-9.\-]", "", raw)
    if not normalized:
        return None
    try:
        amount = Decimal(normalized)
    except InvalidOperation:
        return None
    return -abs(amount) if negative else amount


def clean_date(value: object) -> str | None:
    if pd.isna(value) or not str(value).strip():
        return None
    parsed = pd.to_datetime(str(value).strip(), errors="coerce")
    return None if pd.isna(parsed) else parsed.date().isoformat()


def record_key(row: pd.Series) -> str:
    parts = [
        str(row["policy_id"]),
        str(row["payment_date"]),
        "" if pd.isna(row.get("payment_detail")) else str(row.get("payment_detail")),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def row_hash(row: pd.Series) -> str:
    values = [
        row.get("policy_id"),
        row.get("member_name"),
        row.get("payment_date"),
        row.get("payment_amount"),
        row.get("agent_id"),
        row.get("payment_detail"),
        row.get("carrier"),
    ]
    return hashlib.sha256(
        "|".join("" if value is None or pd.isna(value) else str(value) for value in values).encode()
    ).hexdigest()


def transform(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    result = frame.copy()
    result["source_row"] = result.index + 2
    result["policy_id"] = result["policy_id"].map(clean_identifier)
    result["agent_id"] = result["agent_id"].map(clean_identifier)
    result["member_name"] = result["member_name"].map(clean_identifier)
    result["payment_detail"] = result["payment_detail"].map(clean_identifier)
    result["carrier"] = result["carrier"].map(clean_identifier)
    result["payment_date"] = result["payment_date"].map(clean_date)
    result["payment_amount"] = result["payment_amount"].map(clean_money)

    reasons = []
    for _, row in result.iterrows():
        row_reasons = []
        if clean_identifier(row["policy_id"]) is None:
            row_reasons.append("missing policy_id")
        if clean_date(row["payment_date"]) is None:
            row_reasons.append("invalid payment_date")
        if row["payment_amount"] is None or pd.isna(row["payment_amount"]):
            row_reasons.append("invalid payment_amount")
        reasons.append("; ".join(row_reasons))
    result["rejection_reason"] = reasons

    rejected = result[result["rejection_reason"] != ""].copy()
    accepted = result[result["rejection_reason"] == ""].copy()
    accepted["record_key"] = accepted.apply(record_key, axis=1)
    before_dedupe = len(accepted)
    accepted = accepted.drop_duplicates(subset=["record_key"], keep="last")
    deduplicated = before_dedupe - len(accepted)
    accepted["row_hash"] = accepted.apply(row_hash, axis=1)
    accepted = accepted.drop(columns=["rejection_reason"])
    return accepted, rejected, deduplicated
