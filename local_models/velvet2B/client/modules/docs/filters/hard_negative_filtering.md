# Hard Negative Filtering — Technical Documentation

**Last updated:** 2026-06-04  
**Module:** `modules/filters/hard_negative_filtering.py`  
**Test file:** `tests/test_hard_negative_filtering.py`

---

## Overview

The Hard Negative Filtering module implements an NLP-based 3-phase pipeline for selecting optimal "rejected" candidates in DPO (Direct Preference Optimization) training. Instead of randomly picking a negative or using temperature-based selection, it uses corpus-calibrated metrics to find candidates that are:

1. **Not degenerate** (no loops, hallucinations, or truncated outputs)
2. **Not false negatives** (not near-duplicates of the gold/chosen response)
3. **Maximally informative** as training signal (best multi-attribute score)

---

## Architecture

### Two-Class Design

| Class | Responsibility |
|-------|---------------|
| `HardNegativeConfig` | Corpus-level calibration — scans the full dataset once to derive thresholds (entropy_min, ttr_min, ROUGE-L cutoff, mean_length, std_length) |
| `HardNegativeFilter` | Per-sample selection — takes a pool of K candidates and returns the best hard negative |

### Pipeline Flow (in `prepare.py`)

```
config.yml → HardNegativeConfig(uri) → get_config() → inject weights + M-curve params → HardNegativeFilter(config) → template_fn(..., hn_filter=filter)
```

### Selection Pipeline

```
Candidates (K pool)
    │
    ▼
Phase 1.a: Degenerate Detection
    - Entropy < threshold → quarantine (>25 tokens)
    - TTR < threshold → quarantine (>25 tokens)
    - Short (≤25 tokens): unique_ratio ≤ 0.5 → quarantine
    │
    ├─── quarantined ───▶ Phase 1.b: Structural Rescue
    │                       - Marker density > 0
    │                       - Compression ratio (zlib) ≥ config.rescue_compression_ratio_min
    │                       - N-gram rep rate ≤ config.rescue_ngram_rep_rate_max
    │                       - Pass all 3 → RESCUED
    ▼
    clean
    │
    ├─── IF rescued non-empty 
    │         ▼                                              
    │    survivors = clean + rescued                        
    │         ▼                                           
    │    Phase 2: False Negative Filtering                 
    │         - Exact match with gold → filter            
    │         - ROUGE-L > cutoff → filter                  
    │         ▼                                         
    │    ROUGE-only Selection (no Phase 3)                
    │         - Pick candidate with LOWEST ROUGE-L         
    │         - Composite scoring loses meaning for       
    │           code/math/lists                            
    │                                                      
    ├─── [Otherwise] IF not rescued (normal flow)
    │
    ▼
Phase 2: False Negative Filtering
    - Exact match with gold → filter out
    - ROUGE-L(candidate, gold) > cutoff → filter out
    │
    ▼
Phase 3: Multi-Attribute Scoring (dual-mode)
    Mode A (use_length_penalty=True):
        score = w1*ent + w2*ttr + w3*rouge_dist + w4*M_curve_penalty
    Mode B (use_length_penalty=False):
        score = (w1/(w1+w2+w3))*ent + (w2/(w1+w2+w3))*ttr + (w3/(w1+w2+w3))*rouge_dist
    Select argmax
    │
    ▼
Fallback (if no candidate survives):
    - "temperature": delegate to temperature-based selection from clean pool
    - "drop": return None (sample skipped)
```

---

## NLP Metrics Used

### Normalized Entropy
```
H_norm = H(tokens) / log2(|unique_tokens|)
```
Range: [0, 1]. Detects repetitive/looping text (H_norm ≈ 0).

### Log-TTR (Type-Token Ratio)
```
log_TTR = log(|unique_tokens|) / log(|total_tokens|)
```
Length-agnostic diversity measure (Zipf-robust). Range: [0, 1].

