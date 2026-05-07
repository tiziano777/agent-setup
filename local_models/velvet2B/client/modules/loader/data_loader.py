from __future__ import annotations

from pathlib import Path

import pandas as pd


_LOADERS: list[tuple[str, object]] = [
    ("*.parquet", lambda p: pd.read_parquet(p)),
    ("*.jsonl.gz", lambda p: pd.read_json(p, lines=True, compression="gzip")),
    ("*.jsonl", lambda p: pd.read_json(p, lines=True)),
]


class DataLoader:
    """Read all data files from a distribution directory into a list of dicts.

    Supported formats (auto-detected, checked in priority order):
    parquet > jsonl.gz > jsonl. All files in the directory must share the
    same format — mixed formats per directory are not supported.
    """

    @staticmethod
    def load(dist_uri: str) -> list[dict]:
        path = Path(dist_uri)
        for pattern, reader in _LOADERS:
            files = sorted(path.glob(pattern))
            if files:
                df = pd.concat([reader(f) for f in files], ignore_index=True)
                return df.to_dict("records")
        raise FileNotFoundError(
            f"No supported data files (parquet/jsonl.gz/jsonl) found in: {dist_uri}"
        )
