# Vector Storage e Retrieval (RAG)

Guida completa all'infrastruttura di Retrieval Augmented Generation: vector database, embedding, chunking, ricerca ibrida e reranking.

## Panoramica Architettura

```
Documento sorgente
       |
       v
  [Chunking]           SizeChunker / SentenceChunker / StructureChunker
       |
       v
  [Embedding]           SentenceTransformer / OpenAI
       |
       v
  [Vector Store]        Qdrant / pgvector
       |
  [In-Memory Index]     BM25Index / VectorIndex
       |
       v
  ---- Query time ----
       |
       v
  [Multi-Index Search]  Ogni indice ritorna k*5 candidati
       |
       v
  [RRF Fusion]          Reciprocal Rank Fusion fonde i risultati
       |
       v
  [Reranking]           CrossEncoder / LLM (opzionale)
       |
       v
  Top-k documenti
```

Tutto il codice risiede in `src/shared/retrieval/` ed e esposto tramite factory functions:

```python
from src.shared.retrieval import (
    get_embedding,
    get_vectorstore,
    get_chunker,
    get_reranker,
    get_retriever,
)
```

---

## Installazione Dipendenze

Le dipendenze retrieval sono opzionali e modulari:

```bash
# Solo embedding locali (sentence-transformers)
uv pip install -e ".[retrieval]"

# Qdrant
uv pip install -e ".[retrieval,qdrant]"

# PostgreSQL + pgvector
uv pip install -e ".[retrieval,pgvector]"

# Embedding OpenAI
uv pip install -e ".[openai-embeddings]"

# Reranker cross-encoder
uv pip install -e ".[rerankers]"

# Tutto insieme
uv pip install -e ".[retrieval-all]"
```

---

## Avvio Infrastruttura Docker

Il `docker-compose.yml` include Qdrant e PostgreSQL/pgvector:

```bash
# Avvia tutto (proxy LLM + Qdrant + PostgreSQL)
docker compose up -d

# Solo i vector database
docker compose up -d qdrant postgres-vector

# Verifica stato
docker compose ps
```

| Servizio | Porta | Descrizione |
|----------|-------|-------------|
| `qdrant` | 6333 (REST), 6334 (gRPC) | Vector DB con HNSW |
| `postgres-vector` | 5433 | PostgreSQL 16 + pgvector |
| `litellm-proxy` | 4000 | Proxy LLM (preesistente) |

Variabili d'ambiente in `.env`:

```
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
PGVECTOR_URI=postgresql://postgres:postgres@localhost:5433/vectors
```

---

## Embedding

### Classi disponibili

| Provider | Classe | Dimensioni | Requisito |
|----------|--------|-----------|-----------|
| sentence-transformers | `SentenceTransformerEmbedding` | 384 (default) | `pip install -e ".[retrieval]"` |
| OpenAI | `OpenAIEmbedding` | 1536 (default) | `pip install -e ".[openai-embeddings]"` + `OPENAI_API_KEY` |

### Uso

```python
from src.shared.retrieval import get_embedding

# Locale (nessuna API key necessaria)
emb = get_embedding("sentence-transformer")
vector = emb.embed("Testo da vettorizzare")
# len(vector) == 384

# Batch (ottimizzato)
vectors = emb.embed_batch(["Testo 1", "Testo 2", "Testo 3"])

# OpenAI
emb_oai = get_embedding("openai", model="text-embedding-3-small")
vector = emb_oai.embed("Testo da vettorizzare")
# len(vector) == 1536

# OpenAI con dimensionality reduction
emb_compact = get_embedding("openai", model="text-embedding-3-large", dims=256)
```

### ABC: `BaseEmbedding`

Per aggiungere un nuovo provider, estendi `BaseEmbedding`:

```python
from src.shared.retrieval.embeddings.base import BaseEmbedding

class CohereEmbedding(BaseEmbedding):
    def embed(self, text: str) -> list[float]: ...
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def dimensions(self) -> int: ...
```

---

## Vector Stores

### Qdrant

Tre modalita di connessione:

