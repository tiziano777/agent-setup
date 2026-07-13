"""Hard Negative Filter — NLP-based selection of optimal rejected candidates for DPO.

3-phase pipeline:
  1. Detect and quarantine degenerate candidates (loops/hallucinations/truncation).
     If ALL candidates are degenerate, the sample is appended to hallucinations.jsonl
     and None is returned regardless of fallback strategy.
  2. Filter false negatives (ROUGE-L too close to gold, i.e., near-duplicates).
  3. Multi-attribute scoring → select best hard negative.

Fallback strategies when no candidate survives phases 1-2:
  - "drop": return None (sample skipped)
  - "temperature": delegate to temperature-based selection

Recommended usage — two-pass workflow
--------------------------------------
  1. Call compute_stats(uri) once on the full dataset to derive calibrated
     thresholds from the real corpus distributions (entropy, TTR, ROUGE-L).
     This returns a HardNegativeConfig pre-populated with data-driven values.

  2. Instantiate HardNegativeFilter(config) and call select() once per sample.

This separates global calibration (corpus-level statistics) from local selection
(per-sample K-candidate pool), giving both statistically stable thresholds and
fast per-sample inference.

Design principles:
  - No arbitrary tau: ROUGE-L distance from gold is maximised, not targeted.
  - Corpus-calibrated thresholds: entropy_min and ttr_min, are all
    derived from the actual data distribution.
  - Per-sample adaptive mode still applies on top: percentile within the local
    pool acts as a secondary signal when K is large enough.
  - TTR is log-normalised to be length-agnostic (Zipf-robust).
  - All scoring features are min-max normalised before weighted combination.
  - Degenerate candidates are ALWAYS quarantined, never returned as hard negatives.

Dataset schema (Arrow / JSONL)
-------------------------------
Each sample is expected to have:
  - "chosen":   list of {role, content} messages — last assistant turn = gold.
  - "rejected": list of candidate responses. Each candidate is itself a list of
                {role, content} messages (multi-turn format). compute_stats and
                select() both accept this nested format and extract the last
                assistant message as the candidate text.
"""
from __future__ import annotations

import json
import gzip
import logging
import math
import re
import zlib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from rouge_score import rouge_scorer
from scipy.stats import entropy as scipy_entropy

logger = logging.getLogger(__name__)

HALLUCINATIONS_FILE = Path("hallucinations.jsonl")
SHORT_RESPONSE_THRESHOLD = 25

# Phase 1.b: structural markers for rescue detection (code, math, lists)
_STRUCTURAL_MARKERS_RE = re.compile(
    r"(?:"
    r"\b(?:def|class|if|else|elif|for|while|return|import|from|try|except|with|lambda|yield"
    r"|SELECT|WHERE|INSERT|UPDATE|DELETE|JOIN|CREATE)\b"
    r"|[+\-*/=<>!&|^~%]{1,3}"
    r"|^\s*(?:\d+[\.\)]\s|[-*]\s|#{1,6}\s)"
    r"|[{}()\[\];:]{2,}"
    r"|\\\\(?:frac|sum|int|prod|lim|infty)"
    r")",
    re.MULTILINE
)

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _interpolated_percentile(sorted_values: list[float], p: float) -> float:
    n = len(sorted_values)
    if n == 0:
        return 0.0
    if n == 1:
        return sorted_values[0]
    idx = p * (n - 1)
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac

def _extract_last_assistant_text(messages: list[dict] | dict) -> str:
    """Estrae l'ultimo turno dell'assistant. Gestisce sia liste di messaggi 
    che strutture dizionario contenenti i messaggi."""
    # Se il candidato è avvolto in un dizionario con metadati (es. per temperatura)
    if isinstance(messages, dict):
        # Direct content field (raw candidate format: {"content": "...", "inference_params": {...}})
        if "content" in messages and "messages" not in messages:
            return messages.get("content") or ""
        messages = messages.get("messages", [])
        
    if not messages or not isinstance(messages, list):
        return ""
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            return msg.get("content") or ""
    return messages[-1].get("content") if isinstance(messages[-1], dict) else ""

