from __future__ import annotations

from pathlib import Path

from psycopg import Connection
from psycopg.rows import dict_row

from src.config import get_settings


def get_connection(namespace: str = "papers") -> Connection:
    settings = get_settings()
    return Connection.connect(
        settings.database_url,
        row_factory=dict_row,
        options=f"-c search_path={namespace},public",
    )


def has_documents(namespace: str) -> bool:
    """Return True if the namespace schema has at least one ingested document."""
    try:
        with get_connection(namespace) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM documents LIMIT 1")
                return cur.fetchone() is not None
    except Exception:
        return False


def init_schema(namespace: str = "papers", schema_path: Path | None = None) -> None:
    target_path = schema_path or Path(__file__).with_name("schema.sql")
    schema_sql = target_path.read_text(encoding="utf-8")

    settings = get_settings()
    # Create the schema first using a plain connection (no namespace routing yet).
    with Connection.connect(settings.database_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{namespace}"')
        conn.commit()

    # Create tables and indexes within the namespace.
    with get_connection(namespace) as conn:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
        conn.commit()