```python
from src.shared.retrieval import get_vectorstore, get_embedding

emb = get_embedding("sentence-transformer")

# Remoto (Docker, produzione)
vs = get_vectorstore("qdrant", url="http://localhost:6333")

# In-memory (test, no persistenza)
vs = get_vectorstore("qdrant", url=":memory:")

# File locale (embedded, senza server)
vs = get_vectorstore("qdrant", url="./local_qdrant_data")
```

Utilizzo completo:

```python
from src.shared.retrieval.vectorstores.base import Document

# Crea/verifica la collection
vs.ensure_collection("my_docs", dims=emb.dimensions)

# Inserisci documenti
docs = [
    Document(id="1", content="Python e un linguaggio di programmazione",
             embedding=emb.embed("Python e un linguaggio di programmazione"),
             metadata={"lang": "it", "source": "wiki"}),
    Document(id="2", content="Docker containerizza le applicazioni",
             embedding=emb.embed("Docker containerizza le applicazioni"),
             metadata={"lang": "it", "source": "docs"}),
]
vs.upsert(docs)

# Cerca
results = vs.search(query_vector=emb.embed("linguaggi programmazione"), k=5)
for r in results:
    print(f"{r.document.id}: {r.score:.3f} - {r.document.content}")

# Cerca con filtri
results = vs.search(
    query_vector=emb.embed("linguaggi"),
    k=3,
    filters={"lang": "it"},
)

# Elimina
vs.delete(["1", "2"])
```

### pgvector (PostgreSQL)

```python
vs = get_vectorstore(
    "pgvector",
    connection_uri="postgresql://postgres:postgres@localhost:5433/vectors",
    index_type="hnsw",  # oppure "ivfflat" o None (flat scan)
)

vs.ensure_collection("my_docs", dims=384)
# Crea automaticamente: tabella + estensione vector + indice HNSW
```

L'API e identica a Qdrant (`upsert`, `search`, `delete`) grazie alla ABC `BaseVectorStore`.

### ABC: `BaseVectorStore`

```python
from src.shared.retrieval.vectorstores.base import BaseVectorStore, Document, SearchResult

class MyCustomStore(BaseVectorStore):
    def ensure_collection(self, name: str, dims: int) -> None: ...
    def upsert(self, documents: list[Document]) -> None: ...
    def search(self, query_vector: list[float], k: int = 5,
               filters: dict | None = None) -> list[SearchResult]: ...
    def delete(self, ids: list[str]) -> None: ...
```

### Confronto Vector Stores

| Aspetto | Qdrant | pgvector |
|---------|--------|----------|
| Indice default | HNSW | HNSW o IVFFlat |
| Filtraggio | Nativo (payload filters) | Via SQL WHERE su JSONB |
| Scalabilita | Distribuito (cluster) | Singolo nodo PostgreSQL |
| Persistenza | Volume Docker / Cloud | Volume Docker / RDS |
| Caso d'uso ideale | Vector search dedicato, grandi volumi | Gia usi PostgreSQL, dati relazionali + vettori |
| Modalita embedded | Si (`:memory:`, file locale) | No (richiede server) |

---

## Chunking

### Strategie disponibili

```python
from src.shared.retrieval import get_chunker

# Size-based (piu affidabile, funziona con qualsiasi documento)
chunker = get_chunker("size", chunk_size=500, chunk_overlap=50)
chunks = chunker.chunk(long_text)

# Sentence-based (mantiene confini di frase)
chunker = get_chunker("sentence", max_sentences=5, overlap_sentences=1)
chunks = chunker.chunk(long_text)

# Structure-based (split su heading Markdown)
chunker = get_chunker("structure", pattern=r"\n## ")
chunks = chunker.chunk(markdown_text)
```

### Confronto

| Strategia | Pro | Contro | Quando usarla |
|-----------|-----|--------|---------------|
| **Size** | Prevedibile, funziona ovunque | Puo spezzare mid-frase | Default per documenti generici |
| **Sentence** | Rispetta i confini semantici | Chunk di dimensioni variabili | Testo narrativo, articoli |
| **Structure** | Segue la struttura del documento | Richiede documenti formattati | Markdown, HTML, documenti tecnici |