def _extract_candidates_from_sample(sample: dict) -> tuple[list, str]:
    """Extract candidates and gold text from a sample.
    
    Supports two formats:
    1. Post-processed: {"chosen": [...], "rejected": [...]}
    2. Raw messages: {"messages": [{"role": "ASSISTANT", "positives": [...], "negatives": [...]}]}
    """
    #logger.info("Estrazione candidati da sample: %s", sample)
    
    # Format 1: already has chosen/rejected. Avoid ambiguous truth-value checks
    chosen = sample.get("chosen", None)
    rejected = sample.get("rejected", None)
    def _normalise_to_list(x):
        if x is None:
            return []
        if isinstance(x, list):
            return x
        if hasattr(x, "tolist"):
            try:
                return x.tolist()
            except Exception:
                pass
        try:
            return list(x)
        except Exception:
            return [x]

    chosen_list = _normalise_to_list(chosen)
    rejected_list = _normalise_to_list(rejected)
    if chosen is not None and rejected is not None and chosen_list and rejected_list:
        gold_text = _extract_last_assistant_text(chosen_list)
        return rejected_list, gold_text

    # Format 2: raw messages with positives/negatives
    messages = sample.get("messages", None)
    gold_text = ""
    candidates = []

    if messages is None:
        messages = []
    elif not isinstance(messages, list):
        if hasattr(messages, "tolist"):
            try:
                messages = messages.tolist()
            except Exception:
                try:
                    messages = list(messages)
                except Exception:
                    messages = [messages]
        else:
            try:
                messages = list(messages)
            except Exception:
                messages = [messages]

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = (msg.get("role") or "").upper()
        if role == "ASSISTANT":
            positives = msg.get("positives") or []
            negatives = msg.get("negatives") or []
            if positives:
                # Gold = first positive's content
                first_pos = positives[0]
                gold_text = first_pos.get("content", "") if isinstance(first_pos, dict) else ""
            candidates = negatives
            break  # take first assistant generation turn

    return candidates, gold_text

def _compute_entropy(tokens: list[str]) -> float:
    if len(tokens) <= 1:
        return 0.0
    counts = Counter(tokens)
    if len(counts) <= 1:
        return 0.0
    probs = [c / len(tokens) for c in counts.values()]
    raw = scipy_entropy(probs, base=2)
    # CORREZIONE: Si normalizza sul log2 dei token UNICI, non totali
    return raw / math.log2(len(counts))

def _compute_log_ttr(tokens: list[str]) -> float:
    n = len(tokens)
    if n < 2:
        return 1.0
    n_unique = len(set(tokens))
    if n_unique == 1:
        return 0.0
    return math.log(n_unique) / math.log(n)

def _rouge_l(scorer, candidate_text: str, gold_text: str) -> float:
    if not candidate_text or not gold_text:
        return 0.0
    return scorer.score(gold_text, candidate_text)["rougeL"].fmeasure

