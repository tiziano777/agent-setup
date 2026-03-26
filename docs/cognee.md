# Knowledge Graph Memory (Cognee)

Toolkit per knowledge graph memory basato su Cognee. Trasforma testo in grafi di conoscenza strutturati con entita, relazioni e ricerca semantica. Tutte le chiamate LLM passano per il proxy LiteLLM, usa Qdrant per i vettori e Neo4j per il grafo.

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
│  tools/ ──── get_cognee_tools()              │
│  nodes/ ──── create_cognee_enriched_llm_node │
│              create_cognee_search_node        │
│              create_cognee_add_node           │
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
 LiteLLM     Qdrant          Neo4j
 Proxy       (vettori)       (grafo)
 :4000       :6333           :7687
```

**Scelte architetturali:**

- **LLM via proxy**: Cognee viene configurato con `provider: "custom"` + `openai/{model}` per instradare tutte le chiamate LLM tramite il LiteLLM proxy. Nessuna API key Cognee necessaria.
- **Qdrant condiviso**: Riutilizza la stessa istanza Qdrant del modulo retrieval text-only.
- **Neo4j dedicato**: Il graph database e esclusivo per Cognee. Browser UI su http://localhost:7474.
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
    llm_provider="custom",
    llm_model="llm",                     # modello nel proxy_config.yml
    llm_endpoint="http://localhost:4000/v1",
    vector_db_provider="qdrant",          # o "pgvector", "lancedb"
    vector_db_url="http://localhost:6333",
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
| `llm_model` | `"llm"` | `DEFAULT_MODEL` | Nome modello nel proxy |
| `llm_endpoint` | `http://localhost:4000/v1` | `LITELLM_BASE_URL` | URL proxy LiteLLM |
| `vector_db_provider` | `"qdrant"` | — | Backend vettoriale |
| `vector_db_url` | `http://localhost:6333` | `QDRANT_URL` | URL Qdrant |
| `graph_db_provider` | `"neo4j"` | — | Backend grafo |
| `graph_db_url` | `bolt://localhost:7687` | `NEO4J_URL` | URL Neo4j |
| `graph_db_username` | `"neo4j"` | `NEO4J_USERNAME` | Utente Neo4j |
| `graph_db_password` | `"password"` | `NEO4J_PASSWORD` | Password Neo4j |

### `setup_cognee()`

Configura l'infrastruttura Cognee (idempotente):

```python
from src.shared.cognee_toolkit import setup_cognee

setup_cognee()  # usa env vars
setup_cognee(settings=CogneeSettings(graph_db_provider="networkx"))  # override
```

---

## Infrastruttura Docker

### Sviluppo (`docker-compose.yml`)

Neo4j gira come servizio Docker:

```yaml
neo4j:
  image: neo4j:5-community
  ports:
    - "7474:7474"   # Browser UI
    - "7687:7687"   # Bolt protocol
  environment:
    NEO4J_AUTH: neo4j/password
```

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

## LangGraph Nodes

| Factory | Descrizione |
|---------|-------------|
| `create_cognee_add_node(state_key="cognee_input")` | Legge da `state[state_key]`, ingestisce nel KG |
| `create_cognee_search_node(query_key, result_key)` | Cerca nel KG, scrive in `state[result_key]` |
| `create_cognee_cognify_node(datasets)` | Triggera costruzione del knowledge graph |
| `create_cognee_enriched_llm_node(search_type, system_prompt)` | RAG-over-KG: cerca contesto → chiama LLM |

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
| `QDRANT_URL` | `http://localhost:6333` | URL Qdrant |
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

L'infrastruttura Neo4j e Qdrant e gestita separatamente via Docker. Non servono pacchetti Python aggiuntivi per il graph database.
