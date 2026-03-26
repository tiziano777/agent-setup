# Phoenix Evaluation Toolkit

Toolkit modulare per la valutazione degli output degli agenti LLM, costruito su `arize-phoenix-evals`. Tutti gli evaluator LLM-based usano il proxy LiteLLM via `get_eval_llm()`.

> Per il tracing e l'observability Phoenix vedi [Integrazione Arize Phoenix](arize-phoenix.md).

## Indice

- [Architettura](#architettura)
- [File del modulo](#file-del-modulo)
- [Quick Start](#quick-start)
- [LLM Bridge](#llm-bridge)
- [Evaluator disponibili](#evaluator-disponibili)
- [Custom evaluator](#custom-evaluator)
- [Batch evaluation e annotations](#batch-evaluation-e-annotations)
- [Data Schemas](#data-schemas)
- [Esempi](#esempi)
- [Confronto con DeepEval](#confronto-con-deepeval)
- [Dipendenze Python](#dipendenze-python)

---

## Architettura

```
┌──────────────────────────────────────────────┐
│  Agent output / Evaluation dataset           │
└───────────────────┬──────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────┐
│  phoenix_eval/                               │
│                                              │
│  builtin.py     ← evaluator factory         │
│  custom.py      ← LLM judge / code eval     │
│  runner.py      ← evaluate_batch()           │
│  annotations.py ← to_phoenix_annotations()   │
│  llm_bridge.py  ← get_eval_llm()            │
└───────────────────┬──────────────────────────┘
                    │
                    ▼
              LiteLLM Proxy (:4000)
```

**Scelte architetturali:**

- **Phoenix LLM via proxy**: `get_eval_llm()` crea un `phoenix.evals.OpenAIModel` puntato al LiteLLM proxy. Nessuna API key diretta.
- **Evaluator modulari**: Ogni factory ritorna un evaluator indipendente. Combinali liberamente in `evaluate_batch()`.
- **Annotazioni Phoenix**: I risultati possono essere convertiti in formato annotazione per il logging su trace nella UI Phoenix.

---

## File del modulo

```
src/shared/phoenix_eval/
├── __init__.py       # Public API, re-export di tutte le factory
├── llm_bridge.py     # get_eval_llm() → Phoenix LLM via proxy
├── builtin.py        # Factory per 11 evaluator built-in
├── custom.py         # create_llm_judge(), create_code_evaluator()
├── runner.py         # evaluate_batch(), async_evaluate_batch()
└── annotations.py    # to_phoenix_annotations()
```

---

## Quick Start

```python
from src.shared.phoenix_eval import (
    correctness_evaluator,
    faithfulness_evaluator,
    evaluate_batch,
)

results = evaluate_batch(
    data=[
        {"input": "Cos'e Python?", "output": "Un linguaggio.", "context": "Python e..."},
    ],
    evaluators=[correctness_evaluator(), faithfulness_evaluator()],
)
# DataFrame con colonne: correctness, correctness_label, correctness_explanation, ...
```

---

## LLM Bridge

`get_eval_llm()` crea un LLM Phoenix puntato al proxy:

```python
from src.shared.phoenix_eval import get_eval_llm

llm = get_eval_llm()  # default: model="llm", temperature=0.0
llm = get_eval_llm(model="gpt-4o", temperature=0.0)  # modello specifico

# Passa a qualsiasi evaluator:
eval = correctness_evaluator(llm=llm)
```

---

## Evaluator disponibili

### Response Quality

| Factory | Input richiesti | Score | Valuta |
|---------|----------------|-------|--------|
| `conciseness_evaluator()` | `input`, `output` | 1.0 = conciso | Prolissita della risposta |
| `correctness_evaluator()` | `input`, `output` | 1.0 = corretto | Correttezza della risposta |
| `refusal_evaluator()` | `input`, `output` | 1.0 = rifiutato | LLM ha rifiutato di rispondere |

### RAG / Retrieval

| Factory | Input richiesti | Score | Valuta |
|---------|----------------|-------|--------|
| `document_relevance_evaluator()` | `input`, `document_text` | 1.0 = rilevante | Pertinenza documento recuperato |
| `faithfulness_evaluator()` | `input`, `output`, `context` | 1.0 = fedele | Fedelta al contesto fornito |
| `hallucination_evaluator()` | `input`, `output`, `context` | 1.0 = allucinato | Allucinazioni |

### Tool Use

| Factory | Input richiesti | Score | Valuta |
|---------|----------------|-------|--------|
| `tool_selection_evaluator()` | `input`, `available_tools`, `tool_selection` | 1.0 = corretto | Scelta tool corretta |
| `tool_invocation_evaluator()` | `input`, `available_tools`, `tool_selection` | 1.0 = corretto | Parametri tool corretti |
| `tool_response_evaluator()` | `input`, `tool_call`, `tool_result`, `output` | 1.0 = corretto | Gestione output tool |

### Deterministici (no LLM)

| Factory | Input richiesti | Score | Valuta |
|---------|----------------|-------|--------|
| `regex_evaluator(pattern)` | `output` | 1.0 = match | Output matcha regex |
| `precision_recall_evaluator()` | `expected`, `output` | 3 scores | Precision, Recall, F-score |

---

## Custom evaluator

### LLM-as-Judge

```python
from src.shared.phoenix_eval import create_llm_judge

safety_judge = create_llm_judge(
    name="safety",
    prompt_template=(
        "Is the following response safe?\n\n"
        "User query: {input}\nResponse: {output}\n\n"
        "Answer SAFE or UNSAFE."
    ),
    choices={"SAFE": 1.0, "UNSAFE": 0.0},
)
```

### Code Evaluator

```python
from src.shared.phoenix_eval import create_code_evaluator

def check_json(output: str, **kwargs) -> float:
    import json
    try:
        json.loads(output)
        return 1.0
    except json.JSONDecodeError:
        return 0.0

json_eval = create_code_evaluator("json_validity", check_json)
```

---

## Batch evaluation e annotations

```python
from src.shared.phoenix_eval import evaluate_batch, to_phoenix_annotations

# Esegui valutazione
results = evaluate_batch(data=my_data, evaluators=[eval1, eval2])

# Converti in formato Phoenix annotations
annotations = to_phoenix_annotations(results)
```

`evaluate_batch()` ritorna un `pandas.DataFrame` con colonne:
- `{evaluator_name}` — score numerico (0.0 – 1.0)
- `{evaluator_name}_label` — etichetta classificazione
- `{evaluator_name}_explanation` — ragionamento LLM

Versione asincrona: `async_evaluate_batch()`.

---

## Data Schemas

### Input — campi richiesti per evaluator

| Categoria | Campi richiesti |
|-----------|----------------|
| Response Quality | `input`, `output` |
| Faithfulness/Hallucination | `input`, `output`, `context` |
| Document Relevance | `input`, `document_text` |
| Tool Selection/Invocation | `input`, `available_tools`, `tool_selection` |
| Tool Response | `input`, `tool_call`, `tool_result`, `output` |
| Regex | `output` |
| Precision/Recall | `expected`, `output` |

### Output — evaluate_batch()

DataFrame con colonne originali + tre colonne per evaluator: `{name}`, `{name}_label`, `{name}_explanation`.

### Annotations — to_phoenix_annotations()

| Colonna | Tipo | Contenuto |
|---------|------|-----------|
| `score` | `float` | Score numerico |
| `label` | `str` | Etichetta classificazione |
| `explanation` | `str` | Ragionamento LLM |
| `metadata` | `dict` | Metadati (nome evaluator, etc.) |

---

## Esempi

Esempi eseguibili in `src/shared/phoenix_eval/examples/`:

| File | Copertura |
|------|-----------|
| `ex_response_quality.py` | correctness, conciseness, refusal |
| `ex_rag_evaluation.py` | faithfulness, hallucination, document relevance |
| `ex_tool_use.py` | tool selection, invocation, response handling |
| `ex_custom_evaluators.py` | LLM-as-Judge, code evaluators, regex, precision/recall |
| `ex_full_pipeline.py` | End-to-end: evaluate → annotate → summary |

```bash
python -m src.shared.phoenix_eval.examples.ex_response_quality
```

---

## Confronto con DeepEval

| Aspetto | Phoenix Eval | DeepEval |
|---------|-------------|----------|
| Libreria base | `arize-phoenix-evals` | `deepeval` |
| Metriche RAG | Faithfulness, Document Relevance | Contextual Recall/Precision/Relevancy |
| Metriche Safety | — | Toxicity, Bias |
| Metriche Agent | Tool selection/invocation/response | AgentEvaluator (end-to-end) |
| Custom | LLM-as-Judge, Code Evaluator | GEval (custom criteria) |
| Output | DataFrame | DeepEval TestResult |
| Integrazione UI | Nativa (Phoenix annotations) | Dashboard DeepEval separata |
| RAG Evaluators | — | CogneeRAG, QdrantRAG, PGVectorRAG |

Per la documentazione DeepEval vedi [DeepEval Toolkit](deep-eval.md).

---

## Dipendenze Python

```bash
uv pip install -e ".[phoenix]"
```

| Pacchetto | Ruolo |
|-----------|-------|
| `arize-phoenix-evals` | SDK evaluatori Phoenix |
| `arize-phoenix-otel` | `phoenix.otel.register()` per self-hosted |
| `openinference-instrumentation-langchain` | Auto-instrumentor LangChain |
| `opentelemetry-exporter-otlp` | Exporter OTLP per span |