### ROUGE-L F-measure
Longest common subsequence overlap with gold. Used to:
- Filter false negatives (too similar to gold), including exact-match detection
- Score candidates (inverted: lower ROUGE = more different = better hard negative)
- In rescue mode: used as sole selection criterion (lowest ROUGE = best)

### Soft Normalization (Sigmoid z-score)
All features (entropy, TTR, ROUGE-L) are normalized using corpus-level mean/std:
```
z = (value - mean) / std
score = sigmoid(z)
```
This maps features to (0, 1) using the global distribution as reference.

---

## Phase 1.b: Structural Rescue

### Purpose

Candidates quarantined in Phase 1.a (low entropy/TTR) may be **benign repetitive content** — code, math, or step-lists — rather than pathological loops. Phase 1.b rescues these using structural analysis.

### Discriminant

A quarantined candidate is rescued if ALL three conditions are met:

```
has_structural_markers AND compression_ratio >= 0.35 AND ngram_rep_rate <= 0.60
```

### Metrics

| Metric | Formula | What it detects |
|--------|---------|-----------------|
| Structural Marker Density | Regex count of code keywords, math operators, list markers, punctuation clusters | Presence of formal structure |
| Compression Ratio (zlib) | `len(zlib.compress(text)) / len(text)` | Exact repetition vs structural variety |
| N-gram Repetition Rate | `1 - (unique_bigrams / total_bigrams)` | Bigram-level loop detection |

### Pattern Discrimination Table

| Pattern | Compression | N-gram rep | Marker density | Verdict |
|---------|-------------|-----------|----------------|---------|
| Loop patologico | Molto basso (<0.35) | Alto (>0.60) | Basso (0) | NOT rescued |
| Codice/Math | Medio-alto (≥0.35) | Medio (≤0.60) | Alto (>0) | RESCUED |
| Lista ripetitiva benigna | Medio (≥0.35) | Medio (≤0.60) | Alto (bullets) | RESCUED |
| Testo generale | Alto | Basso | Basso | N/A (passes Phase 1.a) |

### Thresholds

- `rescue_compression_ratio_min: 0.35` — hardcoded, language-dependent
- `rescue_ngram_rep_rate_max: 0.60` — hardcoded, language-dependent

These do not have adaptive formulas — they depend on corpus language, not on sample length. Tune manually for agglutinative languages.

### Behavior on Rescue

When at least one candidate is rescued:
1. Survivors = Phase 1.a clean + rescued candidates
2. Apply Phase 2 only (ROUGE + exact-match filtering)
3. Select candidate with **lowest ROUGE-L** (maximally different from gold)
4. **Skip Phase 3** — composite scoring (entropy, TTR, M-curve) loses meaning for structural content

When zero candidates are rescued: quarantined are confirmed degenerate, normal Phase 2 → Phase 3 flow applies.

---

## M-Curve Length Penalty (Mode A)

The M-curve is a double-Gaussian penalty that rewards candidates at a "sweet spot" distance from the target length, penalizing both:
- **Exact match** with target (suspected false negative — narrow dip)
- **Large deviations** from target (outliers — wide falloff)

### Formula

**Phase A — Target ponderato:**
$$\hat{l} = \beta \cdot l_{gold} + (1 - \beta) \cdot \mu$$

Dove $\mu$ = media di lunghezza del dataset (calcolata in calibrazione).

**Phase B — Distanza:**
$$d = |l_{candidate} - \hat{l}|$$

**Phase C — Double-Gaussian score:**
$$P_{raw}(d) = \exp\left( -\frac{d^2}{2\sigma_{wide}^2} \right) - \gamma \cdot \exp\left( -\frac{d^2}{2\sigma_{narrow}^2} \right)$$

$$P_{final}(d) = \max\left( \frac{P_{raw}(d) + \gamma}{1 + \gamma}, \, 0.1 \right)$$

