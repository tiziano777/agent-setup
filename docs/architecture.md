# Architettura del Sistema

## Overview

Il progetto segue un'architettura a tre livelli:

```
src/shared/          Livello infrastruttura (LLM, memory, retrieval, registry, orchestration)
     |
src/agents/          Livello agenti (moduli autonomi, ciascuno un grafo LangGraph)
     |
src/app/             Livello applicazione (Streamlit, FastAPI, CLI)
```

Ogni livello dipende solo da quelli sopra, mai il contrario.

## Flusso dei Dati

```
Utente
  |
  v
src/app/             <-- entry point applicativo
  |
  v
AgentRegistry        <-- scopre e carica gli agenti disponibili
  |
  v
agent_n/agent.py     <-- grafo StateGraph compilato
  |
  +---> nodes/       <-- logica di ogni nodo
  +---> tools/       <-- tool LangChain (@tool)
  +---> states/      <-- definizione stato (TypedDict)
  +---> prompts/     <-- system prompt
  |
  +---> src/shared/retrieval/  <-- (opzionale) pipeline RAG
  |       +---> chunking/      <-- split documenti in chunk
  |       +---> embeddings/    <-- vettorizzazione testo
  |       +---> vectorstores/  <-- Qdrant / pgvector
  |       +---> indexes/       <-- BM25 / VectorIndex in-memory
  |       +---> pipeline.py    <-- RRF fusion multi-indice
  |       +---> rerankers/     <-- reranking risultati
  |
  v
src/shared/llm.py    <-- client LLM unificato
  |
  v
LiteLLM Proxy        <-- rotazione automatica tra 12 provider
  |
  v
Provider LLM esterno (Groq, Gemini, Mistral, ...)
```

## Componenti Principali

### 1. LiteLLM Proxy (`docker-compose.yml` + `proxy_config.yml`)

Container Docker che espone un endpoint OpenAI-compatible su `localhost:4000`. Tutti i 12 provider LLM sono registrati sotto lo stesso `model_name: "llm"`, il che abilita la rotazione automatica.

**Strategia di routing:**
- `simple-shuffle` -- selezione casuale del provider
- 5 retry con rilevamento header `Retry-After`
- Health check pre-call per evitare provider in cooldown
- 60s di cooldown dopo 5 fallimenti consecutivi
- `drop_params: True` per compatibilita cross-provider

Il proxy gestisce autenticazione, retry e fallback. Gli agenti non hanno bisogno di conoscere i dettagli dei singoli provider.

### 1b. Vector Database (`docker-compose.yml`)

Il docker-compose include anche i servizi per il vector storage:

| Servizio | Immagine | Porta | Uso |
|----------|----------|-------|-----|
| `qdrant` | `qdrant/qdrant:latest` | 6333 (REST), 6334 (gRPC) | Vector search con HNSW |
| `postgres-vector` | `pgvector/pgvector:pg16` | 5433 | PostgreSQL 16 + estensione pgvector |

Entrambi sono opzionali: basta avviare solo quelli necessari con `docker compose up -d qdrant` o `docker compose up -d postgres-vector`.

### 2. Modulo Shared (`src/shared/`)

Cinque file + un sotto-modulo con responsabilita distinte:

| File | Responsabilita |
|------|---------------|
| `llm.py` | Factory `get_llm()` che ritorna un `ChatOpenAI` puntato al proxy. Con `lru_cache` per evitare istanze duplicate. |
| `types.py` | `BaseAgentState` con il reducer `add_messages` e `HandoffPayload` per handoff multi-agent. |
| `memory.py` | Factory `get_checkpointer()` e `get_store()`. InMemory per dev, sostituibili con Postgres per prod. |
| `registry.py` | `AgentRegistry` con discovery via `pkgutil.iter_modules`. Singleton `registry`. |
| `orchestration.py` | Factory `build_supervisor()`, `build_network()`, `build_independent()` per composizione multi-agent. |
| `retrieval/` | Pipeline RAG modulare: embedding, vector stores (Qdrant, pgvector), chunking, indici in-memory (BM25, dense), RRF fusion, reranking. Vedi [Vector Storage e Retrieval](vector-storage.md). |

### 3. Modulo Agenti (`src/agents/`)

Ogni agente e un sub-package Python con struttura fissa:

```
agent_n/
├── __init__.py      # Esporta graph + workflow
├── agent.py         # Graph API: build_graph() -> StateGraph.compile()
├── config/          # AgentSettings (dataclass)
├── states/          # AgentState (TypedDict + add_messages)
├── nodes/           # Funzioni nodo: state -> partial update
├── tools/           # @tool decorated functions
├── prompts/         # SYSTEM_PROMPT + dynamic prompts
├── schemas/         # Pydantic AgentInput/AgentOutput
├── pipelines/       # Functional API: @entrypoint/@task
├── scorers/         # Funzioni di scoring/valutazione
├── memory/          # Namespace per long-term memory
├── image/           # Asset visivi (diagrammi, mermaid, PNG)
└── tests/           # Test unitari
```