def _sigmoid(x: float) -> float:
    try:
        return 1 / (1 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0

def _compute_length_quality_factor(tokens: list[str], min_quality: int = 15) -> float:
    """Calcola fattore di qualità basato sulla lunghezza del testo.

    Mitiga il bias su testi corti: assegna penalità progressiva alla qualità
    delle metriche (entropy, TTR) per testi sotto la soglia di qualità.

    Args:
        tokens: Lista di token
        min_quality: Lunghezza minima per considerare testo di qualità (default 15)

    Returns:
        Fattore tra 0.2 e 1.0 dove:
        - 0.2: testo molto corto (<3 token)
        - 0.5: testo corto (~8 token)
        - 0.8: testo medio (~12 token)
        - 1.0: testo di qualità (>=15 token)
    """
    length = len(tokens)
    if length >= min_quality:
        return 1.0
    if length < 3:
        return 0.2
    # Transizione lineare progressiva: da 0.3 a 1.0
    ratio = length / min_quality
    return 0.3 + (0.7 * ratio)

def _make_serializable(obj):
    """Recursively convert numpy/pyarrow/pandas array-like objects and
    other non-primitive values to native Python types for JSON serialization.

    Handles: numpy scalars/ndarray/masked arrays, pandas Series/DataFrame,
    pyarrow arrays/tables/scalars, bytes, and objects exposing `tolist()` or
    `to_pylist()`/`as_py()`.
    """
    try:
        import numpy as _np
    except Exception:
        _np = None
    try:
        import pandas as _pd
    except Exception:
        _pd = None
    try:
        import pyarrow as _pa
    except Exception:
        _pa = None

    # Primitive types
    if obj is None or isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, float):
        # JSON can't represent NaN/Inf reliably; convert to None
        try:
            if not math.isfinite(obj):
                return None
        except Exception:
            pass
        return obj

    # Bytes -> decode if possible
    if isinstance(obj, (bytes, bytearray)):
        try:
            return obj.decode("utf-8")
        except Exception:
            return str(obj)

    # Numpy scalar (np.str_, np.int64, etc.)
    if _np is not None and isinstance(obj, _np.generic):
        try:
            val = obj.item()
            return _make_serializable(val)
        except Exception:
            try:
                return float(obj)
            except Exception:
                return str(obj)

    # Pandas
    if _pd is not None:
        if isinstance(obj, _pd.Series):
            return _make_serializable(obj.tolist())
        if isinstance(obj, _pd.DataFrame):
            return _make_serializable(obj.to_dict(orient="records"))

    # PyArrow
    if _pa is not None:
        try:
            if isinstance(obj, (_pa.Array, _pa.ChunkedArray)):
                return _make_serializable(obj.to_pylist())
            if isinstance(obj, _pa.Table):
                return _make_serializable(obj.to_pylist())
            if isinstance(obj, _pa.Scalar):
                return _make_serializable(obj.as_py())
        except Exception:
            pass

    # Numpy arrays (including masked arrays)
    if _np is not None and isinstance(obj, _np.ndarray):
        try:
            return _make_serializable(obj.tolist())
        except Exception:
            try:
                # Fallback: iterate elements
                return [_make_serializable(x) for x in obj]
            except Exception:
                return [str(x) for x in obj]

    # Dict-like: ensure keys are strings (numpy.str_ etc. may appear)
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            try:
                key = _make_serializable(k)
            except Exception:
                key = k
            # Force string keys for JSON
            try:
                key_str = str(key)
            except Exception:
                key_str = repr(key)
            out[key_str] = _make_serializable(v)
        return out

    # List/tuple
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(v) for v in obj]

    # Objects exposing to_pylist/tolist/as_py
    if hasattr(obj, "to_pylist"):
        try:
            return _make_serializable(obj.to_pylist())
        except Exception:
            pass
    if hasattr(obj, "tolist"):
        try:
            return _make_serializable(obj.tolist())
        except Exception:
            pass
    if hasattr(obj, "as_py"):
        try:
            return _make_serializable(obj.as_py())
        except Exception:
            pass

    # Fallback to string representation
    try:
        return str(obj)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Classe HardNegativeConfig
# ---------------------------------------------------------------------------

