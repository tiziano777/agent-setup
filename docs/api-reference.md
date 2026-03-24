# API Reference

Reference completo del modulo `src/shared/` e `src/shared/retrieval/`.

## src/shared/llm

### `get_llm(model, temperature, max_tokens) -> ChatOpenAI`

Factory che ritorna un client LLM puntato al LiteLLM proxy.

```python
from src.shared.llm import get_llm

# Default: usa il pool di rotazione
llm = get_llm()

# Con parametri custom
llm = get_llm(model="llm", temperature=0.3, max_tokens=4096)

# Invocazione
response = llm.invoke([{"role": "user", "content": "Ciao"}])
print(response.content)
```

**Parametri:**

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `model` | `str` | `"llm"` | Nome modello come in proxy_config.yml. `"llm"` usa la rotazione |
| `temperature` | `float` | `0.7` | Temperatura di sampling |
| `max_tokens` | `int` | `2048` | Token massimi nella risposta |

**Note:**
- Ritorna un `ChatOpenAI` di `langchain-openai`
- Punta a `LITELLM_BASE_URL` (default `http://localhost:4000/v1`)
- `api_key` e impostata a `"not-needed"` perche il proxy gestisce l'autenticazione
- Risultati cachati con `lru_cache(maxsize=8)` -- stessi parametri = stessa istanza
- Variabili d'ambiente: `LITELLM_BASE_URL`, `DEFAULT_MODEL`

---

## src/shared/types

### `BaseAgentState`

TypedDict base con il campo `messages` e il reducer `add_messages`.

```python
from src.shared.types import BaseAgentState

# Estendi per stato custom
class MyState(BaseAgentState):
    context: str
    score: float
```

**Campi:**

| Campo | Tipo | Reducer | Descrizione |
|-------|------|---------|-------------|
| `messages` | `list[AnyMessage]` | `add_messages` | Lista messaggi, accumulata automaticamente |

### `HandoffPayload`

TypedDict per i payload di handoff tra agenti.

```python
from src.shared.types import HandoffPayload

payload: HandoffPayload = {
    "target_agent": "writer",
    "messages": [...],
    "metadata": {"priority": "high"},
}
```

**Campi:**

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `target_agent` | `str` | Nome dell'agente destinatario |
| `messages` | `list[dict]` | Messaggi da passare |
| `metadata` | `dict` | Metadati arbitrari |

---

## src/shared/memory

### `get_checkpointer() -> InMemorySaver`

Factory per il checkpointer (short-term memory, per thread).

```python
from src.shared.memory import get_checkpointer

checkpointer = get_checkpointer()
graph = build_graph().compile(checkpointer=checkpointer)

# Ora il grafo persiste lo stato per thread_id
result = graph.invoke(
    {"messages": [...]},
    config={"configurable": {"thread_id": "session-1"}}
)
```

**Ritorna:** `InMemorySaver` in sviluppo. Per produzione, sostituire con `PostgresSaver`.

### `get_store(embed_fn, dims) -> InMemoryStore`

Factory per lo store (long-term memory, cross-thread).

```python
from src.shared.memory import get_store

# Store semplice (key-value)
store = get_store()

# Store con semantic search
from langchain_openai import OpenAIEmbeddings
store = get_store(embed_fn=OpenAIEmbeddings(), dims=1536)
```

**Parametri:**

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `embed_fn` | `callable \| None` | `None` | Funzione di embedding per semantic search |
| `dims` | `int` | `1536` | Dimensionalita degli embedding |

**Ritorna:** `InMemoryStore`. Se `embed_fn` e fornito, lo store supporta ricerca semantica.

---

## src/shared/registry

### `AgentEntry`

Dataclass che rappresenta un agente registrato.

```python
@dataclass
class AgentEntry:
    name: str           # Nome dell'agente (es. "agent1")
    module_path: str    # Path modulo (es. "src.agents.agent1")
    graph: Any = None   # StateGraph compilato
    workflow: Any = None # @entrypoint function
```

### `AgentRegistry`

Classe per la discovery e registrazione degli agenti.

```python
from src.shared.registry import registry

# Auto-discover
registry.discover("src.agents")

# Accesso
registry.list_agents()        # ["agent1", "agent2"]
registry.get("agent1")        # AgentEntry
registry.get_graph("agent1")  # CompiledGraph
registry.get_workflow("agent1")  # @entrypoint function
```

**Metodi:**

#### `discover(package_path="src.agents") -> None`

Scansiona i sub-package del path dato e registra quelli che espongono `graph` e/o `workflow`.

- Ignora i package che terminano con `_template`
- Non solleva eccezioni per agenti non caricabili (stampa warning)

#### `get(name) -> AgentEntry | None`

Ritorna l'`AgentEntry` per nome, o `None` se non trovato.

