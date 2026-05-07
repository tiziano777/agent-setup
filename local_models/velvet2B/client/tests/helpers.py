"""Shared constants, mock objects, and sample-building utilities
for the pipeline test suite.

These are plain Python objects (no pytest fixtures) and can be imported
normally by both conftest.py and test_pipeline.py.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

# ── importable root ──────────────────────────────────────────────────────────
_CLIENT_ROOT = Path(__file__).parent.parent
if str(_CLIENT_ROOT) not in sys.path:
    sys.path.insert(0, str(_CLIENT_ROOT))

# ── persistent results dirs ──────────────────────────────────────────────────
LOGS_DIR    = Path(__file__).parent / "logs"
RESULTS_DIR = LOGS_DIR / "results"
INTER_DIR   = RESULTS_DIR / "intermediate"   # raw JSONL written by full-pipeline tests
AGG_DIR     = RESULTS_DIR / "aggregated"     # Parquet written by full-pipeline tests
REPORTS_DIR = RESULTS_DIR / "reports"        # per-test JSON step logs

for _d in (INTER_DIR, AGG_DIR, REPORTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ── real registry path ────────────────────────────────────────────────────────
CHAT_TYPE_MAPPING = str(
    _CLIENT_ROOT / "modules/templates/dpo/chat_type_mapping.yml"
)


# ── sample-building helpers ──────────────────────────────────────────────────

def _id_hash(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _make_sample(seed: str, question: str, *, completed_turn: str | None = None) -> dict:
    """Build a minimal DPO-format sample for the train_dpo template."""
    messages: list[dict] = []
    if completed_turn:
        messages += [
            {"role": "USER",      "content": "Ciao!"},
            {"role": "ASSISTANT", "content": completed_turn},
        ]
    messages += [
        {"role": "USER",      "content": question},
        {"role": "ASSISTANT"},          # generation target — no content
    ]
    return {"_id_hash": _id_hash(seed), "messages": messages}


def write_jsonl(path: Path, records: list[dict]) -> None:
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for r in records:
            f.write(__import__("json").dumps(r) + "\n")


# ── mock aiohttp session ──────────────────────────────────────────────────────

class _MockResp:
    """Minimal stand-in for aiohttp.ClientResponse (async context manager)."""

    def __init__(self, data: dict, status: int = 200) -> None:
        self._data  = data
        self.status = status

    async def json(self) -> dict:
        return self._data

    async def __aenter__(self):  return self
    async def __aexit__(self, *_): pass


class MockClientSession:
    """Drop-in for aiohttp.ClientSession returning canned OpenAI-format responses.

    Args:
        responses: Single dict or list. The i-th POST uses responses[i % len(responses)].
        statuses:  Parallel HTTP status list (default all 200).
    """

    def __init__(
        self,
        responses: dict | list[dict],
        statuses: list[int] | None = None,
    ) -> None:
        self._resps    = responses if isinstance(responses, list) else [responses]
        self._statuses = statuses or [200] * len(self._resps)
        self._call_idx = 0
        self.recorded_payloads: list[dict] = []

    def post(self, url: str, *, json: dict | None = None, **_) -> _MockResp:
        self.recorded_payloads.append({"url": url, "payload": json or {}})
        i      = self._call_idx % len(self._resps)
        status = self._statuses[i % len(self._statuses)]
        resp   = _MockResp(self._resps[i], status)
        self._call_idx += 1
        return resp

    async def __aenter__(self):  return self
    async def __aexit__(self, *_): pass


def openai_response(content: str) -> dict:
    """Minimal OpenAI-style /v1/chat/completions response."""
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}
