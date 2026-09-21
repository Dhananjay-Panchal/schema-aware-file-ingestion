"""Schema-aware file ingestion reference implementation."""

from .pipeline import FileIngestionPipeline, FileRunStats
from .schema import SchemaMapping
from .storage import FileLedger, SqliteWarehouse

__all__ = ["FileIngestionPipeline", "FileLedger", "FileRunStats", "SchemaMapping", "SqliteWarehouse"]