### Parameter Table

| Parametro | Config Key | Default | Descrizione |
|-----------|-----------|---------|-------------|
| $\beta$ | `beta_sample_entry_calibration` | Auto (CV-based) | Bilancia tra lunghezza gold ($\beta$→1) e media dataset ($\beta$→0). Auto: `1.0 - min(CV, 1.0) * 0.5` |
| $\sigma_{wide}$ | (calcolato) | `std_length * outlier_std` | Controlla la tolleranza agli outlier |
| `outlier_std` | `outlier_std` | 1.2 | Moltiplicatore per $\sigma_{wide}$ |
| $\sigma_{narrow}$ | `suspected_std` | 3.0 | Finestra stretta per detection falsi negativi (in token) |
| $\gamma$ | `gamma` | 0.2 | Profondità del dip centrale (malus falso negativo) |

### Comportamento di $\beta$

**$\beta$ è ora calcolato adattivamente** dalla distribuzione dei dati durante la calibrazione:

```
CV = std_length / mean_length   (Coefficient of Variation)
β_adaptive = 1.0 - min(CV, 1.0) * 0.5
```

| CV | β | Comportamento |
|----|---|---------------|
| 0.1 | 0.95 | Distribuzione stretta → focus locale (gold) |
| 0.5 | 0.75 | Distribuzione moderata |
| 1.0 | 0.50 | Distribuzione larga → equilibrio gold/media |

L'override manuale è possibile impostando `beta_sample_entry_calibration` in config.yml. Se non specificato, viene usato il valore adattivo calibrato dal dataset.

- **$\beta$ → 1 (Focus Locale):** Target ancorato su $l_{gold}$. Il modello deve seguire la lunghezza dell'annotatore.
- **$\beta$ → 0 (Focus Globale):** Target ancorato su $\mu$. Il modello viene spinto verso la media del dataset.
- **$\beta$ = 0.5 (Equilibrio):** Baricentro tra lunghezza sample e media dataset.

### Output Range

$P_{final} \in [0.1, 1.0]$ — usato **direttamente** come componente dello score (non passa per soft_norm).

---

## Mode B: Scoring Senza Penalità di Lunghezza

Quando `use_length_penalty=False`, lo scoring usa solo entropy, TTR, e ROUGE-L distance con pesi rinormalizzati a somma 1.0:

```
w_sum = w1 + w2 + w3
score = (w1/w_sum)*n_ent + (w2/w_sum)*n_ttr + (w3/w_sum)*n_dist
```

Utile per dataset con risposte di lunghezza eterogenea dove la lunghezza non è un segnale informativo.

---

## Configuration (`config.yml`)

```yaml
hard_negative_enabled: true
hard_negative_params:
  config_based_fallback: temperature  # "temperature" | "drop"
  w1: 0.2   # entropy weight
  w2: 0.2   # TTR weight
  w3: 0.4   # ROUGE-L distance weight (dominant)
  w4: 0.2   # length penalty weight (Mode A only)
  use_length_penalty: true              # true = Mode A (M-curve), false = Mode B
  outlier_std: 1.2                      # sigma_wide multiplier
  suspected_std: 3.0                    # sigma_narrow (token)
  gamma: 0.2                            # central dip strength
  # Phase 1.b structural rescue thresholds (language-dependent, tune per corpus)
  rescue_compression_ratio_min: 0.35    # zlib compression floor
  rescue_ngram_rep_rate_max: 0.60       # bigram repetition ceiling
```

---

## Calibrazione (`HardNegativeConfig`)

La classe `HardNegativeConfig` scandisce l'intero dataset una volta e produce:

