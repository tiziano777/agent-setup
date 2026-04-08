"""Pytest configuration and fixtures for text2sql_agent tests.

Provides PostgreSQL-based test database fixtures with automatic schema creation,
data population, and cleanup.

Tables:
- customers: id, name, email, created_at
- products: id, name, price, category
- orders: id, customer_id, order_date, total_amount
- order_items: id, order_id, product_id, quantity, unit_price

Foreign keys:
- orders.customer_id -> customers.id
- order_items.order_id -> orders.id
"""

import logging
import os
import uuid
import pytest
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

# PostgreSQL connection parameters (read from env, with test defaults)
TEST_DB_HOST = os.getenv("SQL_HOST", "localhost")
TEST_DB_PORT = int(os.getenv("SQL_PORT", "5432"))
TEST_DB_USER = os.getenv("SQL_USERNAME", "postgres")
TEST_DB_PASSWORD = os.getenv("SQL_PASSWORD", "postgres")
TEST_DB_NAME = os.getenv("SQL_DATABASE", "agent_db")
TEST_DB_SCHEMA_PREFIX = "test_schema_"


def get_test_schema_name():
    """Generate unique test schema name to avoid conflicts."""
    return f"{TEST_DB_SCHEMA_PREFIX}{str(uuid.uuid4())[:8]}"


def get_postgres_connection_string(db_name: str = "postgres", schema: str | None = None) -> str:
    """Build PostgreSQL connection string."""
    conn_str = f"postgresql+psycopg://{TEST_DB_USER}:{TEST_DB_PASSWORD}@{TEST_DB_HOST}:{TEST_DB_PORT}/{db_name}"
    return conn_str


@pytest.fixture(scope="function")
def test_db_schema():
    """Create isolated PostgreSQL test schema with tables and dummy data.

    Yields:
        dict with schema_name, connection_string, and engine

    Cleanup:
        Drops test schema and all contained objects on test completion.
    """
    schema_name = get_test_schema_name()
    logger.info(f"Setting up test schema: {schema_name}")

    # Connect to main DB to create schema
    engine = None
    try:
        main_conn_str = get_postgres_connection_string(db_name=TEST_DB_NAME)
        engine = create_engine(main_conn_str)

        with engine.connect() as conn:
            # Create schema
            conn.execute(text(f"CREATE SCHEMA {schema_name}"))
            conn.commit()
            logger.debug(f"Created schema {schema_name}")

            # Create tables
            conn.execute(text(f"""
                CREATE TABLE {schema_name}.customers (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))

            conn.execute(text(f"""
                CREATE TABLE {schema_name}.products (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    price DECIMAL(10, 2),
                    category VARCHAR(100)
                )
            """))

            conn.execute(text(f"""
                CREATE TABLE {schema_name}.orders (
                    id SERIAL PRIMARY KEY,
                    customer_id INTEGER NOT NULL REFERENCES {schema_name}.customers(id),
                    order_date DATE,
                    total_amount DECIMAL(10, 2)
                )
            """))

            conn.execute(text(f"""
                CREATE TABLE {schema_name}.order_items (
                    id SERIAL PRIMARY KEY,
                    order_id INTEGER NOT NULL REFERENCES {schema_name}.orders(id),
                    product_id INTEGER NOT NULL,
                    quantity INTEGER,
                    unit_price DECIMAL(10, 2)
                )
            """))

            logger.debug(f"Created tables in {schema_name}")

            # Populate test data
            conn.execute(text(f"""
                INSERT INTO {schema_name}.customers (id, name, email) VALUES
                (1, 'Alice Johnson', 'alice@example.com'),
                (2, 'Bob Smith', 'bob@example.com'),
                (3, 'Charlie Brown', 'charlie@example.com')
            """))

            conn.execute(text(f"""
                INSERT INTO {schema_name}.products (id, name, price, category) VALUES
                (1, 'Laptop', 1200.00, 'Electronics'),
                (2, 'Mouse', 25.00, 'Electronics'),
                (3, 'Desk', 300.00, 'Furniture'),
                (4, 'Chair', 150.00, 'Furniture')
            """))

            conn.execute(text(f"""
                INSERT INTO {schema_name}.orders (id, customer_id, order_date, total_amount) VALUES
                (1, 1, '2024-01-15', 1225.00),
                (2, 1, '2024-02-10', 450.00),
                (3, 2, '2024-03-05', 25.00),
                (4, 3, '2024-03-15', 1200.00)
            """))

            conn.execute(text(f"""
                INSERT INTO {schema_name}.order_items (id, order_id, product_id, quantity, unit_price) VALUES
                (1, 1, 1, 1, 1200.00),
                (2, 1, 2, 1, 25.00),
                (3, 2, 3, 1, 300.00),
                (4, 2, 4, 1, 150.00),
                (5, 3, 2, 1, 25.00),
                (6, 4, 1, 1, 1200.00)
            """))

            conn.commit()
            logger.debug(f"Populated test data for {schema_name}")

        # Now set search_path for this schema in a temporary settings class
        # This allows SQLSettings() to automatically use our test schema
        import src.shared.sql.config as sql_config

        original_settings_class = sql_config.SQLSettings

        class TestSQLSettings:
            """Override SQLSettings for tests to use test schema."""

            def __init__(self):
                self.host = TEST_DB_HOST
                self.port = TEST_DB_PORT
                self.database = TEST_DB_NAME
                self.username = TEST_DB_USER
                self.password = TEST_DB_PASSWORD
                self.pool_size = 1
                self.max_overflow = 1
                self.pool_timeout = 5
                self.query_timeout = 30
                self.schema = schema_name  # ← Use test schema!
                self.echo = False

            @property
            def connection_string(self) -> str:
                return f"postgresql+psycopg://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"

        # Replace for duration of test
        sql_config.SQLSettings = TestSQLSettings

        logger.info(f"Test schema {schema_name} ready")

        yield {
            "schema_name": schema_name,
            "connection_string": main_conn_str,
            "engine": engine,
        }

        # Cleanup: restore original class
        sql_config.SQLSettings = original_settings_class

        logger.info(f"Cleaning up test schema: {schema_name}")

    except OperationalError as e:
        logger.error(
            f"PostgreSQL connection failed: {e}. "
            f"Ensure PostgreSQL is running: make build"
        )
        pytest.skip(f"PostgreSQL not available: {e}")

    finally:
        # Drop schema
        if engine:
            try:
                with engine.connect() as conn:
                    # Terminate any remaining connections to this schema
                    conn.execute(text(f"""
                        SELECT pg_terminate_backend(pg_stat_activity.pid)
                        FROM pg_stat_activity
                        WHERE pg_stat_activity.datname = '{TEST_DB_NAME}'
                          AND pid <> pg_backend_pid()
                    """))

                    # Drop schema and all objects
                    conn.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))
                    conn.commit()
                    logger.debug(f"Dropped schema {schema_name}")
            except Exception as e:
                logger.warning(f"Failed to drop schema {schema_name}: {e}")
            finally:
                engine.dispose()


@pytest.fixture(scope="function", autouse=True)
def reset_sql_settings():
    """Auto-reset SQLSettings between tests to avoid state leakage."""
    yield
    # After test, reload the module to get clean settings
    import importlib
    import src.shared.sql.config
    importlib.reload(src.shared.sql.config)