### Arricchimento Contestuale

Per migliorare la qualita della ricerca, ogni chunk puo essere arricchito con contesto dal documento sorgente:

```python
from src.shared.retrieval.contextual import ContextualEnricher

enricher = ContextualEnricher()

# Singolo chunk
enriched = enricher.enrich(chunk, source_text=full_document)
# Ritorna: "Contesto generato dall'LLM\n" + chunk originale

# Batch (ottimizzato per documenti lunghi)
enriched_chunks = enricher.enrich_batch(chunks, source_text=full_document)
```

Per documenti molto lunghi (> 50k caratteri), `enrich_batch` usa automaticamente una finestra di contesto limitata ai chunk circostanti.

---

## Indici In-Memory

Per sviluppo e test senza database esterno.

### BM25Index (ricerca lessicale)

```python
from src.shared.retrieval.indexes.bm25 import BM25Index

bm25 = BM25Index(k1=1.5, b=0.75)
bm25.add_documents([
    {"id": "1", "content": "Python programming language"},
    {"id": "2", "content": "Docker container orchestration"},
])

results = bm25.search("programming", k=3)
# [({"id": "1", "content": "..."}, 0.85), ...]
```

### VectorIndex (ricerca semantica in-memory)

```python
from src.shared.retrieval.indexes.vector import VectorIndex
from src.shared.retrieval import get_embedding

emb = get_embedding("sentence-transformer")
vector_idx = VectorIndex(embedding_fn=emb.embed, distance_metric="cosine")

vector_idx.add_documents([
    {"id": "1", "content": "Python programming language"},
    {"id": "2", "content": "Docker container orchestration"},
])

results = vector_idx.search("coding", k=3)
```

---

## Panoramica Tipi di Indice

### Indici Dense (vettori densi)

| Tipo | Descrizione | Complessita | Quando usarlo |
|------|-------------|-------------|---------------|
| **Flat** | Scansione lineare, risultati esatti | O(n) | < 10k documenti, test |
| **HNSW** | Grafo navigabile small-world, approssimato | O(log n) | Default Qdrant. Il migliore per la maggior parte dei casi |
| **IVFFlat** | Inverted file index, raggruppa vettori in cluster | O(n/nprobe) | Default pgvector. Buono per dataset medi |
| **IVFPQ** | IVF + Product Quantization, comprime i vettori | O(n/nprobe) ridotto | Dataset enormi con vincoli di RAM |
| **ScaNN** | Google's Scalable Nearest Neighbors | O(log n) | Alternativa HNSW per scale molto grandi |

### Indici Sparse (lessicali)

| Tipo | Descrizione | Quando usarlo |
|------|-------------|---------------|
| **BM25** | TF-IDF migliorato con saturazione e normalizzazione lunghezza | Default per keyword search. Eccellente per match esatti e termini tecnici |
| **TF-IDF** | Term Frequency - Inverse Document Frequency classico | Baseline, generalmente superato da BM25 |
| **SPLADE** | Sparse Lexical and Expansion (modello neurale) | Quando serve espansione semantica su indici sparse |

### Approcci Multi-Vector

| Tipo | Descrizione | Quando usarlo |
|------|-------------|---------------|
| **ColBERT** | Late interaction: compara embedding per-token | Massima precisione, alto costo storage |
| **Multi-vector** | Un documento produce N vettori (uno per passaggio) | Documenti lunghi con sezioni eterogenee |

### Combinazioni Ibride Raccomandate

| Combinazione | Qualita | Latenza | Complessita |
|--------------|---------|---------|-------------|
| **BM25 + HNSW + RRF** | Alta | Bassa | Bassa |
| **BM25 + HNSW + RRF + Reranker** | Massima | Media | Media |
| **SPLADE + Dense + RRF** | Molto alta | Media | Alta |
| **ColBERT** | Molto alta | Media | Alta |