| Statistica | Uso |
|-----------|-----|
| `entropy_min` | Soglia Phase 1 (percentile-based) |
| `ttr_min` | Soglia Phase 1 (percentile-based) |
| `target_rouge_cutoff` | Soglia Phase 2 (percentile-based) |
| `global_stats.entropy.{mean, std}` | Soft normalization Phase 3 |
| `global_stats.ttr.{mean, std}` | Soft normalization Phase 3 |
| `global_stats.rouge.{mean, std}` | Soft normalization Phase 3 |
| `global_stats.mean_length` | $\mu$ per M-curve |
| `global_stats.std_length` | $\sigma_{dataset}$ per M-curve |
| `global_stats.cv_length` | Coefficient of Variation (std/mean) |
| `global_stats.beta_adaptive` | $\beta$ calcolato da CV |

---

## Helper Functions

| Funzione | Riga | Descrizione |
|----------|------|-------------|
| `_interpolated_percentile()` | 66 | Interpolazione lineare per percentili da valori ordinati |
| `_extract_last_assistant_text()` | 78 | Estrae ultimo turno assistant (gestisce dict/list) |
| `_extract_candidates_from_sample()` | 95 | Parsing formato chosen/rejected o messages/positives/negatives |
| `_compute_entropy()` | 166 | Entropy normalizzata su log2(unique_tokens) |
| `_compute_log_ttr()` | 177 | Log-TTR (length-agnostic) |
| `_rouge_l()` | 186 | ROUGE-L F-measure via rouge_score |
| `_sigmoid()` | 191 | Sigmoid con overflow protection |
| `_compute_length_quality_factor()` | 197 | [DEPRECATA — non più utilizzata nella pipeline] |
| `_make_serializable()` | 223 | Conversione ricorsiva per JSON (numpy/pyarrow/pandas) |

---

## `HardNegativeFilter` — Metodi

| Metodo | Descrizione |
|--------|-------------|
| `__init__(config)` | Inizializza pesi, soglie, parametri M-curve e rescue da config dict |
| `select(candidates, gold_content, temperature, sample_metadata)` | Orchestratore principale — Phase 1.a → 1.b → branching → Phase 2 → Phase 3 |
| `_partition_degenerate(candidates, gold_content)` | Phase 1.a: separa clean/quarantined (entropy/TTR + unique_ratio) |
| `_rescue_structural(quarantined)` | Phase 1.b: rescue basato su marker+compression+ngram |
| `_filter_false_negatives(candidates, gold_content)` | Phase 2: filtra exact-match e ROUGE-L > cutoff |
| `_rank_candidates(candidates, gold_content)` | Phase 3: scoring multi-attributo (dual-mode) |
| `_select_lowest_rouge(candidates, gold_content)` | Selezione ROUGE-only per rescue mode |
| `_compute_m_curve_penalty(candidate_len, gold_len)` | Calcola P_final della double-Gaussian |
| `_append_hallucinations(candidates, sample_metadata)` | Log degenerate su hallucinations.jsonl |
| `_select_by_temperature(items, temperature)` | Fallback: selezione per temperatura più vicina |

---

## Test

```bash
PYTHONPATH=. python -m pytest tests/test_hard_negative_filtering.py -v
```

55 test cases covering:
- Helper function unit tests (entropy, TTR, percentile, text extraction)
- HardNegativeFilter unit tests (degenerate detection, false negative filtering, scoring, fallback)
- HardNegativeConfig integration tests (JSONL file, directory iteration, mean_length/std_length)
- End-to-end pipeline tests (config → filter → select)
- Template integration tests (apply_chat_template with/without filter)
- prepare.py flow simulation tests (full flow matching production code path)
- M-Curve penalty unit tests (target, outlier, floor, M-shape dip, beta behavior)
- Scoring modes tests (Mode A with M-curve, Mode B without, weight renormalization)
- Exact-match relocation tests (Phase 1 → Phase 2 move)
- Structural rescue tests (code/math rescued, loops rejected, thresholds)
- Rescue flow branching tests (ROUGE-only mode vs normal flow)
- Calibration length stats tests (mean_length/std_length in output)