Ogni agente espone due entry point:
- `graph` -- StateGraph compilato, per composizione, visualizzazione, LangGraph Studio
- `workflow` -- `@entrypoint` function, per flussi lineari con persistence

### 4. Template (`src/agents/_template/`)

Skeleton identico alla struttura sopra ma con placeholder `__AGENT_NAME__`. Il comando `make new-agent name=X` lo copia e sostituisce i placeholder con sed.

Il template e escluso dalla discovery del registry (filtrato su `_template`) e dalla raccolta test di pytest (via `conftest.py`).

## Dual API: Graph vs Functional

| Aspetto | Graph API (`agent.py`) | Functional API (`pipelines/pipeline.py`) |
|---------|-------------------------|------------------------------------------|
| Stile | Dichiarativo: nodi + edge | Imperativo: Python con decoratori |
| Controllo flusso | Conditional edges, routing | if/else, loop, try/except |
| Visualizzazione | Supporto nativo (Mermaid, Studio) | Limitato |
| Multi-agent | Composizione via subgraph | Chiamate dirette |
| Persistence | `graph.compile(checkpointer=...)` | `@entrypoint(checkpointer=...)` |
| Uso consigliato | Grafi complessi, multi-step | Flussi lineari, prototipi rapidi |

Entrambi condividono gli stessi moduli interni (nodes, tools, prompts, states, memory), cambia solo il modo in cui il flusso e orchestrato.

## Ciclo di Vita di una Richiesta (Graph API)

1. L'applicazione chiama `graph.invoke({"messages": [user_msg]})`
2. LangGraph crea lo stato iniziale (`AgentState`) con il messaggio utente
3. Il flusso parte da `START` e raggiunge il nodo `"process"`
4. `process()` in `nodes/example_node.py`:
   - Recupera il system prompt da `prompts/system.py`
   - Chiama `get_llm()` da `src/shared/llm.py`
   - Il client punta a `localhost:4000/v1` (LiteLLM proxy)
   - Il proxy sceglie un provider, gestisce retry/fallback
   - La risposta LLM viene wrappata e aggiunta a `messages`
5. Il flusso raggiunge `END`, lo stato finale viene ritornato

## Memory

Due livelli di memoria, entrambi opzionali:

**Short-term (per thread):**
- Gestita dal checkpointer passato a `compile()` o `@entrypoint()`
- Salva lo stato a ogni super-step del grafo
- Permette resume, replay e time-travel
- Dev: `InMemorySaver` / Prod: `PostgresSaver`

**Long-term (cross-thread):**
- Gestita dallo store (InMemoryStore o DB-backed)
- Namespace per agente e utente: `(user_id, agent_name)`
- Supporto opzionale per semantic search con embedding
- Configurata in `memory/store.py` di ogni agente

## Retrieval (RAG)

Il modulo `src/shared/retrieval/` fornisce un'infrastruttura RAG completa, separata dalla memory ma complementare ad essa:

- **Embedding**: sentence-transformers (locale) e OpenAI (API), dietro ABC `BaseEmbedding`
- **Vector stores**: Qdrant e pgvector, dietro ABC `BaseVectorStore`
- **Indici in-memory**: BM25 (sparse) e VectorIndex (dense), per dev/test
- **Chunking**: size, sentence, structure, dietro ABC `BaseChunker`
- **Reranking**: CrossEncoder (locale) e LLM (via proxy), dietro ABC `BaseReranker`
- **Pipeline**: `RetrieverPipeline` con Reciprocal Rank Fusion multi-indice

Gli agenti accedono al retrieval come tool (`@tool`) o come nodo nel grafo (`retrieve → generate`). Le factory functions (`get_embedding`, `get_vectorstore`, `get_retriever`) seguono lo stesso pattern di `get_llm()` e `get_store()`.

Per la guida completa vedi [Vector Storage e Retrieval](vector-storage.md).

## Registry e Discovery

```python
from src.agents import discover_agents
from src.shared.registry import registry

# Scansiona src/agents/ e registra tutti gli agenti
names = discover_agents()   # ["agent1", "agent2", ...]

# Usa un agente specifico
graph = registry.get_graph("agent1")
result = graph.invoke({"messages": [...]})
```

Il registry usa `pkgutil.iter_modules` per iterare i sub-package di `src/agents/`. Per ogni package:
1. Importa il modulo
2. Legge gli attributi `graph` e `workflow` dal suo `__init__.py`
3. Li registra in un dizionario `{nome: AgentEntry}`

I package che iniziano con `_` (come `_template`) vengono ignorati.