#### `list_agents() -> list[str]`

Ritorna la lista di nomi degli agenti registrati.

#### `get_graph(name) -> CompiledGraph`

Ritorna il grafo compilato. Solleva `KeyError` se l'agente non esiste, `ValueError` se non espone un graph.

#### `get_workflow(name) -> entrypoint`

Ritorna il workflow funzionale. Solleva `KeyError` se l'agente non esiste, `ValueError` se non espone un workflow.

### `registry` (singleton)

Istanza globale di `AgentRegistry`, pronta all'uso.

### `discover_agents() -> list[str]`

Funzione convenience in `src/agents/__init__.py`:

```python
from src.agents import discover_agents

names = discover_agents()  # Chiama registry.discover() e ritorna la lista
```

---

## src/shared/orchestration

### `create_handoff_tool(agent_name, description) -> tool`

Crea un tool LangChain che trasferisce il controllo a un altro agente.

```python
from src.shared.orchestration import create_handoff_tool

transfer = create_handoff_tool("writer", "Transfer to writer for content creation")
```

**Parametri:**

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `agent_name` | `str` | - | Nome dell'agente destinatario |
| `description` | `str \| None` | `None` | Descrizione del tool (default: `"Transfer to {name}"`) |

**Ritorna:** Un `@tool` decorato che produce un `Command(goto=agent_name, graph=Command.PARENT)`.

### `build_supervisor(agent_names, registry, supervisor_model, supervisor_prompt) -> CompiledGraph`

Costruisce un grafo multi-agent con pattern supervisor.

```python
from src.shared.orchestration import build_supervisor

graph = build_supervisor(
    agent_names=["researcher", "writer"],
    registry=registry,
    supervisor_model="llm",
    supervisor_prompt="Route tasks to the appropriate agent.",
)
```

**Parametri:**

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `agent_names` | `list[str]` | - | Nomi agenti worker (devono essere nel registry) |
| `registry` | `AgentRegistry` | - | Istanza del registry |
| `supervisor_model` | `str` | `"llm"` | Modello per il supervisor |
| `supervisor_prompt` | `str` | `"You are a supervisor..."` | System prompt del supervisor |

### `build_network(agent_configs, registry) -> CompiledGraph`

Costruisce un grafo multi-agent peer-to-peer.

```python
from src.shared.orchestration import build_network

graph = build_network(
    agent_configs={
        "agent1": {"tools": [...], "prompt": "You are agent1."},
        "agent2": {"tools": [...], "prompt": "You are agent2."},
    },
    registry=registry,
)
```

**Parametri:**

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `agent_configs` | `dict[str, dict]` | - | Config per agente: `{"tools": [], "prompt": ""}` |
| `registry` | `AgentRegistry` | - | Istanza del registry |

### `build_independent(agent_names, registry) -> CompiledGraph`

Costruisce un grafo che esegue agenti in parallelo.

```python
from src.shared.orchestration import build_independent

graph = build_independent(
    agent_names=["analyst", "critic"],
    registry=registry,
)
```

**Parametri:**

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `agent_names` | `list[str]` | - | Nomi agenti da eseguire in parallelo |
| `registry` | `AgentRegistry` | - | Istanza del registry |

---

## src/shared/retrieval

Modulo RAG con factory functions, classi astratte e implementazioni. Per la guida d'uso completa vedi [Vector Storage e Retrieval](vector-storage.md).

### Factory Functions

#### `get_embedding(provider, **kwargs) -> BaseEmbedding`

Ritorna un provider di embedding.

```python
from src.shared.retrieval import get_embedding

emb = get_embedding("sentence-transformer")             # Locale (384 dim)
emb = get_embedding("openai", model="text-embedding-3-small")  # API (1536 dim)
```

**Provider supportati:**

| Provider | Classe | Dims default | Requisito |
|----------|--------|-------------|-----------|
| `"sentence-transformer"` | `SentenceTransformerEmbedding` | 384 | `pip install -e ".[retrieval]"` |
| `"openai"` | `OpenAIEmbedding` | 1536 | `pip install -e ".[openai-embeddings]"` |

**kwargs per `"sentence-transformer"`:** `model_name`, `normalize`, `device`

**kwargs per `"openai"`:** `model`, `api_key`, `dims`

---

#### `get_vectorstore(provider, **kwargs) -> BaseVectorStore`

Ritorna un vector store.

```python
from src.shared.retrieval import get_vectorstore

vs = get_vectorstore("qdrant")                   # Qdrant (default)
vs = get_vectorstore("qdrant", url=":memory:")   # In-memory
vs = get_vectorstore("pgvector")                 # PostgreSQL + pgvector
```

**Provider supportati:**

