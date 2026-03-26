# RAG Multimodale

Pipeline RAG multimodale basata su RAG-Anything per l'elaborazione di PDF, immagini, tabelle e equazioni. Supporta parsing con MinerU, Docling, PaddleOCR e GLM-OCR, knowledge graph + vector retrieval, e query ibride.

## Indice

- [Architettura](#architettura)
- [File del modulo](#file-del-modulo)
- [Configurazione](#configurazione)
- [Quick Start](#quick-start)
- [Parser supportati](#parser-supportati)
- [GLM-OCR](#glm-ocr)
- [Data Models](#data-models)
- [Pipeline API](#pipeline-api)
- [Layer Adapter](#layer-adapter)
- [Relazione con retrieval text-only](#relazione-con-retrieval-text-only)
- [Variabili d'ambiente](#variabili-dambiente)
- [Dipendenze Python](#dipendenze-python)

---

## Architettura

```
┌──────────────────────────────────────────────┐
│  Documento (PDF, immagine, DOCX, PPTX)       │
└───────────────────┬──────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────┐
│  Parser                                      │
│  MinerU / Docling / PaddleOCR / GLM-OCR      │
│                                              │
│  Output: list[MultimodalContent]             │
│  (testo, immagini, tabelle, equazioni)       │
└───────────────────┬──────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────┐
│  RAGAnything                                 │
│                                              │
│  Knowledge Graph (LightRAG)                  │
│  + Vector Store (embedding)                  │
│  + Multimodal content indexing               │
└───────────────────┬──────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────┐
│  Query Engine                                │
│  hybrid / local / global / naive             │
│  + VLM-enhanced (opzionale)                  │
└───────────────────┬──────────────────────────┘
                    │
                    ▼
              LiteLLM Proxy (:4000)
              via adapter layer
```

**Scelte architetturali:**

- **LLM/Embedding via proxy**: I layer adapter (`llm_adapter.py`, `embedding_adapter.py`) wrappano `get_llm()` e `get_embedding()` del progetto nelle interfacce async richieste da RAG-Anything.
- **Storage locale**: I dati e indici vengono salvati in `./rag_storage` (configurabile via `RAGANYTHING_WORKING_DIR`). Non usa Qdrant/PGVector direttamente.
- **Parser intercambiabili**: `BaseMultimodalParser` ABC permette di aggiungere nuovi parser.

---

## File del modulo

```
src/shared/retrieval/multimodal/
├── __init__.py              # Factory functions: get_multimodal_retriever(), get_multimodal_parser()
├── config.py                # MultimodalRetrievalSettings dataclass
├── models.py                # ContentType, MultimodalContent, MultimodalDocument
├── pipeline.py              # MultimodalRetrieverPipeline (orchestratore principale)
├── parsers/
│   ├── __init__.py
│   ├── base.py              # BaseMultimodalParser ABC
│   ├── raganything.py       # RAGAnythingParser (MinerU/Docling/PaddleOCR)
│   └── glmocr.py            # GlmOcrParser (GLM-OCR cloud/self-hosted)
└── adapters/
    ├── __init__.py
    ├── llm_adapter.py       # create_llm_model_func(), create_vision_model_func()
    └── embedding_adapter.py # create_embedding_func() → LightRAG EmbeddingFunc
```

---

## Configurazione

### `MultimodalRetrievalSettings`

```python
from src.shared.retrieval.multimodal import MultimodalRetrievalSettings

settings = MultimodalRetrievalSettings(
    working_dir="./rag_storage",
    parser="mineru",                # "mineru", "docling", "paddleocr", "glmocr"
    parse_method="auto",            # "auto", "ocr", "txt"
    enable_image_processing=True,
    enable_table_processing=True,
    enable_equation_processing=True,
    default_query_mode="hybrid",    # "hybrid", "local", "global", "naive"
    embedding_provider="sentence-transformer",
    embedding_model="paraphrase-multilingual-MiniLM-L12-v2",
    llm_model="llm",               # modello nel proxy
)
```

| Campo | Default | Env Var | Descrizione |
|-------|---------|---------|-------------|
| `working_dir` | `./rag_storage` | `RAGANYTHING_WORKING_DIR` | Directory per indici e dati |
| `parser` | `"mineru"` | — | Parser: mineru, docling, paddleocr, glmocr |
| `parse_method` | `"auto"` | — | Metodo parsing: auto, ocr, txt |
| `glmocr_mode` | `"maas"` | `GLMOCR_MODE` | GLM-OCR: maas (cloud) o selfhosted |
| `glmocr_api_key` | — | `GLMOCR_API_KEY` o `ZHIPU_API_KEY` | API key per GLM-OCR MaaS |
| `glmocr_selfhosted_host` | `localhost` | `GLMOCR_HOST` | Host GLM-OCR self-hosted |
| `glmocr_selfhosted_port` | `8080` | `GLMOCR_PORT` | Porta GLM-OCR self-hosted |
| `default_query_mode` | `"hybrid"` | — | Modalita query: hybrid, local, global, naive |
| `vlm_enhanced` | `None` (auto) | — | VLM-enhanced retrieval (richiede vision_model) |
| `vision_model` | — | `VISION_MODEL` | Modello vision (opzionale, per VLM-enhanced) |
| `llm_model` | `"llm"` | `DEFAULT_MODEL` | Modello LLM |
| `embedding_provider` | `"sentence-transformer"` | — | Provider embedding |
| `max_workers` | `4` | — | Worker per batch processing |

---

## Quick Start

```python
from src.shared.retrieval.multimodal import get_multimodal_retriever

# Crea la pipeline
pipeline = get_multimodal_retriever()

# Ingestione di un PDF
await pipeline.ingest("report.pdf")

# Ingestione batch di una cartella
await pipeline.ingest_folder("./documenti/", file_extensions=[".pdf", ".docx"])

# Query
answer = await pipeline.query("Quali sono i risultati principali?")
print(answer)

# Query con modalita specifica
answer = await pipeline.query("Descrivi le tabelle", mode="local")
```

### Versione sincrona (per nodi LangGraph)

```python
pipeline.ingest_sync("report.pdf")
answer = pipeline.query_sync("Quali sono i risultati?")
```

---

## Parser supportati

| Parser | Backed by | Formati | Nota |
|--------|-----------|---------|------|
| `mineru` (default) | MinerU via RAG-Anything | PDF, DOC, DOCX, PPT, PPTX, XLS, XLSX, immagini, TXT, MD | Parser piu completo |
| `docling` | Docling via RAG-Anything | Stessi di mineru | Alternativa a MinerU |
| `paddleocr` | PaddleOCR via RAG-Anything | Stessi di mineru | Ottimizzato per OCR |
| `glmocr` | GLM-OCR (GLM-4.1V) | PDF, PNG, JPG, JPEG, BMP, TIFF, GIF, WEBP | Vision-language model |

### Uso diretto dei parser

```python
from src.shared.retrieval.multimodal import get_multimodal_parser

parser = get_multimodal_parser("glmocr")
content_list = await parser.parse("document.pdf")

# Batch
results = await parser.parse_batch("./docs/", file_extensions=[".pdf"], max_workers=4)
```

---

## GLM-OCR

Due modalita operative:

### MaaS (cloud) — Default

```python
settings = MultimodalRetrievalSettings(
    parser="glmocr",
    glmocr_mode="maas",
    glmocr_api_key="your-zhipu-api-key",  # o env GLMOCR_API_KEY / ZHIPU_API_KEY
)
```

### Self-hosted

```python
settings = MultimodalRetrievalSettings(
    parser="glmocr",
    glmocr_mode="selfhosted",
    glmocr_selfhosted_host="localhost",
    glmocr_selfhosted_port=8080,
)
```

---

## Data Models

### `ContentType`

```python
class ContentType(Enum):
    TEXT = "text"
    IMAGE = "image"
    TABLE = "table"
    EQUATION = "equation"
    GENERIC = "generic"
```

### `MultimodalContent`

Singolo elemento estratto da un documento:

```python
@dataclass
class MultimodalContent:
    content_type: ContentType
    page_idx: int = 0
    text: str | None = None          # TEXT
    img_path: Path | None = None     # IMAGE
    image_caption: str | None = None # IMAGE
    table_body: str | None = None    # TABLE (markdown)
    table_caption: str | None = None # TABLE
    latex: str | None = None         # EQUATION
    content: str | None = None       # GENERIC fallback

    def to_raganything_dict(self) -> dict  # conversione per RAG-Anything
    @property
    def display_text(self) -> str          # testo human-readable
```

### `MultimodalDocument`

Estende `Document` del modulo retrieval text-only:

```python
@dataclass
class MultimodalDocument(Document):
    media: list[MultimodalContent]
    source_path: str | None = None

    @classmethod
    def from_content_list(cls, doc_id, content_list, source_path=None, metadata=None)
```

---

## Pipeline API

### `MultimodalRetrieverPipeline`

| Metodo | Tipo | Descrizione |
|--------|------|-------------|
| `ingest(file_path, output_dir)` | async | Parsa e indicizza un documento |
| `ingest_folder(folder_path, ...)` | async | Parsa e indicizza un'intera cartella |
| `ingest_content_list(content_list, ...)` | async | Inserisce contenuto pre-parsato |
| `query(question, mode, vlm_enhanced)` | async | Query con risposta generata |
| `query_with_multimodal(question, multimodal_content, mode)` | async | Query con contesto multimodale aggiuntivo |
| `query_sync(question, mode)` | sync | Wrapper sincrono per nodi LangGraph |
| `ingest_sync(file_path)` | sync | Wrapper sincrono per ingestione |
| `rag` | property | Accesso diretto all'istanza RAGAnything |
| `settings` | property | Settings correnti |

---

## Layer Adapter

Gli adapter bridgano l'infrastruttura del progetto alle interfacce RAG-Anything/LightRAG:

### `create_llm_model_func()`

Wrappa `get_llm()` in una funzione async `(prompt, system_prompt, history) -> str` per RAG-Anything.

### `create_vision_model_func()`

Come sopra ma con supporto per immagini base64, messaggi multimodali, e fallback text-only.

### `create_embedding_func()`

Wrappa `get_embedding()` in un `LightRAG.EmbeddingFunc` async con `np.ndarray` output.

---

## Relazione con retrieval text-only

| Aspetto | `retrieval/` (text-only) | `retrieval/multimodal/` |
|---------|-------------------------|------------------------|
| Formati | Testo puro | PDF, immagini, tabelle, equazioni |
| Storage | Qdrant / PGVector | Filesystem locale (`./rag_storage`) |
| Indici | BM25 + HNSW + RRF | Knowledge graph (LightRAG) + vector |
| Query | `RetrieverPipeline.search()` | `MultimodalRetrieverPipeline.query()` |
| Embedding | Diretto (`BaseEmbedding`) | Via adapter (`create_embedding_func()`) |
| LLM | Via `get_llm()` | Via adapter (`create_llm_model_func()`) |

I due moduli sono complementari. Il modulo multimodale estende `Document` dal modulo text-only tramite `MultimodalDocument`.

Per la guida retrieval text-only vedi [Vector Storage e Retrieval](vector-storage.md).

---

## Variabili d'ambiente

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `RAGANYTHING_WORKING_DIR` | `./rag_storage` | Directory di lavoro |
| `DEFAULT_MODEL` | `llm` | Modello LLM nel proxy |
| `VISION_MODEL` | — | Modello vision (opzionale) |
| `GLMOCR_MODE` | `maas` | Modalita GLM-OCR: maas o selfhosted |
| `GLMOCR_API_KEY` / `ZHIPU_API_KEY` | — | API key per GLM-OCR cloud |
| `GLMOCR_HOST` | `localhost` | Host per GLM-OCR self-hosted |
| `GLMOCR_PORT` | `8080` | Porta per GLM-OCR self-hosted |

---

## Dipendenze Python

```bash
# Pipeline base (MinerU/Docling/PaddleOCR)
uv pip install -e ".[multimodal-rag]"

# Con GLM-OCR
uv pip install -e ".[multimodal-rag,glmocr]"
```

| Pacchetto | Ruolo |
|-----------|-------|
| `raganything` | Orchestratore RAG multimodale |
| `lightrag` | Knowledge graph + vector retrieval engine |
| `glmocr` | Parser OCR basato su GLM-4.1V (opzionale) |