**Raccomandazione**: partire con **BM25 + VectorStore (HNSW) + RRF**, aggiungere il reranker solo se la qualita non e sufficiente.

---

## Pipeline di Retrieval

### Quick Start (pronta all'uso)

```python
from src.shared.retrieval import get_retriever

# Pipeline ibrida BM25 + VectorIndex con RRF
retriever = get_retriever()

# Indicizza documenti
retriever.add_documents([
    {"id": "1", "content": "Python e un linguaggio interpretato"},
    {"id": "2", "content": "Docker containerizza le applicazioni"},
    {"id": "3", "content": "I vector database memorizzano embedding"},
])

# Cerca
results = retriever.search("linguaggio di programmazione", k=2)
for doc in results:
    print(f"{doc['id']}: {doc['content']}")
```

### Pipeline custom

```python
from src.shared.retrieval import get_embedding, get_reranker
from src.shared.retrieval.indexes.bm25 import BM25Index
from src.shared.retrieval.indexes.vector import VectorIndex
from src.shared.retrieval.pipeline import RetrieverPipeline

emb = get_embedding("sentence-transformer")

pipeline = RetrieverPipeline(
    indexes=[
        BM25Index(),
        VectorIndex(embedding_fn=emb.embed),
    ],
    reranker=get_reranker("cross-encoder"),
    k_rrf=60,
    fan_out=5,             # ogni indice recupera k*5 candidati
)

pipeline.add_documents([...])
results = pipeline.search("query", k=5)
```

### Reciprocal Rank Fusion (RRF)

La formula di fusione usata dalla pipeline:

```
score(d) = sum( 1 / (k_rrf + rank_i) )   per ogni indice i
```

Dove `k_rrf=60` (default) riduce l'impatto dei documenti in fondo alla classifica. Ogni indice contribuisce indipendentemente al punteggio finale, rendendo la fusion robusta anche quando un indice non trova un documento.

---

## Reranking

### CrossEncoder (locale, bassa latenza)

```python
from src.shared.retrieval import get_reranker

reranker = get_reranker("cross-encoder")
# Modello: cross-encoder/ms-marco-MiniLM-L-6-v2
# Scoring locale, nessuna API call
```

### LLM Reranker (via LiteLLM proxy)

```python
reranker = get_reranker("llm")
# Usa get_llm() -> LiteLLM proxy -> provider rotation
# Piu accurato per query complesse, latenza piu alta
```

### Confronto

| Aspetto | CrossEncoder | LLM Reranker |
|---------|-------------|-------------|
| Latenza | ~50ms per 10 documenti | ~1-3s (API call) |
| Costo | Zero (locale) | Token LLM |
| Qualita | Buona (ottimizzato per information retrieval) | Migliore per query complesse e ambigue |
| Offline | Si | No (richiede proxy attivo) |

---

## Configurazione Centralizzata

```python
from src.shared.retrieval.config import RetrievalSettings

settings = RetrievalSettings(
    embedding_provider="sentence-transformer",
    embedding_model="paraphrase-multilingual-MiniLM-L12-v2",
    embedding_dims=384,
    vectorstore_provider="qdrant",
    collection_name="knowledge_base",
    qdrant_url="http://localhost:6333",
    search_k=5,
    rrf_k=60,
    use_reranker=True,
    reranker_provider="cross-encoder",
)

from src.shared.retrieval import get_retriever
retriever = get_retriever(settings=settings)
```

---

## Integrazione con gli Agenti

### Come tool LangChain

```python
# src/agents/rag_agent/tools/search_tool.py
from langchain_core.tools import tool
from src.shared.retrieval import get_retriever

@tool
def search_knowledge_base(query: str) -> str:
    """Cerca nella knowledge base e ritorna i documenti piu rilevanti."""
    retriever = get_retriever()
    results = retriever.search(query, k=3)
    return "\n\n---\n\n".join(doc["content"] for doc in results)
```

### Come nodo nel StateGraph

