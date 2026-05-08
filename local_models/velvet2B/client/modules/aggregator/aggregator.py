from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)


class DuckDBAggregator:
    """Aggregate BASE-schema JSONL records into the FINAL schema using DuckDB.

    Given N*K records (N samples × K inference variants), groups by `_id_hash`
    and collapses the mode key (positive/negative/candidate) into an array,
    producing N aggregated records written as rolling Parquet files.

    Args:
        mode: One of "positive", "negative", "candidate". The plural form
              (e.g. "positives") becomes the array key in the FINAL schema.
        max_mb: Rolling file size threshold in megabytes.
    """

    def __init__(self, mode: str, max_mb: int = 100):
        self.mode = mode
        self.plural = mode + "s"
        self.max_bytes = max_mb * 1024 * 1024

    def aggregate_and_write(self, jsonl_files: list[Path], output_dir: Path) -> list[Path]:
        """Read JSONL files, group by _id_hash, write rolling Parquet files.

        Returns:
            List of written Parquet file paths.
        """
        existing = [str(f) for f in jsonl_files if f.exists()]
        if not existing:
            logger.warning("No JSONL files to aggregate in %s", output_dir)
            return []

        output_dir.mkdir(parents=True, exist_ok=True)
        con = duckdb.connect()

        files_expr = "[" + ", ".join(f"'{f}'" for f in existing) + "]"
        con.execute(f"CREATE TABLE raw AS SELECT * FROM read_json_auto({files_expr})")

        # Stream results via cursor to avoid pulling the full table into memory
        # Try to include optional _distribution_id and _distribution_uri if they exist
        # Otherwise fallback to NULL values
        try:
            # First, check if the columns exist by querying the schema
            schema_result = con.execute("DESCRIBE raw").fetchall()
            columns = {row[0] for row in schema_result}
            has_dist_id = "_distribution_id" in columns
            has_dist_uri = "_distribution_uri" in columns
        except Exception:
            has_dist_id = False
            has_dist_uri = False

        # Build the SELECT list dynamically
        dist_id_expr = "FIRST(_distribution_id)" if has_dist_id else "NULL"
        dist_uri_expr = "FIRST(_distribution_uri)" if has_dist_uri else "NULL"

        cursor = con.execute(f"""
            SELECT
                _id_hash,
                _distribution_name,
                {dist_id_expr} AS _distribution_id,
                {dist_uri_expr} AS _distribution_uri,
                list({self.mode}) AS {self.plural}
            FROM raw
            GROUP BY _id_hash, _distribution_name
        """)

        written: list[Path] = []
        part = 1
        batch_rows: list[dict] = []

        def _flush(rows: list[dict], part_num: int) -> Path:
            out = output_dir / f"aggregated_part{part_num}.parquet"
            table = pa.Table.from_pylist(rows)
            pq.write_table(table, out, compression="snappy")
            logger.info("Wrote %s (%d rows)", out.name, len(rows))
            return out

        columns = [desc[0] for desc in cursor.description]

        for row in cursor.fetchall():
            batch_rows.append(dict(zip(columns, row)))

            # Estimate current batch size and flush when threshold is exceeded.
            # We flush eagerly: once the batch would likely exceed max_bytes we
            # write and start fresh. A rough heuristic of ~512 bytes per row is
            # used to avoid building a full Arrow table just for a size check.
            if len(batch_rows) * 512 >= self.max_bytes:
                written.append(_flush(batch_rows, part))
                part += 1
                batch_rows = []

        if batch_rows:
            written.append(_flush(batch_rows, part))

        con.close()
        return written