class HardNegativeConfig:
    def __init__(
        self, 
        uri: str | Path, 
        degenerate_percentile: float = 0.15,
        fn_rouge_percentile: float = 0.30,
        enabled: bool = True
    ):
        self._uri = Path(uri)
        if not self._uri.exists():
            raise FileNotFoundError(f"Dataset non trovato: {self._uri}")

        self._degenerate_percentile = degenerate_percentile
        self._fn_rouge_percentile = fn_rouge_percentile
        self._enabled = enabled

        self._config_dict: dict = {}
        self._pipeline()

    def get_config(self, entry_uri: str | None = None) -> dict:
        return self._config_dict

    def _pipeline(self):
        scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=False)
        logger.info("HardNegativeConfig: scansione globale del dataset '%s'", self._uri)

        entropy_values = []
        ttr_values = []
        rouge_values = []
        length_penalty_values = []
        length_values = []
        
        degenerate_count = 0
        n_samples = 0
        n_candidates = 0
        k_distribution = Counter()
        global_vocab = set()

        # Calcoliamo le statistiche in un unico passo 
        for sample in self._iter_dataset():
            candidates, gold_text = _extract_candidates_from_sample(sample)
            if not candidates:
                continue

            n_samples += 1
            k_distribution[len(candidates)] += 1
            gold_len = len(gold_text.split())

            for cand in candidates:
                n_candidates += 1
                text = _extract_last_assistant_text(cand)
                tokens = text.split()
                global_vocab.update(tokens)

                length_values.append(len(tokens))

                if len(tokens) < 3:
                    entropy_values.append(0.0)
                    ttr_values.append(0.0)
                    degenerate_count += 1
                    r = _rouge_l(scorer, text, gold_text)
                    rouge_values.append(r)
                    length_penalty_values.append(1.0)
                    continue

                ent = _compute_entropy(tokens)
                ttr = _compute_log_ttr(tokens)
                r = _rouge_l(scorer, text, gold_text)

                len_pen = min(abs(len(tokens) - gold_len) / max(gold_len, 1), 1.0)

                entropy_values.append(ent)
                ttr_values.append(ttr)
                rouge_values.append(r)
                length_penalty_values.append(len_pen)

                if ent == 0.0 or ttr == 0.0:
                    degenerate_count += 1

        if n_candidates == 0:
            raise ValueError("Il dataset non ha prodotto candidati validi.")

        corpus_vocab_size = max(len(global_vocab), 2)
        entropy_values.sort()
        ttr_values.sort()
        rouge_values.sort()

        entropy_min = _interpolated_percentile(entropy_values, self._degenerate_percentile)
        ttr_min = _interpolated_percentile(ttr_values, self._degenerate_percentile)
        target_rouge = _interpolated_percentile(rouge_values, self._fn_rouge_percentile)

        def _get_stats(vals: list[float]) -> tuple[float, float]:
            mean = sum(vals) / len(vals)
            var = sum((v - mean) ** 2 for v in vals) / len(vals)
            return mean, max(math.sqrt(var), 1e-9)

        mean_ent, std_ent = _get_stats(entropy_values)
        mean_ttr, std_ttr = _get_stats(ttr_values)
        mean_r, std_r = _get_stats(rouge_values)
        mean_lp, std_lp = _get_stats(length_penalty_values)
        mean_length, std_length = _get_stats(length_values) if length_values else (0.0, 1.0)

        # Beta adattivo basato su Coefficient of Variation
        cv = std_length / mean_length if mean_length > 0 else 1.0
        beta_adaptive = 1.0 - min(cv, 1.0) * 0.5

        self._config_dict = {
            "enabled": self._enabled,
            "degenerate_percentile": self._degenerate_percentile,
            "fn_rouge_percentile": self._fn_rouge_percentile,
            "corpus_vocabulary_size": corpus_vocab_size,
            "entropy_min": entropy_min,
            "ttr_min": ttr_min,
            "global_stats": {
                "entropy": {"mean": mean_ent, "std": std_ent},
                "ttr": {"mean": mean_ttr, "std": std_ttr},
                "rouge": {"mean": mean_r, "std": std_r},
                "length_pen": {"mean": mean_lp, "std": std_lp},
                "target_rouge_cutoff": target_rouge,
                "mean_length": mean_length,
                "std_length": std_length,
                "cv_length": cv,
                "beta_adaptive": beta_adaptive
            },
            "metrics_summary": {
                "total_samples": n_samples,
                "total_candidates": n_candidates,
                "degenerate_count": degenerate_count,
                "degenerate_ratio": degenerate_count / max(n_candidates, 1),
                "k_distribution": dict(sorted(k_distribution.items())),
            }
        }
        logger.info("HardNegativeConfig: Calibrazione globale completata con successo.")

    def _iter_dataset(self):
        # Handle directories: find data files inside and iterate them
        if self._uri.is_dir():
            yield from self._iter_directory()
            return
        suffix = self._uri.suffix.lower()
        if suffix == ".arrow":
            yield from self._iter_arrow(self._uri)
        elif suffix in {".jsonl", ".json", ".jsonlines", ".jsonl.gz", ".gz"}:
            yield from self._iter_jsonl(self._uri)
        else:
            try:
                yield from self._iter_arrow(self._uri)
            except Exception:
                yield from self._iter_jsonl(self._uri)

    def _iter_directory(self):
        """Iterate data files in a directory (arrow > jsonl.gz > jsonl > parquet)."""
        arrow_files = sorted(self._uri.glob("*.arrow"))
        if arrow_files:
            for f in arrow_files:
                yield from self._iter_arrow(f)
            return
        jsonl_files = sorted(self._uri.glob("*.jsonl")) + sorted(self._uri.glob("*.jsonlines")) + sorted(self._uri.glob("*.jsonl.gz")) + sorted(self._uri.glob("*.gz"))
        if jsonl_files:
            for f in jsonl_files:
                yield from self._iter_jsonl(f)
            return
        parquet_files = sorted(self._uri.glob("*.parquet"))
        if parquet_files:
            yield from self._iter_parquet(parquet_files)
            return
        raise FileNotFoundError(
            f"Nessun file dati (arrow/jsonl/parquet) trovato in: {self._uri}"
        )

    def _iter_arrow(self, filepath: Path | None = None):
        import pyarrow as pa
        import pyarrow.ipc as ipc
        
        target = filepath or self._uri
        # CORREZIONE: Robustezza nella lettura di file Arrow. 
        # Tenta prima lo Stream reader (standard di HF datasets) e poi fallback su File reader.
        try:
            with ipc.open_stream(target) as reader:
                table = reader.read_all()
                for row in table.to_pylist():
                    yield row
        except Exception:
            with ipc.open_file(target) as reader:
                table = reader.read_all()
                for row in table.to_pylist():
                    yield row

    def _iter_jsonl(self, filepath: Path | None = None):
        target = filepath or self._uri

        # Verifica se il file è compresso controllando l'estensione
        is_gzip = str(target).endswith(".gz")

        # Seleziona la funzione di apertura e la modalità corretta
        open_func = gzip.open if is_gzip else open
        mode = "rt" if is_gzip else "r"

        with open_func(target, mode=mode, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)

    def _iter_parquet(self, files: list[Path]):
        import pandas as pd
        for f in files:
            df = pd.read_parquet(f)
            for row in df.to_dict("records"):
                yield row