```python
# src/agents/rag_agent/states/state.py
from src.shared.types import BaseAgentState

class RAGAgentState(BaseAgentState):
    context: str           # Documenti recuperati
    sources: list[str]     # ID dei documenti usati

# src/agents/rag_agent/nodes/retrieve.py
from src.shared.retrieval import get_retriever

def retrieve(state: RAGAgentState) -> dict:
    query = state["messages"][-1].content
    retriever = get_retriever()
    results = retriever.search(query, k=5)
    context = "\n\n".join(doc["content"] for doc in results)
    sources = [doc["id"] for doc in results]
    return {"context": context, "sources": sources}

# src/agents/rag_agent/nodes/generate.py
from src.shared.llm import get_llm

def generate(state: RAGAgentState) -> dict:
    llm = get_llm()
    prompt = (
        f"Rispondi alla domanda usando SOLO il contesto fornito.\n\n"
        f"Contesto:\n{state['context']}\n\n"
        f"Domanda: {state['messages'][-1].content}"
    )
    response = llm.invoke([{"role": "user", "content": prompt}])
    return {"messages": [response]}
```

### Flusso StateGraph RAG completo

```python
# src/agents/rag_agent/agent.py
from langgraph.graph import END, START, StateGraph
from src.agents.rag_agent.states.state import RAGAgentState
from src.agents.rag_agent.nodes.retrieve import retrieve
from src.agents.rag_agent.nodes.generate import generate

def build_graph() -> StateGraph:
    builder = StateGraph(RAGAgentState)
    builder.add_node("retrieve", retrieve)
    builder.add_node("generate", generate)
    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "generate")
    builder.add_edge("generate", END)
    return builder

graph = build_graph().compile()

# START --> retrieve --> generate --> END
```

---

## Workflow Completo: Indicizzazione Documenti

```python
from src.shared.retrieval import get_embedding, get_vectorstore, get_chunker
from src.shared.retrieval.contextual import ContextualEnricher
from src.shared.retrieval.vectorstores.base import Document

# 1. Carica e chunka il documento
with open("documento.md") as f:
    source_text = f.read()

chunker = get_chunker("size", chunk_size=500, chunk_overlap=50)
chunks = chunker.chunk(source_text)

# 2. (Opzionale) Arricchisci con contesto
enricher = ContextualEnricher()
chunks = enricher.enrich_batch(chunks, source_text)

# 3. Genera embedding
emb = get_embedding("sentence-transformer")
vectors = emb.embed_batch(chunks)

# 4. Prepara i Document
docs = [
    Document(
        id=f"doc-{i}",
        content=chunk,
        embedding=vector,
        metadata={"source": "documento.md", "chunk_index": i},
    )
    for i, (chunk, vector) in enumerate(zip(chunks, vectors))
]

# 5. Inserisci nel vector store
vs = get_vectorstore("qdrant")
vs.ensure_collection("my_knowledge_base", dims=emb.dimensions)
vs.upsert(docs)
```

---

## Estendere il Sistema

Per aggiungere un nuovo vector store, embedding provider, chunker o reranker:

1. Crea un file nel sotto-modulo appropriato (es. `vectorstores/milvus.py`)
2. Estendi l'ABC corrispondente (`BaseVectorStore`, `BaseEmbedding`, ecc.)
3. Aggiungi un branch nella factory function in `src/shared/retrieval/__init__.py`
4. Aggiungi le dipendenze in `pyproject.toml` come optional dependency

Esempio -- aggiungere un nuovo vector store:

```python
# src/shared/retrieval/vectorstores/milvus.py
from src.shared.retrieval.vectorstores.base import BaseVectorStore

class MilvusVectorStore(BaseVectorStore):
    def ensure_collection(self, name, dims): ...
    def upsert(self, documents): ...
    def search(self, query_vector, k=5, filters=None): ...
    def delete(self, ids): ...
```

```python
# In src/shared/retrieval/__init__.py, aggiungi alla factory:
def get_vectorstore(provider="qdrant", **kwargs):
    ...
    if provider == "milvus":
        from src.shared.retrieval.vectorstores.milvus import MilvusVectorStore
        return MilvusVectorStore(**kwargs)
```
