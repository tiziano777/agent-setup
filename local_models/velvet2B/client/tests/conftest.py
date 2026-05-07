"""Pytest fixtures and session hooks for the pipeline test suite.

All importable helpers (MockClientSession, sample builders, etc.) live in
helpers.py to avoid the 'conftest is not a module' import error.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import sys

import pytest

# Make tests/ importable so `from helpers import ...` works in both
# conftest.py (loaded as a pytest plugin) and test_pipeline.py.
_TESTS_DIR = Path(__file__).parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

from helpers import (
    REPORTS_DIR,
    RESULTS_DIR,
    _id_hash,
    _make_sample,
    CHAT_TYPE_MAPPING,
)


# ════════════════════════════════════════════════════════════════════════════
# StepLogger
# ════════════════════════════════════════════════════════════════════════════

class StepLogger:
    """Records every step of a test (input, output, errors) and dumps to JSON."""

    def __init__(self, test_name: str) -> None:
        self.test_name  = test_name
        self.steps: list[dict] = []
        self._t0        = time.monotonic()
        self._passed: bool | None = None

    def log(
        self,
        step: str,
        *,
        input: Any = None,
        output: Any = None,
        error: str | None = None,
        note: str | None = None,
    ) -> None:
        entry: dict = {"step": step, "elapsed_s": round(time.monotonic() - self._t0, 4)}
        if input  is not None: entry["input"]  = input
        if output is not None: entry["output"] = output
        if error  is not None: entry["error"]  = error
        if note   is not None: entry["note"]   = note
        self.steps.append(entry)

    def mark_passed(self) -> None: self._passed = True
    def mark_failed(self) -> None: self._passed = False

    def dump(self) -> Path:
        report = {
            "test":       self.test_name,
            "passed":     self._passed,
            "duration_s": round(time.monotonic() - self._t0, 4),
            "steps":      self.steps,
        }
        out = REPORTS_DIR / f"{self.test_name}.json"
        out.write_text(json.dumps(report, indent=2, default=str))
        return out


# ════════════════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def step_logger(request: pytest.FixtureRequest) -> StepLogger:
    lg = StepLogger(request.node.name)
    yield lg
    lg.dump()


# ── sample fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def sample_single_turn() -> dict:
    return _make_sample("st_001", "Qual è la capitale d'Italia?")


@pytest.fixture
def sample_multi_turn() -> dict:
    return _make_sample(
        "mt_001",
        "E la capitale della Germania?",
        completed_turn="Roma è la capitale d'Italia.",
    )


@pytest.fixture
def sample_batch() -> list[dict]:
    return [
        _make_sample("geo_001", "Qual è la capitale della Francia?"),
        _make_sample("math_001", "Quanto fa 17 × 6?"),
        _make_sample("code_001", "Come si scrive un for loop in Python?"),
    ]


@pytest.fixture
def system_prompts() -> tuple[list[str], list[str]]:
    return (
        ["Sei un assistente utile.", "Rispondi in modo molto conciso."],
        ["sys_v1",                   "sys_v2"],
    )


# ── registry ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def chat_registry():
    from modules.templates.chat_type_registry import ChatTypeRegistry
    return ChatTypeRegistry(CHAT_TYPE_MAPPING)


# ── RecipeEntry factory ───────────────────────────────────────────────────────

@pytest.fixture
def recipe_entry_factory(tmp_path):
    from modules.recipe.recipe_config import RecipeEntry
    import json as _json

    counter = [0]

    def _make(
        samples: list[dict],
        *,
        replica: int = 1,
        system_prompts: list[str] | None = None,
        system_prompt_names: list[str] | None = None,
        dist_name: str | None = None,
    ) -> tuple["RecipeEntry", Path]:
        counter[0] += 1
        name     = dist_name or f"test_dist_{counter[0]:02d}"
        dist_dir = tmp_path / "datasets" / name
        dist_dir.mkdir(parents=True, exist_ok=True)
        jsonl = dist_dir / "data.jsonl"
        with open(jsonl, "w") as fh:
            for r in samples:
                fh.write(_json.dumps(r) + "\n")

        entry = RecipeEntry(
            chat_type="train_dpo",
            dist_id=_id_hash(name),
            dist_name=name,
            dist_uri=str(dist_dir),
            replica=replica,
            samples=len(samples),
            system_prompt=system_prompts,
            system_prompt_name=system_prompt_names,
            tokens=999,
            words=999,
            validation_error=None,
        )
        return entry, dist_dir

    return _make


# ── module-level patches applied to every test ───────────────────────────────

@pytest.fixture(autouse=True)
def _force_completions_api(monkeypatch):
    """Force USE_CHAT_COMPLETIONS_API=True for every test in the suite."""
    import async_client
    monkeypatch.setattr(async_client, "USE_CHAT_COMPLETIONS_API", True)


@pytest.fixture(autouse=True)
def _slim_temperatures(monkeypatch):
    """Use only 2 temperatures to keep task counts small during tests."""
    import async_client
    monkeypatch.setattr(async_client, "TEMPERATURE_RANGE", [0.0, 0.7])


# ════════════════════════════════════════════════════════════════════════════
# Session-level summary
# ════════════════════════════════════════════════════════════════════════════

_SESSION_RESULTS: list[dict] = []


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    if call.when == "call":
        rep = outcome.get_result()
        _SESSION_RESULTS.append({
            "test":   item.nodeid,
            "passed": rep.passed,
            "failed": rep.failed,
        })


def pytest_sessionfinish(session, exitstatus):
    summary = {
        "total":   len(_SESSION_RESULTS),
        "passed":  sum(1 for r in _SESSION_RESULTS if r["passed"]),
        "failed":  sum(1 for r in _SESSION_RESULTS if r["failed"]),
        "results": _SESSION_RESULTS,
    }
    (RESULTS_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
