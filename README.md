# Agent Setup

Ambiente modulare per lo sviluppo di agenti LangGraph con rotazione automatica tra provider LLM gratuiti LiteLLM proxy.

## Caratteristiche

- **Modularita** - Ogni agente e un modulo Python autonomo con struttura standardizzata
- **Dual API** - Supporto sia Graph API (StateGraph) che Functional API (@entrypoint/@task)
- **Multi-Agent** - Pattern predefiniti: supervisor, swarm/p2p, indipendente
- **LLM Rotation** - 12 provider LLM configurati con fallback automatico e retry
- **Retrieval (RAG)** - Pipeline ibrida con vector DB (Qdrant, pgvector), BM25, RRF fusion e reranking
- **Multimodal RAG** - Pipeline RAG-Anything per PDF, immagini, tabelle, equazioni con GLM-OCR
- **Knowledge Graph** - Cognee per grafi di conoscenza con 14 tipi di ricerca (Qdrant + Neo4j)
- **Observability** - Tracing automatico con Arize Phoenix via OpenTelemetry (PostgreSQL backend)
- **Evaluation (Phoenix)** - LLM-as-Judge, evaluator built-in, batch runner con annotazioni Phoenix
- **Evaluation (DeepEval)** - Metriche RAG, safety, agent con BaseDeepEvaluator estensibile
- **Vulnerability Scanning** - Giskard per 9 categorie di vulnerabilita LLM
- **Scaffolding** - Nuovo agente in un comando: `make new-agent name=my_agent`
- **Registry** - Discovery automatica degli agenti a runtime

## Requisiti