| Provider | Classe | Requisito |
|----------|--------|-----------|
| `"qdrant"` | `QdrantVectorStore` | `pip install -e ".[qdrant]"` |
| `"pgvector"` | `PgVectorStore` | `pip install -e ".[pgvector]"` |

**kwargs per `"qdrant"`:** `url`, `api_key`, `collection_name`, `distance`

**kwargs per `"pgvector"`:** `connection_uri`, `index_type`

---

#### `get_chunker(strategy, **kwargs) -> BaseChunker`

Ritorna una strategia di chunking.

```python
from src.shared.retrieval import get_chunker

chunker = get_chunker("size", chunk_size=500, chunk_overlap=50)
chunker = get_chunker("sentence", max_sentences=5, overlap_sentences=1)
chunker = get_chunker("structure", pattern=r"\n## ")
```

**Strategie supportate:** `"size"`, `"sentence"`, `"structure"`

---

#### `get_reranker(provider, **kwargs) -> BaseReranker`

Ritorna un reranker.

```python
from src.shared.retrieval import get_reranker

reranker = get_reranker("cross-encoder")   # Locale
reranker = get_reranker("llm")             # Via LiteLLM proxy
```

**Provider supportati:**

| Provider | Classe | Requisito |
|----------|--------|-----------|
| `"cross-encoder"` | `CrossEncoderReranker` | `pip install -e ".[rerankers]"` |
| `"llm"` | `LLMReranker` | Proxy LiteLLM attivo |

---

#### `get_retriever(settings, **kwargs) -> RetrieverPipeline`

Ritorna una pipeline di retrieval pronta all'uso (BM25 + VectorIndex + RRF).

```python
from src.shared.retrieval import get_retriever

retriever = get_retriever()                           # Default settings
retriever = get_retriever(settings=RetrievalSettings(
    use_reranker=True,
    reranker_provider="cross-encoder",
))
```

---

### Data Models

#### `Document`

```python
from src.shared.retrieval.vectorstores.base import Document

doc = Document(
    id="doc-1",
    content="Testo del documento",
    embedding=[0.1, 0.2, ...],         # Opzionale
    metadata={"source": "wiki"},        # Opzionale
)
```

| Campo | Tipo | Default | Descrizione |
|-------|------|---------|-------------|
| `id` | `str` | - | Identificatore univoco |
| `content` | `str` | - | Testo del documento |
| `embedding` | `list[float] \| None` | `None` | Vettore embedding |
| `metadata` | `dict` | `{}` | Metadati arbitrari |

#### `SearchResult`

```python
from src.shared.retrieval.vectorstores.base import SearchResult

# Ritornato da BaseVectorStore.search()
result.document    # Document
result.score       # float (similarita, 0-1)
```

#### `RetrievalSettings`

```python
from src.shared.retrieval.config import RetrievalSettings
```

| Campo | Tipo | Default | Descrizione |
|-------|------|---------|-------------|
| `embedding_provider` | `str` | `"sentence-transformer"` | Provider embedding |
| `embedding_model` | `str` | `"paraphrase-multilingual-MiniLM-L12-v2"` | Modello |
| `embedding_dims` | `int` | `384` | Dimensioni vettore |
| `vectorstore_provider` | `str` | `"qdrant"` | Backend vector store |
| `collection_name` | `str` | `"default"` | Nome collection |
| `qdrant_url` | `str` | env `QDRANT_URL` | URL Qdrant |
| `postgres_uri` | `str` | env `PGVECTOR_URI` | URI PostgreSQL |
| `pgvector_index_type` | `str` | `"hnsw"` | Tipo indice (`"hnsw"`, `"ivfflat"`) |
| `search_k` | `int` | `5` | Top-k risultati |
| `rrf_k` | `int` | `60` | Costante RRF |
| `use_reranker` | `bool` | `False` | Abilita reranking |
| `reranker_provider` | `str` | `"cross-encoder"` | Provider reranker |

---

### Classi Astratte (ABC)

Tutte le implementazioni sono estendibili. Per aggiungere un nuovo provider, estendi l'ABC e aggiungi un branch nella factory corrispondente.

| ABC | Metodi astratti | Implementazioni |
|-----|----------------|-----------------|
| `BaseEmbedding` | `embed()`, `embed_batch()`, `dimensions` | `SentenceTransformerEmbedding`, `OpenAIEmbedding` |
| `BaseVectorStore` | `ensure_collection()`, `upsert()`, `search()`, `delete()` | `QdrantVectorStore`, `PgVectorStore` |
| `BaseChunker` | `chunk()` | `SizeChunker`, `SentenceChunker`, `StructureChunker` |
| `BaseReranker` | `rerank()` | `CrossEncoderReranker`, `LLMReranker` |
| `BaseIndex` (Protocol) | `add_document()`, `add_documents()`, `search()` | `BM25Index`, `VectorIndex` |