# ---------------------------------------------------------------------------
# HardNegativeFilter
# ---------------------------------------------------------------------------

class HardNegativeFilter:
    def __init__(self, config: dict):
        self.config = config
        self._scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=False)

        self._entropy_min = config.get("entropy_min", 0.0)
        self._ttr_min = config.get("ttr_min", 0.0)

        self._g_stats = config.get("global_stats", {})
        self._rouge_cutoff_global = self._g_stats.get("target_rouge_cutoff", 1.0)

        self._w_entropy = config.get("w_entropy", 0.20)
        self._w_ttr = config.get("w_ttr", 0.20)
        self._w_rouge_dist = config.get("w_rouge_dist", 0.40)
        self._w_length_pen = config.get("w_length_pen", 0.20)

        # M-curve length penalty parameters
        self._use_length_penalty = config.get("use_length_penalty", True)
        # Beta adattivo: valore calibrato
        self._beta = self._g_stats.get("beta_adaptive", 0.5)
        self._outlier_std_mult = config.get("outlier_std", 1.2)
        self._suspected_std = config.get("suspected_std", 3.0)
        self._gamma = config.get("gamma", 0.2)
        self._mean_length = self._g_stats.get("mean_length", 50.0)
        self._std_length = self._g_stats.get("std_length", 30.0)

        self._hallucinations_path = HALLUCINATIONS_FILE

        # Phase 1.b structural rescue thresholds
        self._compression_ratio_min = config.get("rescue_compression_ratio_min", 0.35)
        self._ngram_rep_rate_max = config.get("rescue_ngram_rep_rate_max", 0.60)

    def select(
        self,
        candidates: list,
        gold_content: str,
        temperature: float | None = None,
        sample_metadata: dict | None = None,
    ) -> dict | list | None:
        if not self.config.get("enabled", True):
            return candidates[0] if candidates else None
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]

        # Phase 1.a: partition degenerate
        clean, quarantined = self._partition_degenerate(candidates, gold_content)

        # Phase 1.b: structural rescue attempt on quarantined candidates
        rescued = self._rescue_structural(quarantined) if quarantined else []

        if rescued:
            # ROUGE-only mode: composite scoring loses meaning for code/math/lists
            survivors = clean + rescued
            surviving, _ = self._filter_false_negatives(survivors, gold_content)
            if surviving:
                return self._select_lowest_rouge(surviving, gold_content)
            if self.config.get("fallback") == "temperature" and temperature is not None:
                return self._select_by_temperature(survivors, temperature)
            return None

        # Normal flow: quarantined confirmed degenerate
        if not clean:
            self._append_hallucinations(candidates, sample_metadata, gold_content)
            return None

        surviving, _ = self._filter_false_negatives(clean, gold_content)

        if surviving:
            best = self._rank_candidates(surviving, gold_content)
            if best is not None:
                return best

        if self.config.get("fallback") == "temperature" and temperature is not None:
            return self._select_by_temperature(clean or candidates, temperature)

        return None

    def _partition_degenerate(self, candidates: list, gold_content: str = "") -> tuple[list, list]:
        clean = []
        degenerate = []

        for cand in candidates:
            content = _extract_last_assistant_text(cand)
            tokens = content.split()

            # Short responses (≤25 tokens): entropy/TTR numerically unstable.
            # Use repetition detection only; exact-match with gold handled in Phase 2.
            if len(tokens) <= SHORT_RESPONSE_THRESHOLD:
                unique_ratio = len(set(tokens)) / len(tokens) if tokens else 0.0
                if not content.strip() or unique_ratio <= 0.5:
                    degenerate.append(cand)
                else:
                    clean.append(cand)
                continue

            # Standard path (>25 tokens): entropy/TTR check
            ent = _compute_entropy(tokens)
            ttr = _compute_log_ttr(tokens)

            if ent < self._entropy_min or ttr < self._ttr_min:
                degenerate.append(cand)
            else:
                clean.append(cand)

        return clean, degenerate

    def _rescue_structural(self, quarantined: list) -> list:
        """Phase 1.b: Rescue quarantined candidates with benign structural repetition.

        Discriminant: has_markers AND compression_ratio >= threshold AND ngram_rep <= threshold.
        Targets code, math, and step-lists that have low entropy/TTR but are NOT hallucinations.
        """
        rescued = []
        for cand in quarantined:
            content = _extract_last_assistant_text(cand)
            if not content.strip():
                continue
            tokens = content.split()
            if len(tokens) <= SHORT_RESPONSE_THRESHOLD:
                continue  # too short for reliable structural analysis

            # 1. Marker density: must have structural markers
            markers = _STRUCTURAL_MARKERS_RE.findall(content)
            if not markers:
                continue

            # 2. Compression ratio (zlib) >= threshold
            text_bytes = content.encode("utf-8")
            compression_ratio = len(zlib.compress(text_bytes)) / len(text_bytes)
            if compression_ratio < self._compression_ratio_min:
                continue

            # 3. N-gram repetition rate <= threshold
            bigrams = list(zip(tokens, tokens[1:]))
            ngram_rep_rate = 1.0 - (len(set(bigrams)) / max(len(bigrams), 1))
            if ngram_rep_rate > self._ngram_rep_rate_max:
                continue

            rescued.append(cand)
        return rescued

    def _select_lowest_rouge(self, candidates: list, gold_content: str):
        """ROUGE-only selection: pick candidate most different from gold.

        Used in rescue mode where composite scoring loses meaning for
        structured content (code/math/lists).
        """
        best_cand = None
        best_rouge = float("inf")
        for cand in candidates:
            content = _extract_last_assistant_text(cand)
            r_score = _rouge_l(self._scorer, content, gold_content)
            if r_score < best_rouge:
                best_rouge = r_score
                best_cand = cand
        return best_cand

    def _filter_false_negatives(self, candidates: list, gold_content: str) -> tuple[list, int]:
        surviving = []
        filtered_count = 0
        gold_normalized = gold_content.strip().lower()

        for cand in candidates:
            content = _extract_last_assistant_text(cand)
            # Exact match with gold = false negative (moved from Phase 1)
            if content.strip().lower() == gold_normalized:
                filtered_count += 1
                continue
            # ROUGE-L proximity check
            r_score = _rouge_l(self._scorer, content, gold_content)
            if r_score <= self._rouge_cutoff_global:
                surviving.append(cand)
            else:
                filtered_count += 1

        return surviving, filtered_count

    def _rank_candidates(self, candidates: list, gold_content: str):
        if not candidates:
            return None

        gold_len = len(gold_content.split())
        best_score = float("-inf")
        best_cand = None

        def _soft_norm(val: float, key: str, invert: bool = False) -> float:
            stats = self._g_stats.get(key, {"mean": 0.5, "std": 1.0})
            z = (val - stats["mean"]) / stats["std"]
            score = _sigmoid(z)
            return (1.0 - score) if invert else score

        for cand in candidates:
            content = _extract_last_assistant_text(cand)
            tokens = content.split()

            if not tokens:
                continue

            ent = _compute_entropy(tokens)
            ttr = _compute_log_ttr(tokens)
            rouge_l = _rouge_l(self._scorer, content, gold_content)

            n_ent = _soft_norm(ent, "entropy")
            n_ttr = _soft_norm(ttr, "ttr")
            n_dist = _soft_norm(rouge_l, "rouge", invert=True)

            if self._use_length_penalty:
                p_len = self._compute_m_curve_penalty(len(tokens), gold_len)
                score = (
                    self._w_entropy * n_ent
                    + self._w_ttr * n_ttr
                    + self._w_rouge_dist * n_dist
                    + self._w_length_pen * p_len
                )
            else:
                w_sum = self._w_entropy + self._w_ttr + self._w_rouge_dist
                score = (
                    (self._w_entropy / w_sum) * n_ent
                    + (self._w_ttr / w_sum) * n_ttr
                    + (self._w_rouge_dist / w_sum) * n_dist
                )

            if score > best_score:
                best_score = score
                best_cand = cand

        return best_cand

    def _compute_m_curve_penalty(self, candidate_len: int, gold_len: int) -> float:
        """Double-Gaussian M-curve length penalty.

        Returns a score in [0.1, 1.0] that penalizes:
        - Exact match with target (suspected false negative, narrow dip)
        - Large deviations from target (outliers, wide falloff)
        """
        l_hat = self._beta * gold_len + (1 - self._beta) * self._mean_length
        d = abs(candidate_len - l_hat)
        sigma_wide = max(self._std_length * self._outlier_std_mult, 1e-6)
        sigma_narrow = max(self._suspected_std, 1e-6)
        p_raw = math.exp(-d**2 / (2 * sigma_wide**2)) - self._gamma * math.exp(-d**2 / (2 * sigma_narrow**2))
        return max((p_raw + self._gamma) / (1 + self._gamma), 0.1)

    def _append_hallucinations(self, candidates: list, sample_metadata: dict | None, gold_content: str = "") -> None:
        # Compute diagnostic scores for each candidate
        scored_candidates = []
        for cand in candidates:
            content = _extract_last_assistant_text(cand)
            tokens = content.split()
            diag: dict = {}
            if tokens:
                diag["token_count"] = len(tokens)
                diag["unique_ratio"] = len(set(tokens)) / len(tokens)
                if len(tokens) > SHORT_RESPONSE_THRESHOLD:
                    diag["entropy"] = round(_compute_entropy(tokens), 4)
                    diag["ttr"] = round(_compute_log_ttr(tokens), 4)
                    diag["rouge_l_vs_gold"] = round(_rouge_l(self._scorer, content, gold_content), 4) if gold_content else None
                    # Structural rescue diagnostics
                    text_bytes = content.encode("utf-8")
                    diag["compression_ratio"] = round(len(zlib.compress(text_bytes)) / len(text_bytes), 4)
                    bigrams = list(zip(tokens, tokens[1:]))
                    diag["ngram_rep_rate"] = round(1.0 - (len(set(bigrams)) / max(len(bigrams), 1)), 4)
                    diag["structural_markers"] = len(_STRUCTURAL_MARKERS_RE.findall(content))
            scored_candidates.append({"candidate": cand, "diagnostics": diag})

        record = {
            "gold_content": gold_content,
            "candidates": scored_candidates,
            "metadata": sample_metadata or {},
        }
        sanitized = _make_serializable(record)
        try:
            with open(self._hallucinations_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(sanitized, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.error("HN Scrittura fallita su %s: %s", self._hallucinations_path, exc)

    @staticmethod
    def _select_by_temperature(items: list, temperature: float):
        if not items:
            return {}
        # CORREZIONE: Gestione sicura nel caso 'it' sia una lista (multi-turn) 
        # o un dizionario contenente metadati aggiuntivi.
        def _get_temp(it):
            if isinstance(it, dict):
                return (it.get("inference_params") or {}).get("temperature", float("inf"))
            return float("inf")

        return min(items, key=lambda it: abs(_get_temp(it) - temperature))