- Python >= 3.11
- Docker e Docker Compose
- [uv](https://docs.astral.sh/uv/) (consigliato) oppure pip

## Quick Start

```bash
# 1. Clona e configura le API key
cp .env.template .env
# Compila .env con le tue API key (anche solo alcune)

# 2. Avvia il proxy LLM
make build

# 3. Verifica che il proxy funzioni
make llm-proxy-health

# 4. Installa le dipendenze Python
uv venv .venv --python 3.11
source .venv/bin/activate
uv pip install -e ".[dev]"

# 5. Verifica con i test
make test
```

## Struttura del Progetto

```
agent-setup/
├── .env.template              # Template API key per i provider
├── docker-compose.yml         # LiteLLM proxy + Qdrant + PostgreSQL + Phoenix + Neo4j
├── docker-compose.prod.yml    # Stack completo produzione (app + infra + Neo4j)
├── proxy_config.yml           # Configurazione 12 provider LLM
├── pyproject.toml             # Dipendenze e tool config
├── langgraph.json             # Entry point per deployment LangGraph
├── Makefile                   # Comandi proxy + agenti + sviluppo + k8s
│
├── src/
│   ├── shared/                # Utilities condivise
│   │   ├── llm.py             # Client LLM centralizzato (LiteLLM proxy)
│   │   ├── tracing.py         # Phoenix OTEL tracing (auto-instrumentation)
│   │   ├── types.py           # BaseAgentState, HandoffPayload
│   │   ├── memory.py          # Factory checkpointer + store
│   │   ├── registry.py        # Auto-discovery agenti
│   │   ├── orchestration.py   # Factory multi-agent
│   │   ├── retrieval/         # Pipeline RAG modulare
│   │   │   ├── embeddings/    # BaseEmbedding, SentenceTransformer, OpenAI
│   │   │   ├── vectorstores/  # BaseVectorStore, Qdrant, pgvector
│   │   │   ├── chunking/      # BaseChunker, size/sentence/structure
│   │   │   ├── indexes/       # BM25Index, VectorIndex (in-memory)
│   │   │   ├── rerankers/     # BaseReranker, LLM, CrossEncoder
│   │   │   ├── multimodal/    # RAG multimodale (RAGAnything + GLM-OCR)
│   │   │   ├── pipeline.py    # RetrieverPipeline (multi-index + RRF)
│   │   │   └── contextual.py  # Arricchimento chunk con LLM
│   │   ├── cognee_toolkit/    # Knowledge graph memory (Cognee + Neo4j)
│   │   ├── phoenix_eval/      # Evaluation toolkit (arize-phoenix-evals)
│   │   ├── deep_eval/         # Evaluation toolkit (deepeval)
│   │   └── giskard_vulnerability_eval/  # Vulnerability scanning (Giskard)
│   │
│   ├── agents/
│   │   ├── _template/         # Skeleton per nuovi agenti
│   │   └── agent1/            # Primo agente (generato da template)
│   │       ├── __init__.py    # Exports + setup_tracing() automatico
│   │       ├── agent.py       # Graph API entry point
│   │       ├── config/        # Configurazione agente
│   │       ├── nodes/         # Nodi del grafo
│   │       ├── tools/         # Tool LangChain
│   │       ├── prompts/       # System prompt e template
│   │       ├── states/        # Definizione stato (TypedDict)
│   │       ├── schemas/       # Pydantic models I/O
│   │       ├── pipelines/     # Functional API entry point
│   │       ├── scorers/       # Scorer per valutazione
│   │       ├── memory/        # Namespace long-term memory
│   │       ├── image/         # Diagrammi e visualizzazioni
│   │       └── tests/         # Test unitari
│   │
│   └── app/                   # Applicazione (Streamlit/FastAPI)
│
├── deploy/
│   ├── docker/
│   │   └── init-db.sql  # Init database phoenix + schema isolation
│   └── kubernetes/              # Manifesti K8s (infra + app + configmap)
│
└── docs/                      # Documentazione
    ├── getting-started.md     # Guida setup completa
    ├── architecture.md        # Architettura del sistema
    ├── agent-development.md   # Guida sviluppo agenti
    ├── multi-agent.md         # Pattern multi-agente
    ├── vector-storage.md      # RAG: vector DB, embedding, chunking, RRF
    ├── multimodal-rag.md      # RAG multimodale (PDF, immagini, tabelle)
    ├── cognee.md              # Knowledge graph memory (Cognee)
    ├── arize-phoenix.md       # Integrazione Phoenix (tracing + observability)
    ├── phoenix-eval.md        # Evaluation toolkit Phoenix
    ├── deep-eval.md           # Valutazione con DeepEval
    ├── giskard.md             # Vulnerability scanning (Giskard)
    ├── api-reference.md       # Reference modulo shared
    ├── deployment.md          # Guida deployment (Docker, K8s, Cloud)
    ├── makefile.md            # Reference comandi Makefile
    └── update-external-repos.md  # Gestione repo esterni
```

## Comandi Makefile

### Proxy LLM

| Comando | Descrizione |
|---------|-------------|
| `make build` | Avvia il proxy LiteLLM |
| `make down` | Ferma il proxy |
| `make llm-proxy-health` | Controlla lo stato del proxy |
| `make llm-proxy-logs` | Log in tempo reale |
| `make llm-proxy-restart` | Riavvia dopo modifica config |
| `make llm-proxy-test` | Test rapido del rotator |
| `make test-all` | Test di tutti i provider configurati |

### Gestione Agenti

| Comando | Descrizione |
|---------|-------------|
| `make new-agent name=X` | Crea un nuovo agente dal template |
| `make list-agents` | Lista agenti disponibili |

### Sviluppo

| Comando | Descrizione |
|---------|-------------|
| `make install` | Installa dipendenze in modalita dev |
| `make test` | Esegui tutti i test |
| `make test-agent name=X` | Test di un singolo agente |
| `make lint` | Lint con ruff |
| `make fmt` | Auto-format con ruff |

### Observability (Phoenix)

| Comando | Descrizione |
|---------|-------------|
| `make phoenix-logs` | Log Phoenix in tempo reale |
| `make test-phoenix` | Healthcheck Phoenix |
| `make k8s-logs-phoenix` | Log Phoenix in Kubernetes |
| `make k8s-port-forward-phoenix` | Phoenix UI su localhost:6006 via K8s |

Per la guida completa sull'integrazione Phoenix vedi [docs/arize-phoenix.md](docs/arize-phoenix.md).

### Kubernetes

| Comando | Descrizione |
|---------|-------------|
| `make k8s-apply-all` | Deploy completo via Kustomize |
| `make k8s-infra` | Deploy infrastruttura (LiteLLM + Qdrant + PostgreSQL + Phoenix) |
| `make k8s-app` | Deploy solo app |
| `make k8s-status` | Stato dei pod |
| `make k8s-destroy` | Elimina tutto il namespace |

## Provider LLM Configurati

| Provider | Modello | Note |
|----------|---------|------|
| Groq | llama-3.3-70b-versatile | - |
| Cerebras | qwen-3-235b | - |
| Google AI Studio | gemini-2.0-flash | - |
| NVIDIA NIM | llama-3.3-70b-instruct | - |
| Mistral | mistral-small-latest | - |
| Mistral | codestral-latest | Ottimizzato per codice |
| OpenRouter | deepseek-v3.2 | - |
| Cohere | command-r-v2 | - |
| GitHub Models | DeepSeek-V3 | Usa GITHUB_TOKEN |
| Cloudflare | llama-3.1-8b-instruct | - |
| Vercel AI Gateway | claude-opus-4.6 | - |
| OpenCode Zen | nemotron-3-super | Versione free |

Tutti i provider ruotano automaticamente sotto il nome unificato `model="llm"` con strategia `simple-shuffle`, 5 retry e fallback automatico.

## Documentazione

### Guide

- [Guida Setup Completa](docs/getting-started.md)
- [Architettura del Sistema](docs/architecture.md)
- [Sviluppo Agenti](docs/agent-development.md)
- [Pattern Multi-Agent](docs/multi-agent.md)
- [Guida Deployment](docs/deployment.md)
- [Comandi Makefile](docs/makefile.md)
- [Gestione Repository Esterni](docs/update-external-repos.md)

### Retrieval e Knowledge Graph

- [Vector Storage e Retrieval (RAG)](docs/vector-storage.md)
- [Multimodal RAG](docs/multimodal-rag.md)
- [Knowledge Graph Memory (Cognee)](docs/cognee.md)

### Observability e Valutazione

- [Integrazione Arize Phoenix](docs/arize-phoenix.md)
- [Phoenix Evaluation Toolkit](docs/phoenix-eval.md)
- [DeepEval Toolkit](docs/deep-eval.md)
- [Giskard Vulnerability Scanning](docs/giskard.md)

### Reference

- [API Reference](docs/api-reference.md)

## Dipendenze Principali

- [LangGraph](https://langchain-ai.github.io/langgraph/) - Framework per grafi agentici
- [LangChain](https://python.langchain.com/) - Interfacce model/tool
- [LiteLLM](https://docs.litellm.ai/) - Proxy multi-provider con API OpenAI-compatible
- [Arize Phoenix](https://docs.arize.com/phoenix) - LLM observability e tracing via OpenTelemetry
- [Pydantic](https://docs.pydantic.dev/) - Validazione schema I/O
- [Qdrant](https://qdrant.tech/) - Vector database ad alte prestazioni
- [pgvector](https://github.com/pgvector/pgvector) - Estensione vector search per PostgreSQL
- [sentence-transformers](https://www.sbert.net/) - Embedding locali e cross-encoder reranking
- [Cognee](https://github.com/topoteretes/cognee) - Knowledge graph memory e RAG
- [Neo4j](https://neo4j.com/) - Graph database per knowledge graph
- [DeepEval](https://docs.confident-ai.com/docs/) - Framework valutazione LLM
- [Giskard](https://docs.giskard.ai/) - Vulnerability scanning per LLM
- [RAGAnything](https://github.com/HKUDS/RAGAnything) - RAG multimodale
