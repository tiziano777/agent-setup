# Knowledge Graph Memory (Cognee)

Toolkit per knowledge graph memory basato su Cognee. Trasforma testo in grafi di conoscenza strutturati con entita, relazioni e ricerca semantica. Tutte le chiamate LLM passano per il proxy LiteLLM, usa PGVector (PostgreSQL) per i vettori e Neo4j per il grafo.

## Indice

- [Architettura](#architettura)
- [File del modulo](#file-del-modulo)
- [Configurazione](#configurazione)
- [Infrastruttura Docker](#infrastruttura-docker)
- [Quick Start](#quick-start)
- [CogneeMemory API](#cogneememory-api)
- [14 Tipi di ricerca](#14-tipi-di-ricerca)
- [LangGraph Tools](#langgraph-tools)
- [LangGraph Nodes](#langgraph-nodes)
- [Search Utilities](#search-utilities)
- [Variabili d'ambiente](#variabili-dambiente)
- [Dipendenze Python](#dipendenze-python)

---

## Architettura

```
┌──────────────────────────────────────────────┐
│  Agent (LangGraph StateGraph)                │
│                                              │
│  tools/ ──── get_cognee_tools()              │        │
└───────────────────┬──────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────┐
│  CogneeMemory                                │
│                                              │
│  add() → cognify() → search()                │
│  Lazy init: setup_cognee() on first use      │
└───┬───────────┬───────────────┬──────────────┘
    │           │               │
    ▼           ▼               ▼
 LiteLLM    PostgreSQL       Neo4j
 Proxy      PGVector         (grafo)
 :4000      :5433            :7687
```

**Scelte architetturali:**

- **LLM via proxy**: Cognee usa `provider: "openai"` + modello `openai/{model}` per instradare tutte le chiamate LLM tramite il LiteLLM proxy (`openai` e il format standard di LiteLLM). Nessuna API key Cognee necessaria.
- **PGVector (PostgreSQL)**: Stesso PostgreSQL dell'infrastruttura (porta 5433, database `vectors`). Cognee usa PGVector sia come vector DB che come relational DB per evitare errori `CREATE EXTENSION vector` su SQLite.
- **Neo4j dedicato**: Il graph database e esclusivo per Cognee. Browser UI su http://localhost:7474.
- **Embeddings locali**: `fastembed` con modello `BAAI/bge-small-en-v1.5` — nessuna API key necessaria per gli embedding.
- **Lazy init**: `setup_cognee()` e idempotente e viene chiamato automaticamente al primo uso di `CogneeMemory`.

---

## File del modulo

```
src/shared/cognee_toolkit/
├── __init__.py    # Public API, factory functions, lazy re-exports
├── config.py      # CogneeSettings dataclass + setup_cognee()
├── memory.py      # CogneeMemory: add/cognify/search/memify
├── tools.py       # @tool factories per LangGraph agents
├── nodes.py       # Node factories per StateGraph
└── search.py      # CogneeSearchType enum, search_with_fallback(), multi_search()
```

| File | Responsabilita |
|------|---------------|
| `config.py` | `CogneeSettings` dataclass con env vars, `setup_cognee()` per wiring infrastruttura |
| `memory.py` | `CogneeMemory` class: wrapper async/sync per add, cognify, search, memify |
| `tools.py` | `get_cognee_tools()`: 3 tool LangChain (add, search, cognify) |
| `nodes.py` | 4 node factories: add, search, cognify, enriched LLM (RAG-over-KG) |
| `search.py` | Enum 14 tipi di ricerca, preset (CONVERSATIONAL, FAST, CODE), utilities |

---

## Configurazione

### `CogneeSettings`

```python
from src.shared.cognee_toolkit import CogneeSettings

settings = CogneeSettings(
    llm_provider="openai",                # LiteLLM usa format OpenAI-compatible
    llm_model="llm",                      # modello nel proxy_config.yml
    llm_endpoint="http://localhost:4000/v1",
    vector_db_provider="pgvector",        # o "lancedb" come fallback locale
    vector_db_host="localhost",
    vector_db_port="5433",
    vector_db_name="vectors",
    vector_db_username="postgres",
    vector_db_password="postgres",
    graph_db_provider="neo4j",            # o "kuzu", "falkordb", "networkx"
    graph_db_url="bolt://localhost:7687",
    graph_db_username="neo4j",
    graph_db_password="password",
    default_dataset="main_dataset",
    default_search_type="GRAPH_COMPLETION",
    top_k=10,
)
```

| Campo | Default | Env Var | Descrizione |
|-------|---------|---------|-------------|
| `llm_provider` | `"openai"` | — | Provider LLM (format OpenAI via LiteLLM) |
| `llm_model` | `"llm"` | `DEFAULT_MODEL` | Nome modello nel proxy |
| `llm_endpoint` | `http://localhost:4000/v1` | `LITELLM_BASE_URL` | URL proxy LiteLLM |
| `llm_api_key` | `"not-needed"` | `OPENAI_API_KEY` | API key (il proxy gestisce le chiavi reali) |
| `vector_db_provider` | `"pgvector"` | — | Backend vettoriale (`"pgvector"` o `"lancedb"`) |
| `vector_db_host` | `"localhost"` | `COGNEE_VECTOR_DB_HOST` | Host PostgreSQL |
| `vector_db_port` | `"5433"` | `COGNEE_VECTOR_DB_PORT` | Porta PostgreSQL |
| `vector_db_name` | `"vectors"` | `COGNEE_VECTOR_DB_NAME` | Database PostgreSQL |
| `vector_db_username` | `"postgres"` | `COGNEE_VECTOR_DB_USERNAME` | Utente PostgreSQL |
| `vector_db_password` | `"postgres"` | `COGNEE_VECTOR_DB_PASSWORD` | Password PostgreSQL |
| `embedding_provider` | `"fastembed"` | `EMBEDDING_PROVIDER` | Provider embeddings (locale, no API) |
| `embedding_model` | `"BAAI/bge-small-en-v1.5"` | `EMBEDDING_MODEL` | Modello embeddings |
| `embedding_dimensions` | `384` | — | Dimensioni vettore embedding |
| `graph_db_provider` | `"neo4j"` | — | Backend grafo |
| `graph_db_url` | `bolt://localhost:7687` | `NEO4J_URL` | URL Neo4j |
| `graph_db_username` | `"neo4j"` | `NEO4J_USERNAME` | Utente Neo4j |
| `graph_db_password` | `"password"` | `NEO4J_PASSWORD` | Password Neo4j |

### `setup_cognee()`

Configura l'infrastruttura Cognee (idempotente). L'ordine delle operazioni e critico:

1. **LLM** → `set_llm_config()` con provider `openai` e modello `openai/{model}` verso il proxy LiteLLM
2. **Vector DB** → `set_vector_db_config()` con `vector_db_provider` e `vector_dataset_database_handler` impostati a `"pgvector"` — **deve precede** `system_root_directory()` perche quest'ultimo sovrascrive l'URL se vede `"lancedb"` (default Cognee)
3. **System root** → `system_root_directory()` imposta la directory dati locale (`.cognee_system/`)
4. **Relational DB** → `set_relational_db_config()` con `db_provider: "postgres"` sullo stesso PostgreSQL — **necessario** perche `SqlAlchemyAdapter.create_database()` esegue `CREATE EXTENSION vector` sulla connessione relazionale quando `vector_db_provider=="pgvector"`, e questo fallirebbe su SQLite
5. **Embeddings** → `fastembed` locale (nessuna API key necessaria)
6. **Graph DB** → `set_graph_db_config()` verso Neo4j

```python
from src.shared.cognee_toolkit import setup_cognee

setup_cognee()  # usa env vars
setup_cognee(settings=CogneeSettings(graph_db_provider="networkx"))  # override
```

---

## Infrastruttura Docker

### Sviluppo (`docker-compose.yml`)

Cognee usa PostgreSQL (PGVector) e Neo4j come servizi Docker:

```yaml
postgres:
  image: pgvector/pgvector:pg17
  ports:
    - "5433:5432"
  environment:
    POSTGRES_USER: postgres
    POSTGRES_PASSWORD: postgres

neo4j:
  image: neo4j:5-community
  ports:
    - "7474:7474"   # Browser UI
    - "7687:7687"   # Bolt protocol
  environment:
    NEO4J_AUTH: neo4j/password
```

> **Nota**: PostgreSQL e condiviso con il resto dell'infrastruttura (Phoenix, PGVector per retrieval). Il database `vectors` e usato da Cognee sia come vector store (PGVector) che come relational store.

> **Avvio modulare**: Per avviare solo i servizi necessari a Cognee, usa `make llm-up && make graphdb-up && make database-up` oppure `make modules-up m="llm graphdb database"`. Vedi `make help-modules` per la guida completa.

### Produzione (`docker-compose.prod.yml`)

Include Neo4j con APOC plugin, healthcheck, e limiti di memoria (1G).

### Kubernetes (`deploy/kubernetes/infra.yml`)

StatefulSet Neo4j con PVC 10Gi, health/readiness probe, Service con porte 7474/7687.

---

## Quick Start

### 1. Come classe Python

```python
from src.shared.cognee_toolkit import get_cognee_memory

memory = get_cognee_memory()

# Ingestione
await memory.add("LangGraph e un framework per grafi agentici")
await memory.add(["Usa StateGraph per definire i nodi", "I tool sono funzioni @tool"])

# Costruzione grafo di conoscenza
await memory.cognify()

# Ricerca
results = await memory.search("Come funziona LangGraph?")
for r in results:
    print(r)
```

### 2. Come LangGraph tools

```python
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from src.shared.llm import get_llm
from src.shared.cognee_toolkit import get_cognee_tools

tools = get_cognee_tools(session_id="user_123")
agent = create_react_agent(get_llm(), tools)

result = agent.invoke({"messages": [HumanMessage(content="Cosa sai di LangGraph?")]})
```

### 3. Come nodo LangGraph (RAG-over-KG)

```python
from langgraph.graph import END, START, StateGraph
from src.shared.types import BaseAgentState
from src.shared.cognee_toolkit import create_cognee_enriched_llm_node

builder = StateGraph(BaseAgentState)
builder.add_node("process", create_cognee_enriched_llm_node(
    search_type="GRAPH_COMPLETION",
    session_id="researcher",
))
builder.add_edge(START, "process")
builder.add_edge("process", END)

graph = builder.compile()
```

---

## CogneeMemory API

```python
class CogneeMemory:
    async def add(data: str | list[str], dataset_name: str = None) -> None
    async def cognify(datasets: str | list[str] = None) -> Any
    async def search(query: str, search_type: str = "GRAPH_COMPLETION",
                     top_k: int = None, session_id: str = None,
                     datasets: str | list[str] = None, only_context: bool = False) -> list
    async def memify(dataset: str = None, **kwargs) -> Any
    async def add_and_cognify(data: str | list[str], dataset_name: str = None) -> Any
```

Wrapper sincroni disponibili per ogni metodo: `add_sync()`, `cognify_sync()`, `search_sync()`, `add_and_cognify_sync()`.

---

## 14 Tipi di ricerca

```python
from src.shared.cognee_toolkit import CogneeSearchType
```

| Tipo | Descrizione |
|------|-------------|
| `SUMMARIES` | Riassunti dei documenti ingestiti |
| `CHUNKS` | Chunk di testo dai documenti originali |
| `CHUNKS_LEXICAL` | Ricerca lessicale (keyword-based) sui chunk |
| `RAG_COMPLETION` | Retrieval + LLM completion classico |
| `TRIPLET_COMPLETION` | Completion basato su triple (soggetto-relazione-oggetto) |
| `GRAPH_COMPLETION` | **Default.** Completion arricchito dal grafo completo |
| `GRAPH_SUMMARY_COMPLETION` | Completion dal grafo + riassunti |
| `GRAPH_COMPLETION_COT` | Graph completion con chain-of-thought |
| `GRAPH_COMPLETION_CONTEXT_EXTENSION` | Graph completion con estensione del contesto |
| `CYPHER` | Query Cypher dirette su Neo4j |
| `NATURAL_LANGUAGE` | Traduzione automatica da linguaggio naturale a Cypher |
| `FEELING_LUCKY` | Ricerca veloce "a fortuna" |
| `TEMPORAL` | Ricerca con ordinamento temporale |
| `CODING_RULES` | Ottimizzato per regole e pattern di codice |

### Preset

```python
from src.shared.cognee_toolkit import CONVERSATIONAL_TYPES, FAST_TYPES, CODE_TYPES

CONVERSATIONAL_TYPES  # ["GRAPH_COMPLETION", "RAG_COMPLETION", "TRIPLET_COMPLETION"]
FAST_TYPES            # ["CHUNKS", "CHUNKS_LEXICAL", "SUMMARIES"]
CODE_TYPES            # ["CODING_RULES", "CHUNKS"]
```

---

## LangGraph Tools

`get_cognee_tools()` ritorna 3 tool:

| Tool | Descrizione |
|------|-------------|
| `cognee_add` | Ingestisce testo nel knowledge graph (add + cognify automatico) |
| `cognee_search` | Cerca nel knowledge graph con `GRAPH_COMPLETION` |
| `cognee_cognify` | Costruisce/aggiorna il knowledge graph da un dataset |

`get_cognee_memory_tools()` ritorna solo `(cognee_add, cognee_search)` per un pattern conversazionale minimale.

---

## Search Utilities

### `search_with_fallback()`

Cerca con fallback automatico se il tipo primario non ritorna risultati:

```python
from src.shared.cognee_toolkit import search_with_fallback

results = await search_with_fallback(
    "Come funziona il proxy?",
    primary_type="GRAPH_COMPLETION",
    fallback_type="CHUNKS",
)
```

### `multi_search()`

Esegue piu tipi di ricerca in sequenza, ritorna risultati per tipo:

```python
from src.shared.cognee_toolkit import multi_search

all_results = await multi_search(
    "Come funziona il proxy?",
    search_types=["GRAPH_COMPLETION", "CHUNKS", "SUMMARIES"],
)
# {"GRAPH_COMPLETION": [...], "CHUNKS": [...], "SUMMARIES": [...]}
```

---

## Variabili d'ambiente

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `DEFAULT_MODEL` | `llm` | Modello LLM nel proxy |
| `LITELLM_BASE_URL` | `http://localhost:4000/v1` | URL proxy LiteLLM |
| `OPENAI_API_KEY` | `not-needed` | API key (il proxy gestisce le chiavi reali) |
| `COGNEE_VECTOR_DB_HOST` | `localhost` | Host PostgreSQL per PGVector |
| `COGNEE_VECTOR_DB_PORT` | `5433` | Porta PostgreSQL |
| `COGNEE_VECTOR_DB_NAME` | `vectors` | Database PostgreSQL |
| `COGNEE_VECTOR_DB_USERNAME` | `postgres` | Utente PostgreSQL |
| `COGNEE_VECTOR_DB_PASSWORD` | `postgres` | Password PostgreSQL |
| `EMBEDDING_PROVIDER` | `fastembed` | Provider embeddings |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Modello embeddings |
| `NEO4J_URL` | `bolt://localhost:7687` | URL Neo4j (Bolt protocol) |
| `NEO4J_USERNAME` | `neo4j` | Utente Neo4j |
| `NEO4J_PASSWORD` | `password` | Password Neo4j |

---

## Dipendenze Python

```bash
uv pip install -e ".[cognee]"
```

Definite in `pyproject.toml`:

```toml
cognee = [
    "cognee>=0.1",
]
```

| Pacchetto | Ruolo |
|-----------|-------|
| `cognee` | Knowledge graph engine (add, cognify, search, memify) |

L'infrastruttura PostgreSQL, Neo4j e Qdrant e gestita separatamente via Docker. Non servono pacchetti Python aggiuntivi per i database.
