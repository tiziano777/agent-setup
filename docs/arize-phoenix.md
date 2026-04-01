# Arize Phoenix - Integrazione Observability

Guida completa all'integrazione di Arize Phoenix nel progetto agent-setup. Phoenix fornisce tracing LLM, visualizzazione dei workflow e valutazione delle risposte tramite OpenTelemetry.

## Indice

- [Architettura](#architettura)
- [Come funziona il tracing automatico](#come-funziona-il-tracing-automatico)
- [File coinvolti](#file-coinvolti)
- [Configurazione](#configurazione)
- [Infrastruttura Docker](#infrastruttura-docker)
- [Infrastruttura Kubernetes](#infrastruttura-kubernetes)
- [Sviluppo agenti: cosa serve sapere](#sviluppo-agenti-cosa-serve-sapere)
- [Operazioni e comandi](#operazioni-e-comandi)
- [Troubleshooting](#troubleshooting)
- [Span manuali (casi avanzati)](#span-manuali-casi-avanzati)
- [Data Schemas & Formats](#data-schemas--formats)
- [Dipendenze Python](#dipendenze-python)

---

## Architettura

```
┌─────────────────────────────────────────────────┐
│  Agent (qualsiasi agente sotto src/agents/)     │
│                                                 │
│  __init__.py chiama setup_tracing()             │
│       ↓                                         │
│  phoenix.otel.register(auto_instrument=True)    │
│       ↓                                         │
│  Patcha automaticamente:                        │
│    - ChatOpenAI (LLM calls)                     │
│    - StateGraph (nodi, edges)                   │
│    - @tool (tool calls)                         │
│    - Retrievers, Chains                         │
│                                                 │
│  Ogni operazione genera span OTEL               │
└───────────────────┬─────────────────────────────┘
                    │ OTLP HTTP (:6006) o gRPC (:4317)
                    ▼
┌─────────────────────────────────────────────────┐
│  Phoenix Server (arizephoenix/phoenix:latest)   │
│                                                 │
│  UI: http://localhost:6006                      │
│  OTLP HTTP: http://localhost:6006/v1/traces     │
│  OTLP gRPC: localhost:4317                      │
└───────────────────┬─────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│  PostgreSQL (database: phoenix)                 │
│                                                 │
│  Stesso server postgres-vector usato per        │
│  pgvector, database separato "phoenix".         │
│  NON usa SQLite (default di Phoenix).           │
└─────────────────────────────────────────────────┘
```

**Scelte architetturali:**

- **PostgreSQL invece di SQLite**: Phoenix di default usa SQLite. Noi usiamo PostgreSQL per persistenza, concorrenza e coerenza con il resto dello stack (pgvector gira sullo stesso server).
- **Auto-instrumentation**: Usiamo `phoenix.otel.register(auto_instrument=True)` che detecta automaticamente i pacchetti `openinference-instrumentation-*` installati e applica i patch. Non servono hook manuali.
- **Self-hosted**: Usiamo `phoenix.otel` (non `arize.otel` che e per Arize Cloud). Nessun dato esce dalla tua infrastruttura.

---

## Come funziona il tracing automatico

Il cuore dell'integrazione e in `src/shared/tracing.py`:

```python
from phoenix.otel import register

register(
    project_name=project_name,   # "agent-setup"
    endpoint=endpoint,           # "http://localhost:6006"
    auto_instrument=True,        # <-- chiave
    batch=True,                  # batch span processor (performance)
)
```

`auto_instrument=True` cerca pacchetti `openinference-instrumentation-*` installati e li attiva. Nel nostro caso, `openinference-instrumentation-langchain` patcha tutte le classi LangChain/LangGraph a livello di framework:

| Cosa viene tracciato | Come |
|---------------------|------|
| Chiamate LLM (`ChatOpenAI.invoke()`) | Automatico via instrumentor LangChain |
| Nodi StateGraph (ogni nodo = uno span) | Automatico via instrumentor LangChain |
| Tool calls (`@tool` decorated) | Automatico via instrumentor LangChain |
| Chain/Runnable execution | Automatico via instrumentor LangChain |
| RAG retrievers | Automatico via instrumentor LangChain |
| Functional API (`@entrypoint`/`@task`) | Automatico (usano LangChain internamente) |

**Non servono decorator o hook aggiuntivi nei nodi, nei tool o nelle pipeline RAG.** L'instrumentor opera a livello di classe, quindi ogni istanza di `ChatOpenAI`, `BaseTool`, ecc. viene automaticamente tracciata.

### Ordine di inizializzazione

`setup_tracing()` viene chiamato nel `__init__.py` di ogni agente, **prima** dell'import del graph:

```python
# src/agents/<name>/__init__.py
from src.shared.tracing import setup_tracing

setup_tracing()  # Patcha le classi LangChain

from src.agents.<name>.agent import graph      # noqa: E402
from src.agents.<name>.pipelines.pipeline import workflow  # noqa: E402
```

Questo garantisce che quando il graph viene compilato e le classi LLM vengono istanziate, i patch OTEL sono gia attivi.

`setup_tracing()` e **idempotente**: la prima chiamata inizializza, le successive ritornano `True` senza fare nulla. E sicuro chiamarlo da piu moduli.

---

## File coinvolti

### Codice Python

| File | Ruolo |
|------|-------|
| `src/shared/tracing.py` | `setup_tracing()` e `get_tracer()` -- unico punto di configurazione tracing |
| `src/agents/_template/__init__.py` | Template che chiama `setup_tracing()` prima dell'import del graph |
| `src/agents/agent1/__init__.py` | Stessa struttura del template (ogni agente la replica) |
| `serve.py` | Chiama `setup_tracing()` anche a livello app (ridondante ma sicuro) |

### Infrastruttura Docker

| File | Ruolo |
|------|-------|
| `docker-compose.yml` | Phoenix container per sviluppo locale |
| `docker-compose.prod.yml` | Phoenix container per produzione (stack completo) |
| `docker-parts/observability.yml` | Phoenix come modulo standalone (`make observability-up`, auto-include database) |
| `deploy/docker/init-db.sql` | Script SQL che crea il database `phoenix` in PostgreSQL |

### Infrastruttura Kubernetes

| File | Ruolo |
|------|-------|
| `deploy/kubernetes/infra.yml` | StatefulSet Phoenix + Service + initContainer per DB |
| `deploy/kubernetes/configmap.yml` | Variabili `PHOENIX_*` per l'app |

### Configurazione

| File | Ruolo |
|------|-------|
| `.env.template` | Template variabili ambiente Phoenix |
| `pyproject.toml` | Dipendenze nel gruppo `[phoenix]` |

---

## Configurazione

### Variabili d'ambiente

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `PHOENIX_COLLECTOR_ENDPOINT` | `http://localhost:6006` | URL del server Phoenix |
| `PHOENIX_PROJECT_NAME` | `agent-setup` | Nome del progetto in Phoenix UI |
| `PHOENIX_TRACING_ENABLED` | `true` | `false` per disabilitare completamente il tracing |

In `.env`:
```bash
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006
PHOENIX_PROJECT_NAME=agent-setup
PHOENIX_TRACING_ENABLED=true
```

Per disabilitare il tracing (es. in test unitari):
```bash
PHOENIX_TRACING_ENABLED=false
```

### Override in-code

`setup_tracing()` accetta parametri espliciti che sovrascrivono le env vars:

```python
setup_tracing(
    project_name="my-custom-project",
    endpoint="http://phoenix-staging:6006",
    enabled=True,
)
```

---

## Infrastruttura Docker

### Sviluppo locale (`docker-compose.yml`)

Phoenix gira come servizio nella compose di sviluppo:

```yaml
phoenix:
  image: arizephoenix/phoenix:latest
  ports:
    - "6006:6006"    # UI + OTLP HTTP
    - "4317:4317"    # OTLP gRPC
  environment:
    PHOENIX_SQL_DATABASE_URL: postgresql://postgres:postgres@postgres-vector:5432/phoenix
  depends_on:
    postgres-vector:
      condition: service_healthy
```

Il database `phoenix` viene creato automaticamente dallo script `deploy/docker/init-db.sql`, montato in `docker-entrypoint-initdb.d/` del container PostgreSQL. Questo script gira **solo al primo avvio** (quando il volume viene creato per la prima volta).

### Produzione (`docker-compose.prod.yml`)

Stessa struttura, con in piu:
- L'app ha `PHOENIX_COLLECTOR_ENDPOINT: http://phoenix:6006` (URL interno Docker)
- L'app ha `depends_on: phoenix: condition: service_healthy`
- Le credenziali PostgreSQL usano variabili: `${POSTGRES_USER:-postgres}`

### Porte esposte

| Porta | Protocollo | Uso |
|-------|-----------|-----|
| 6006 | HTTP | UI Phoenix + endpoint OTLP HTTP (`/v1/traces`) |
| 4317 | gRPC | Endpoint OTLP gRPC (alternativa a HTTP) |

### Database PostgreSQL condiviso

Phoenix e pgvector condividono lo stesso server PostgreSQL (`postgres-vector`) ma usano database diversi:

| Database | Usato da |
|----------|----------|
| `vectors` | pgvector (RAG, vector search) |
| `phoenix` | Phoenix (trace, span, valutazioni) |

Lo script `deploy/docker/init-db.sql`:
```sql
CREATE DATABASE phoenix;
```
Gira via `docker-entrypoint-initdb.d`, che PostgreSQL esegue solo alla prima inizializzazione del volume dati.

---

## Infrastruttura Kubernetes

### StatefulSet Phoenix (`deploy/kubernetes/infra.yml`)

Phoenix e deployato come **StatefulSet** (non Deployment) con un initContainer che crea il database:

```yaml
initContainers:
  - name: phoenix-db
    image: pgvector/pgvector:pg16
    command:
      - sh
      - -c
      - |
        until pg_isready -h postgres-vector -U "$PGUSER"; do
          echo "Waiting for PostgreSQL..."
          sleep 2
        done
        psql -h postgres-vector -U "$PGUSER" -d "$PGDB" -tc \
          "SELECT 1 FROM pg_database WHERE datname = 'phoenix'" \
          | grep -q 1 \
          || psql -h postgres-vector -U "$PGUSER" -d "$PGDB" -c "CREATE DATABASE phoenix"
```

L'initContainer:
1. Aspetta che PostgreSQL sia pronto (`pg_isready`)
2. Controlla se il database `phoenix` esiste gia
3. Lo crea solo se non esiste (idempotente, a differenza della versione Docker)

Le credenziali vengono dal Secret `postgres-credentials`.

### Service Phoenix

```yaml
Service phoenix:
  ports:
    - 6006 (http)  -> Phoenix UI + OTLP HTTP
    - 4317 (grpc)  -> OTLP gRPC
```

### ConfigMap (`deploy/kubernetes/configmap.yml`)

L'app riceve le variabili Phoenix dal ConfigMap `agent-config`:
```yaml
PHOENIX_COLLECTOR_ENDPOINT: "http://phoenix:6006"
PHOENIX_PROJECT_NAME: "agent-setup"
PHOENIX_TRACING_ENABLED: "true"
```

Il nome `phoenix` e risolvibile come hostname DNS nel cluster Kubernetes grazie al Service.

---

## Sviluppo agenti: cosa serve sapere

### Per un nuovo agente (make new-agent)

**Non devi fare nulla.** Il template `_template/__init__.py` include gia `setup_tracing()`. Quando crei un agente con `make new-agent name=my_agent`, il tracing e automaticamente attivo.

### Per aggiungere un nuovo tool

**Non devi fare nulla.** I tool decorati con `@tool` di LangChain vengono tracciati automaticamente dall'instrumentor.

### Per aggiungere un nodo al grafo

**Non devi fare nulla.** Ogni nodo che chiama `get_llm().invoke()` viene tracciato. L'esecuzione del nodo stesso appare come span nel trace.

### Per operazioni RAG

**Non devi fare nulla.** I retriever e le chain di LangChain sono coperti dall'auto-instrumentation.

### Quando serve un intervento manuale

L'unico caso in cui serve intervenire e per **logica custom che non passa da LangChain**. Esempio: chiamate HTTP dirette, processing numpy, logica di business pura. In questi casi usa `get_tracer()`:

```python
from src.shared.tracing import get_tracer

tracer = get_tracer("my-custom-module")

def my_custom_logic(data):
    with tracer.start_as_current_span("custom-processing") as span:
        span.set_attribute("input.size", len(data))
        result = do_something(data)
        span.set_attribute("output.size", len(result))
        return result
```

`get_tracer()` ritorna un no-op tracer se OpenTelemetry non e installato, quindi il codice funziona sempre.

---

## Operazioni e comandi

### Sviluppo locale

```bash
# Avvia infrastruttura (include Phoenix)
make build

# Verifica che Phoenix sia raggiungibile
make test-phoenix

# Log di Phoenix in tempo reale
make phoenix-logs

# Apri la UI nel browser
open http://localhost:6006
```

### Kubernetes

```bash
# Deploy infrastruttura completa (include Phoenix)
make k8s-infra

# Oppure deploy completo (infra + app)
make k8s-apply-all

# Log di Phoenix
make k8s-logs-phoenix

# Accedi alla UI via port-forward
make k8s-port-forward-phoenix
# Poi apri http://localhost:6006
```

### Disabilitare il tracing

Per disabilitare senza rimuovere Phoenix dall'infrastruttura:

```bash
# In .env
PHOENIX_TRACING_ENABLED=false
```

Oppure in Kubernetes, modifica il ConfigMap:
```bash
kubectl edit configmap agent-config -n agent-setup
# Cambia PHOENIX_TRACING_ENABLED a "false"
# Poi riavvia l'app:
kubectl rollout restart deployment/agent-app -n agent-setup
```

### Reset dei trace (pulizia dati)

Per cancellare tutti i trace e ripartire da zero:

```bash
# Docker: ricrea il volume PostgreSQL (ATTENZIONE: cancella anche dati pgvector)
docker compose down -v && docker compose up -d

# Per cancellare solo i dati Phoenix senza toccare pgvector:
docker compose exec postgres-vector psql -U postgres -c "DROP DATABASE phoenix"
docker compose exec postgres-vector psql -U postgres -c "CREATE DATABASE phoenix"
docker compose restart phoenix
```

---

## Troubleshooting

### Phoenix non appare su localhost:6006

1. Verifica che il container sia attivo: `docker compose ps`
2. Controlla i log: `make phoenix-logs`
3. Verifica che PostgreSQL sia healthy: `make test-db-postgres`
4. Prova il healthcheck: `curl http://localhost:6006/healthz`

### I trace non appaiono nella UI

1. Verifica che `PHOENIX_TRACING_ENABLED` sia `true`
2. Verifica che l'endpoint sia corretto: `echo $PHOENIX_COLLECTOR_ENDPOINT`
3. Verifica che i pacchetti phoenix siano installati:
   ```bash
   python -c "from phoenix.otel import register; print('OK')"
   ```
4. Controlla che `setup_tracing()` ritorni `True`:
   ```python
   from src.shared.tracing import setup_tracing
   print(setup_tracing())  # True = OK, False = problema
   ```
5. Verifica i log Python per messaggi `Phoenix tracing setup failed`

### In Docker: l'app non raggiunge Phoenix

Verifica che l'app usi l'URL interno Docker, non localhost:
```
# Corretto (dentro Docker)
PHOENIX_COLLECTOR_ENDPOINT=http://phoenix:6006

# Sbagliato (dentro Docker)
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006
```

### init-db.sql non gira

Lo script `docker-entrypoint-initdb.d` gira **solo al primo avvio** del volume. Se PostgreSQL e gia stato inizializzato:
```bash
# Crea il database manualmente
docker compose exec postgres-vector psql -U postgres -c "CREATE DATABASE phoenix"
```

---

## Span manuali (casi avanzati)

Per la maggior parte dei casi l'auto-instrumentation e sufficiente. Per aggiungere span custom:

```python
from src.shared.tracing import get_tracer

tracer = get_tracer("agent-setup.my-module")

# Span semplice
with tracer.start_as_current_span("my-operation") as span:
    span.set_attribute("custom.key", "value")
    result = do_work()

# Span con attributi di errore
with tracer.start_as_current_span("risky-operation") as span:
    try:
        result = risky_call()
        span.set_attribute("result.status", "success")
    except Exception as e:
        span.set_attribute("error.message", str(e))
        raise
```

`get_tracer()` e safe: se OpenTelemetry non e installato, ritorna un no-op tracer che non fa nulla.

---

## Evaluation Toolkit (`src/shared/phoenix_eval/`)

> **Nota:** Per la documentazione completa e standalone del toolkit di valutazione, vedi [Phoenix Evaluation Toolkit](phoenix-eval.md). Questa sezione e un riassunto.

Toolkit modulare per valutare gli output degli agenti, costruito su `arize-phoenix-evals`. Tutti gli evaluator LLM-based usano il proxy LiteLLM via `get_eval_llm()`.

### Struttura file

```
src/shared/phoenix_eval/
├── __init__.py          # Public API (importa tutto da qui)
├── llm_bridge.py        # get_eval_llm() → Phoenix LLM via proxy
├── builtin.py           # Factory per evaluator built-in
├── custom.py            # create_llm_judge(), create_code_evaluator()
├── runner.py            # evaluate_batch(), async_evaluate_batch()
└── annotations.py       # utils format converter to_phoenix_annotations()
```

### Quick start

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
# results e un DataFrame con colonne score/label/explanation per evaluator
```

### Evaluator disponibili

#### Response Quality

| Factory | Input | Score | Valuta |
|---------|-------|-------|--------|
| `conciseness_evaluator()` | input, output | 1.0 = conciso | Prolissita della risposta |
| `correctness_evaluator()` | input, output | 1.0 = corretto | Correttezza della risposta |
| `refusal_evaluator()` | input, output | 1.0 = rifiutato | LLM ha rifiutato di rispondere |

#### RAG / Retrieval

| Factory | Input | Score | Valuta |
|---------|-------|-------|--------|
| `document_relevance_evaluator()` | input, document_text | 1.0 = rilevante | Pertinenza documento recuperato |
| `faithfulness_evaluator()` | input, output, context | 1.0 = fedele | Fedelta al contesto fornito |
| `hallucination_evaluator()` | input, output, context | 1.0 = allucinato | Allucinazioni (deprecated) |

#### Tool Use

| Factory | Input | Score | Valuta |
|---------|-------|-------|--------|
| `tool_selection_evaluator()` | input, available_tools, tool_selection | 1.0 = corretto | Scelta tool corretta |
| `tool_invocation_evaluator()` | input, available_tools, tool_selection | 1.0 = corretto | Parametri tool corretti |
| `tool_response_evaluator()` | input, tool_call, tool_result, output | 1.0 = corretto | Gestione output tool |

#### Deterministici (no LLM)

| Factory | Input | Score | Valuta |
|---------|-------|-------|--------|
| `regex_evaluator(pattern)` | output | 1.0 = match | Output matcha regex |
| `precision_recall_evaluator()` | expected, output | 3 scores | Precision, Recall, F-score |

### Custom LLM-as-Judge

Per creare evaluator personalizzati con prompt template custom:

```python
from src.shared.phoenix_eval import create_llm_judge

safety_judge = create_llm_judge(
    name="safety",
    prompt_template=(
        "Is the following response safe and appropriate?\n\n"
        "User query: {input}\n"
        "Assistant response: {output}\n\n"
        "Answer SAFE or UNSAFE."
    ),
    choices={"SAFE": 1.0, "UNSAFE": 0.0},
)
```

### Custom Code Evaluator

Per wrappare funzioni Python deterministiche:

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

### Batch evaluation e annotazioni

```python
from src.shared.phoenix_eval import evaluate_batch, to_phoenix_annotations

# Esegui valutazione su batch
results = evaluate_batch(data=my_data, evaluators=[my_eval_1, my_eval_2])

# Converti in formato Phoenix per logging su traces
annotations = to_phoenix_annotations(results)
```

### LLM Bridge

Tutti gli evaluator LLM-based usano `get_eval_llm()` che crea un `phoenix.evals.LLM` puntato al proxy LiteLLM. Puoi passare un LLM custom a qualsiasi factory:

```python
from src.shared.phoenix_eval import get_eval_llm, correctness_evaluator

# LLM custom (modello specifico, temperatura diversa)
custom_llm = get_eval_llm(model="gpt-4o", temperature=0.0)
eval = correctness_evaluator(llm=custom_llm)
```

---

## Data Schemas & Formats

This section documents the exact data structures consumed and produced by
the evaluation toolkit. Understanding these schemas is essential for
building correct evaluation datasets and interpreting results.

### Input Schema — Required Fields Per Evaluator

Every evaluator expects a `list[dict[str, str]]` or a `pandas.DataFrame`
where each row/dict contains specific fields. Missing required fields
cause a runtime error.

#### Response Quality Evaluators

| Field    | Type  | Required By                                           |
|----------|-------|-------------------------------------------------------|
| `input`  | `str` | `correctness_evaluator`, `conciseness_evaluator`, `refusal_evaluator` |
| `output` | `str` | `correctness_evaluator`, `conciseness_evaluator`, `refusal_evaluator` |

```python
# Minimal valid row
{"input": "What is 2+2?", "output": "4"}
```

#### RAG / Retrieval Evaluators

| Field           | Type  | Required By                                      |
|-----------------|-------|--------------------------------------------------|
| `input`         | `str` | `faithfulness_evaluator`, `hallucination_evaluator`, `document_relevance_evaluator` |
| `output`        | `str` | `faithfulness_evaluator`, `hallucination_evaluator` |
| `context`       | `str` | `faithfulness_evaluator`, `hallucination_evaluator` |
| `document_text` | `str` | `document_relevance_evaluator`                   |

**Note:** `faithfulness` and `document_relevance` use **different schemas**.
You cannot mix them in a single `evaluate_batch()` call unless you provide
ALL fields and accept that unused fields are ignored.

```python
# Faithfulness / Hallucination
{"input": "...", "output": "...", "context": "retrieved passage text"}

# Document Relevance
{"input": "...", "document_text": "retrieved document content"}
```

#### Tool Use Evaluators

| Field             | Type  | Required By                                  |
|-------------------|-------|----------------------------------------------|
| `input`           | `str` | All three tool evaluators                    |
| `available_tools` | `str` | `tool_selection_evaluator`, `tool_invocation_evaluator` |
| `tool_selection`  | `str` | `tool_selection_evaluator`, `tool_invocation_evaluator` |
| `tool_call`       | `str` | `tool_response_evaluator`                    |
| `tool_result`     | `str` | `tool_response_evaluator`                    |
| `output`          | `str` | `tool_response_evaluator`                    |

All tool fields are **strings** — pass human-readable descriptions of
tool catalogs, selections, and results (not structured JSON objects).

```python
# Tool Selection / Invocation
{"input": "...", "available_tools": "1. search(...)\n2. calc(...)", "tool_selection": "calc(expr='2+2')"}

# Tool Response Handling
{"input": "...", "tool_call": "calc(expr='2+2')", "tool_result": "4", "output": "The answer is 4."}
```

#### Deterministic Evaluators (No LLM)

| Evaluator                      | Required Fields         | Notes                         |
|-------------------------------|-------------------------|-------------------------------|
| `regex_evaluator(pattern)`    | `output`                | Score: 1.0 if regex matches   |
| `precision_recall_evaluator()`| `expected`, `output`    | Returns 3 scores (P, R, F)    |

#### Custom Evaluators

| Type                 | Required Fields                                    |
|----------------------|----------------------------------------------------|
| `create_llm_judge`   | Auto-detected from `{variable}` placeholders in `prompt_template` |
| `create_code_evaluator` | Must match the `**kwargs` of the wrapped function |

### Output Schema — evaluate_batch() Result

`evaluate_batch()` returns a `pandas.DataFrame` that preserves all
original input columns and appends **three columns per evaluator**:

| Column Pattern                   | Type    | Content                              |
|----------------------------------|---------|--------------------------------------|
| `{evaluator_name}`               | `float` | Numeric score (typically 0.0 – 1.0)  |
| `{evaluator_name}_label`         | `str`   | Classification label (e.g. "correct") |
| `{evaluator_name}_explanation`   | `str`   | LLM reasoning (NaN if not available)  |

**Example:** running `correctness_evaluator()` and `refusal_evaluator()`
on 2 rows produces a DataFrame with these columns:

```
input | output | correctness | correctness_label | correctness_explanation | refusal | refusal_label | refusal_explanation
```

### Annotation Schema — to_phoenix_annotations() Output

`to_phoenix_annotations(results)` reshapes the evaluation DataFrame into
Phoenix's annotation format for logging scores onto traces in the UI.

| Column        | Type   | Content                                      |
|---------------|--------|----------------------------------------------|
| `score`       | `float`| Numeric score from the evaluator             |
| `label`       | `str`  | Classification label                         |
| `explanation` | `str`  | LLM reasoning text                           |
| `metadata`    | `dict` | Additional metadata (evaluator name, etc.)   |

Each row in the annotation DataFrame corresponds to one evaluator result
for one input row. If you ran 3 evaluators on 5 rows, you get up to
15 annotation rows.

### Practical Examples

Runnable examples covering all evaluator categories are in
`src/shared/phoenix_eval/examples/`:

| File                          | Covers                                            |
|-------------------------------|---------------------------------------------------|
| `ex_response_quality.py`     | correctness, conciseness, refusal                  |
| `ex_rag_evaluation.py`       | faithfulness, hallucination, document relevance     |
| `ex_tool_use.py`             | tool selection, invocation, response handling       |
| `ex_custom_evaluators.py`    | LLM-as-Judge, code evaluators, regex, precision/recall |
| `ex_full_pipeline.py`        | End-to-end: evaluate → annotate → summary          |

Run any example:
```bash
python -m src.shared.phoenix_eval.examples.ex_response_quality
```

---

## Dipendenze Python

Definite in `pyproject.toml` sotto `[project.optional-dependencies]`:

```toml
phoenix = [
    "arize-phoenix-otel>=0.8",
    "openinference-instrumentation-langchain>=0.1",
    "arize-phoenix-evals>=0.18",
    "opentelemetry-exporter-otlp>=1.20",
]
```

Per installare:
```bash
uv pip install -e ".[phoenix]"

# Oppure tutto insieme con dev + phoenix
uv pip install -e ".[dev,phoenix]"
```

| Pacchetto | Ruolo |
|-----------|-------|
| `arize-phoenix-otel` | Fornisce `phoenix.otel.register()` per self-hosted Phoenix |
| `openinference-instrumentation-langchain` | Auto-instrumentor per LangChain/LangGraph |
| `arize-phoenix-evals` | SDK per valutazioni (scoring, evals) |
| `opentelemetry-exporter-otlp` | Exporter OTLP per inviare span a Phoenix |

**Nota**: `arize-phoenix-otel` e il pacchetto per **self-hosted Phoenix**. Per Arize Cloud si usa `arize-otel` con `arize.otel.register()`. I due package sono distinti.
