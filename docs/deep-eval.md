# DeepEval Toolkit

Toolkit estensibile per la valutazione di agenti LLM, pipeline RAG e workflow LangGraph. Costruito su `deepeval`, tutte le chiamate LLM passano per il proxy LiteLLM via `LiteLLMModel`.

## Indice

- [Architettura](#architettura)
- [File del modulo](#file-del-modulo)
- [Configurazione](#configurazione)
- [Quick Start](#quick-start)
- [Metriche disponibili](#metriche-disponibili)
- [RAG Evaluators](#rag-evaluators)
- [Agent Evaluation](#agent-evaluation)
- [BaseDeepEvaluator](#basedeepEvaluator)
- [Test Cases](#test-cases)
- [Runner](#runner)
- [Confronto con Phoenix Evals](#confronto-con-phoenix-evals)
- [Variabili d'ambiente](#variabili-dambiente)
- [Dipendenze Python](#dipendenze-python)

---

## Architettura

```
┌──────────────────────────────────────────────┐
│  Agent output / RAG pipeline / LangGraph     │
└───────────────────┬──────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────┐
│  deep_eval/                                  │
│                                              │
│  metrics.py        ← 10 metriche factory     │
│  rag_evaluators.py ← Cognee/Qdrant/PGVector  │
│  agent_evaluators.py ← AgentEvaluator        │
│  base.py           ← BaseDeepEvaluator ABC   │
│  runner.py         ← evaluate() / dataset    │
│  test_cases.py     ← helper creazione TC     │
│  llm_bridge.py     ← get_deepeval_model()    │
│  config.py         ← DeepEvalSettings        │
└───────────────────┬──────────────────────────┘
                    │
                    ▼
              LiteLLM Proxy (:4000)
              via LiteLLMModel("openai/{model}")
```

**Scelte architetturali:**

- **LLM via proxy**: `get_deepeval_model()` crea un `LiteLLMModel` con prefisso `openai/` per instradare tutte le chiamate metriche tramite il proxy.
- **BaseDeepEvaluator ABC**: Classe astratta per creare evaluator custom con `_setup_metrics()` + `create_test_case()`.
- **RAG Evaluators dedicati**: Evaluator specializzati per Cognee (KG), Qdrant e PGVector con `retrieve_context()` integrato.
- **Schema isolation PGVector**: `PGVectorRAGEvaluator` usa lo schema `deepeval` (env var `PGVECTOR_SCHEMA_DEEPEVAL`) per isolamento dati.

---

## File del modulo

```
src/shared/deep_eval/
├── __init__.py           # Public API con lazy re-exports
├── config.py             # DeepEvalSettings + configure_deepeval()
├── llm_bridge.py         # get_deepeval_model() → LiteLLMModel via proxy
├── base.py               # BaseDeepEvaluator ABC
├── metrics.py            # 10 factory functions per metriche
├── rag_evaluators.py     # CogneeRAGEvaluator, QdrantRAGEvaluator, PGVectorRAGEvaluator
├── agent_evaluators.py   # AgentEvaluator + evaluate_langgraph_agent()
├── runner.py             # evaluate() / evaluate_dataset()
├── test_cases.py         # Helper per creazione test case
└── examples/             # 7 esempi eseguibili
    ├── ex_agent_evaluation.py
    ├── ex_custom_metrics.py
    ├── ex_full_pipeline.py
    ├── ex_rag_cognee.py
    ├── ex_rag_pgvector.py
    ├── ex_rag_qdrant.py
    └── ex_tool_evaluation.py
```

---

## Configurazione

### `DeepEvalSettings`

```python
from src.shared.deep_eval import DeepEvalSettings

settings = DeepEvalSettings(
    model="llm",                          # modello nel proxy
    base_url="http://localhost:4000/v1",
    threshold=0.5,                        # soglia pass/fail
    pgvector_schema="deepeval",           # schema PostgreSQL isolato
)
```

| Campo | Default | Env Var | Descrizione |
|-------|---------|---------|-------------|
| `model` | `"llm"` | `DEFAULT_MODEL` | Modello nel proxy |
| `base_url` | `http://localhost:4000/v1` | `LITELLM_BASE_URL` | URL proxy LiteLLM |
| `threshold` | `0.5` | — | Soglia pass/fail per le metriche |
| `pgvector_schema` | `"deepeval"` | `PGVECTOR_SCHEMA_DEEPEVAL` | Schema PostgreSQL per RAG evaluator |

### `configure_deepeval()`

```python
from src.shared.deep_eval.config import configure_deepeval

configure_deepeval()  # auto-config da env vars
```

---

## Quick Start

```python
from src.shared.deep_eval import (
    answer_relevancy_metric,
    faithfulness_metric,
    evaluate,
    create_test_case,
)

tc = create_test_case(
    input="What is Python?",
    actual_output="A programming language.",
    retrieval_context=["Python is a programming language created by ..."],
)

evaluate([tc], metrics=[answer_relevancy_metric(), faithfulness_metric()])
```

---

## Metriche disponibili

### Response Quality

| Factory | Campi richiesti | Score | Valuta |
|---------|----------------|-------|--------|
| `answer_relevancy_metric()` | `input`, `actual_output` | 0.0–1.0 | Pertinenza della risposta |
| `hallucination_metric()` | `input`, `actual_output`, `context` | 0.0–1.0 | Allucinazioni |
| `faithfulness_metric()` | `input`, `actual_output`, `retrieval_context` | 0.0–1.0 | Fedelta al contesto |

### RAG / Contextual

| Factory | Campi richiesti | Score | Valuta |
|---------|----------------|-------|--------|
| `contextual_recall_metric()` | `input`, `actual_output`, `expected_output`, `retrieval_context` | 0.0–1.0 | Recall dei chunk recuperati |
| `contextual_precision_metric()` | `input`, `actual_output`, `expected_output`, `retrieval_context` | 0.0–1.0 | Precisione dei chunk recuperati |
| `contextual_relevancy_metric()` | `input`, `actual_output`, `retrieval_context` | 0.0–1.0 | Rilevanza del contesto |

### Safety

| Factory | Campi richiesti | Score | Valuta |
|---------|----------------|-------|--------|
| `toxicity_metric()` | `input`, `actual_output` | 0.0–1.0 | Contenuti tossici |
| `bias_metric()` | `input`, `actual_output` | 0.0–1.0 | Bias e stereotipi |

### Agent / Custom

| Factory | Campi richiesti | Score | Valuta |
|---------|----------------|-------|--------|
| `task_completion_metric()` | `input`, `actual_output`, `expected_output` | 0.0–1.0 | Completamento del task |
| `geval_metric(name, criteria)` | custom | 0.0–1.0 | Metrica custom con criteri liberi |

Ogni factory accetta parametri `model` e `threshold` opzionali:

```python
metric = answer_relevancy_metric(threshold=0.7)
```

---

## RAG Evaluators

Evaluator specializzati con `retrieve_context()` integrato per i vector store del progetto.

### CogneeRAGEvaluator

```python
from src.shared.deep_eval import CogneeRAGEvaluator

evaluator = CogneeRAGEvaluator(search_type=CogneeSearchType.GRAPH_COMPLETION)
context = await evaluator.retrieve_context("What is LangGraph?")
results = evaluator.evaluate(
    input="What is LangGraph?",
    actual_output="LangGraph is a framework for...",
    retrieval_context=context,
)
```

### QdrantRAGEvaluator

```python
from src.shared.deep_eval import QdrantRAGEvaluator

evaluator = QdrantRAGEvaluator(collection_name="my_docs", top_k=3)
context = evaluator.retrieve_context("What is LangGraph?")
```

### PGVectorRAGEvaluator

```python
from src.shared.deep_eval import PGVectorRAGEvaluator

evaluator = PGVectorRAGEvaluator(
    table_name="documents",
    top_k=3,
    schema="deepeval",  # default da env var PGVECTOR_SCHEMA_DEEPEVAL
)
context = evaluator.retrieve_context("What is LangGraph?")
```

Tutti e tre gli evaluator pre-configurano le metriche contestuali: `ContextualRecall`, `ContextualPrecision`, `ContextualRelevancy`.

---

## Agent Evaluation

### AgentEvaluator

Evaluator end-to-end per LangGraph agents:

```python
from src.shared.deep_eval import AgentEvaluator

evaluator = AgentEvaluator(graph=compiled_graph)
result = evaluator.evaluate(
    input="What is the capital of France?",
    expected_output="Paris",
)
```

### `evaluate_langgraph_agent()`

Convenience function per valutazione rapida:

```python
from src.shared.deep_eval import evaluate_langgraph_agent

results = evaluate_langgraph_agent(
    graph=compiled_graph,
    test_data=[
        {"input": "What is 2+2?", "expected_output": "4"},
        {"input": "Capital of Italy?", "expected_output": "Rome"},
    ],
)
```

---

## BaseDeepEvaluator

Classe astratta per creare evaluator custom:

```python
from src.shared.deep_eval.base import BaseDeepEvaluator

class MyEvaluator(BaseDeepEvaluator):
    def _setup_metrics(self, **kwargs):
        from deepeval.metrics import AnswerRelevancyMetric
        self._metrics = [AnswerRelevancyMetric(model=self._model, threshold=self._threshold)]

    def create_test_case(self, **kwargs):
        from deepeval.test_case import LLMTestCase
        return LLMTestCase(
            input=kwargs["input"],
            actual_output=kwargs["actual_output"],
        )
```

---

## Test Cases

Helper per creare test case:

```python
from src.shared.deep_eval import create_test_case, create_rag_test_case

# Test case base
tc = create_test_case(input="...", actual_output="...")

# Test case RAG (con retrieval_context)
tc = create_rag_test_case(
    input="...",
    actual_output="...",
    retrieval_context=["chunk 1", "chunk 2"],
    expected_output="...",
)

# Batch da dizionari
from src.shared.deep_eval import create_test_cases_from_dicts
tcs = create_test_cases_from_dicts([
    {"input": "Q1", "actual_output": "A1"},
    {"input": "Q2", "actual_output": "A2"},
])
```

---

## Runner

```python
from src.shared.deep_eval import evaluate, evaluate_dataset

# Singolo batch
evaluate(test_cases=[tc1, tc2], metrics=[metric1, metric2])

# Da dataset
evaluate_dataset(dataset=my_deepeval_dataset, metrics=[metric1])
```

---

## Confronto con Phoenix Evals

| Aspetto | DeepEval | Phoenix Eval |
|---------|----------|-------------|
| Libreria base | `deepeval` | `arize-phoenix-evals` |
| Metriche RAG | Contextual Recall/Precision/Relevancy | Faithfulness, Document Relevance |
| Metriche Safety | Toxicity, Bias | — |
| Metriche Agent | AgentEvaluator (end-to-end) | Tool selection/invocation/response |
| Custom | GEval (custom criteria) | LLM-as-Judge, Code Evaluator |
| Output | DeepEval TestResult | DataFrame |
| RAG Evaluators | CogneeRAG, QdrantRAG, PGVectorRAG | — |
| Integrazione UI | Dashboard DeepEval | Nativa (Phoenix annotations) |

Per la documentazione Phoenix Eval vedi [Phoenix Evaluation Toolkit](phoenix-eval.md).

---

## Variabili d'ambiente

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `DEFAULT_MODEL` | `llm` | Modello LLM nel proxy |
| `LITELLM_BASE_URL` | `http://localhost:4000/v1` | URL proxy LiteLLM |
| `PGVECTOR_SCHEMA_DEEPEVAL` | `deepeval` | Schema PostgreSQL per PGVectorRAGEvaluator |

---

## Dipendenze Python

```bash
uv pip install -e ".[deepeval]"
```

| Pacchetto | Ruolo |
|-----------|-------|
| `deepeval` | Framework metriche LLM, test case, runner |
