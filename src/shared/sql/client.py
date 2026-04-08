"""PostgreSQL client with schema introspection and query execution.

Provides :class:`SQLClient` for connection pooling, schema discovery,
and safe query execution with Phoenix tracing.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from src.shared.sql.config import SQLSettings
from src.shared.tracing import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)


class SQLClient:
    """PostgreSQL client with pooling and schema introspection."""

    def __init__(self, settings: SQLSettings | None = None):
        """Initialize SQL client with connection pooling.

        Args:
            settings: SQL configuration dataclass. Uses defaults when *None*.
        """
        self.settings = settings or SQLSettings()
        self._engine = None
        self._session_maker = None

    @property
    def engine(self):
        """Lazy-initialized SQLAlchemy engine with connection pooling."""
        if self._engine is None:
            # SQLite doesn't support command_timeout, only psycopg does
            is_sqlite = self.settings.connection_string.startswith("sqlite://")

            if is_sqlite:
                # SQLite: minimal pool config
                self._engine = create_engine(
                    self.settings.connection_string,
                    echo=self.settings.echo,
                    connect_args={"check_same_thread": False} if is_sqlite else {},
                )
            else:
                # PostgreSQL: full pool config with psycopg options
                self._engine = create_engine(
                    self.settings.connection_string,
                    poolclass=QueuePool,
                    pool_size=self.settings.pool_size,
                    max_overflow=self.settings.max_overflow,
                    pool_timeout=self.settings.pool_timeout,
                    echo=self.settings.echo,
                    connect_args={
                        "command_timeout": self.settings.query_timeout,
                        "connect_timeout": 10,
                    },
                )
        return self._engine

    @property
    def session_maker(self):
        """Lazy-initialized session factory."""
        if self._session_maker is None:
            self._session_maker = sessionmaker(bind=self.engine)
        return self._session_maker

    def get_session(self):
        """Get a new database session."""
        return self.session_maker()

    def execute_query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a SELECT query and return results as JSON.

        Args:
            query: SQL query string
            params: Query parameters (bound as :param_name)

        Returns:
            {
                "success": bool,
                "rows": list[dict],
                "row_count": int,
                "error": str | None,
                "error_type": str | None,
                "execution_time_ms": float,
            }
        """
        with tracer.start_as_current_span("sql.execute_query") as span:
            import time

            start = time.time()
            session = None
            try:
                session = self.get_session()
                stmt = text(query)

                # Bind parameters if provided
                if params:
                    stmt = stmt.bindparams(**params)

                result = session.execute(stmt)
                rows = result.fetchall()
                columns = result.keys()

                # Convert rows to list of dicts
                data = [dict(zip(columns, row)) for row in rows]

                if hasattr(span, "set_attribute"):
                    span.set_attribute("rows_returned", len(data))

                return {
                    "success": True,
                    "rows": data,
                    "row_count": len(data),
                    "error": None,
                    "error_type": None,
                    "execution_time_ms": (time.time() - start) * 1000,
                }

            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e)

                logger.error(f"Query execution failed: {error_type}: {error_msg}")
                if hasattr(span, "set_attribute"):
                    span.set_attribute("error", True)
                    span.set_attribute("error_type", error_type)

                return {
                    "success": False,
                    "rows": [],
                    "row_count": 0,
                    "error": error_msg,
                    "error_type": error_type,
                    "execution_time_ms": (time.time() - start) * 1000,
                }

            finally:
                if session:
                    session.close()

    def execute_update(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an INSERT/UPDATE/DELETE query.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            {
                "success": bool,
                "rows_affected": int,
                "error": str | None,
                "error_type": str | None,
                "execution_time_ms": float,
            }
        """
        with tracer.start_as_current_span("sql.execute_update") as span:
            import time

            start = time.time()
            session = None
            try:
                session = self.get_session()
                stmt = text(query)

                if params:
                    stmt = stmt.bindparams(**params)

                result = session.execute(stmt)
                session.commit()

                rows_affected = result.rowcount

                if hasattr(span, "set_attribute"):
                    span.set_attribute("rows_affected", rows_affected)

                return {
                    "success": True,
                    "rows_affected": rows_affected,
                    "error": None,
                    "error_type": None,
                    "execution_time_ms": (time.time() - start) * 1000,
                }

            except Exception as e:
                if session:
                    session.rollback()

                error_type = type(e).__name__
                error_msg = str(e)

                logger.error(f"Update execution failed: {error_type}: {error_msg}")
                if hasattr(span, "set_attribute"):
                    span.set_attribute("error", True)
                    span.set_attribute("error_type", error_type)

                return {
                    "success": False,
                    "rows_affected": 0,
                    "error": error_msg,
                    "error_type": error_type,
                    "execution_time_ms": (time.time() - start) * 1000,
                }

            finally:
                if session:
                    session.close()

    def get_tables(self) -> list[str]:
        """Get list of table names in the configured schema.

        Returns:
            List of table names
        """
        with tracer.start_as_current_span("sql.get_tables"):
            try:
                inspector = inspect(self.engine)
                # SQLite doesn't support schemas, only PostgreSQL does
                schema = None if self.settings.connection_string.startswith("sqlite://") else self.settings.schema
                tables = inspector.get_table_names(schema=schema)
                return sorted(tables)
            except Exception as e:
                logger.error(f"Failed to get tables: {e}")
                return []

    def get_table_schema(self, table_name: str) -> dict[str, Any]:
        """Get DDL schema for a specific table.

        Returns:
            {
                "table_name": str,
                "columns": [{"name": str, "type": str, "nullable": bool, "primary_key": bool}],
                "primary_keys": list[str],
                "foreign_keys": list[{"column": str, "references": str}],
                "indexes": list[str],
            }
        """
        with tracer.start_as_current_span("sql.get_table_schema"):
            try:
                inspector = inspect(self.engine)
                # SQLite doesn't support schemas
                schema = None if self.settings.connection_string.startswith("sqlite://") else self.settings.schema

                columns = []
                for col in inspector.get_columns(table_name, schema=schema):
                    columns.append(
                        {
                            "name": col["name"],
                            "type": str(col["type"]),
                            "nullable": col["nullable"],
                            "primary_key": False,  # Will update below
                        }
                    )

                # Mark primary keys
                pk_constraint = inspector.get_pk_constraint(table_name, schema=schema)
                pk_cols = pk_constraint.get("constrained_columns", []) if pk_constraint else []
                for col in columns:
                    if col["name"] in pk_cols:
                        col["primary_key"] = True

                # Get foreign keys
                fks = []
                for fk in inspector.get_foreign_keys(table_name, schema=schema):
                    fks.append(
                        {
                            "column": fk["constrained_columns"][0],
                            "references": (
                                f"{fk['referred_table']}"
                                f"({fk['referred_columns'][0]})"
                            ),
                        }
                    )

                # Get indexes
                indexes = []
                for idx in inspector.get_indexes(table_name, schema=schema):
                    indexes.append(idx["name"])

                return {
                    "table_name": table_name,
                    "columns": columns,
                    "primary_keys": pk_cols,
                    "foreign_keys": fks,
                    "indexes": indexes,
                }

            except Exception as e:
                logger.error(f"Failed to get schema for {table_name}: {e}")
                return {
                    "table_name": table_name,
                    "columns": [],
                    "primary_keys": [],
                    "foreign_keys": [],
                    "indexes": [],
                }

    def get_full_catalog(self) -> dict[str, Any]:
        """Get complete database catalog (all tables + schemas + relationships).

        Returns:
            {
                "schema": str,
                "tables": list[str],
                "schemas": dict[table_name, schema_dict],
                "relationships": list[{"from": str, "to": str}],
            }
        """
        with tracer.start_as_current_span("sql.get_full_catalog"):
            tables = self.get_tables()

            schemas = {}
            for table in tables:
                schemas[table] = self.get_table_schema(table)

            # Build relationship map
            relationships = []
            for table, schema in schemas.items():
                for fk in schema["foreign_keys"]:
                    ref_table = fk["references"].split("(")[0]
                    relationships.append({"from": f"{table}.{fk['column']}", "to": ref_table})

            return {
                "schema": self.settings.schema,
                "tables": tables,
                "schemas": schemas,
                "relationships": relationships,
            }

    def get_table_statistics(self, table_name: str) -> dict[str, Any]:
        """Get row count and basic statistics for a table.

        Returns:
            {"table_name": str, "row_count": int, "estimated_size_mb": float}
        """
        with tracer.start_as_current_span("sql.get_table_statistics"):
            try:
                session = self.get_session()

                # Get row count
                count_query = f"SELECT COUNT(*) as cnt FROM {self.settings.schema}.{table_name}"
                result = session.execute(text(count_query))
                row_count = result.scalar() or 0

                # Get estimated size
                size_query = (
                    f"SELECT pg_total_relation_size('{self.settings.schema}.{table_name}')::bigint"
                )
                result = session.execute(text(size_query))
                size_bytes = result.scalar() or 0

                session.close()

                return {
                    "table_name": table_name,
                    "row_count": row_count,
                    "estimated_size_mb": size_bytes / (1024 * 1024),
                }

            except Exception as e:
                logger.error(f"Failed to get statistics for {table_name}: {e}")
                return {"table_name": table_name, "row_count": 0, "estimated_size_mb": 0}

    def health_check(self) -> bool:
        """Check database connectivity.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            session = self.get_session()
            result = session.execute(text("SELECT 1"))
            result.scalar()
            session.close()
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def close(self):
        """Close connection pool."""
        if self._engine:
            self._engine.dispose()
