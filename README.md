# Agent Setup

Ambiente modulare per lo sviluppo di agenti LangGraph con rotazione automatica tra provider LLM gratuiti LiteLLM proxy.

## Caratteristiche

- **Modularita** - Ogni agente e un modulo Python autonomo con struttura standardizzata
- **Dual API** - Supporto sia Graph API (StateGraph) che Functional API (@entrypoint/@task)
- **Multi-Agent** - Pattern predefiniti: supervisor, swarm/p2p, indipendente
- **LLM Rotation** - 12 provider LLM configurati con fallback automatico e retry
- **Retrieval (RAG)** - Pipeline ibrida con vector DB (Qdrant, pgvector), BM25, RRF fusion e reranking
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
├── docker-compose.yml         # LiteLLM proxy + Qdrant + PostgreSQL/pgvector
├── proxy_config.yml           # Configurazione 12 provider LLM
├── pyproject.toml             # Dipendenze e tool config
├── langgraph.json             # Entry point per deployment LangGraph
├── Makefile                   # Comandi proxy + agenti + sviluppo
│
├── src/
│   ├── shared/                # Utilities condivise
│   │   ├── llm.py             # Client LLM centralizzato (LiteLLM proxy)
│   │   ├── types.py           # BaseAgentState, HandoffPayload
│   │   ├── memory.py          # Factory checkpointer + store
│   │   ├── registry.py        # Auto-discovery agenti
│   │   ├── orchestration.py   # Factory multi-agent
│   │   └── retrieval/         # Pipeline RAG modulare
│   │       ├── embeddings/    # BaseEmbedding, SentenceTransformer, OpenAI
│   │       ├── vectorstores/  # BaseVectorStore, Qdrant, pgvector
│   │       ├── chunking/      # BaseChunker, size/sentence/structure
│   │       ├── indexes/       # BM25Index, VectorIndex (in-memory)
│   │       ├── rerankers/     # BaseReranker, LLM, CrossEncoder
│   │       ├── pipeline.py    # RetrieverPipeline (multi-index + RRF)
│   │       └── contextual.py  # Arricchimento chunk con LLM
│   │
│   ├── agents/
│   │   ├── _template/         # Skeleton per nuovi agenti
│   │   └── agent1/            # Primo agente (generato da template)
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
└── docs/                      # Documentazione
    ├── architecture.md        # Architettura del sistema
    ├── getting-started.md     # Guida setup completa
    ├── agent-development.md   # Guida sviluppo agenti
    ├── multi-agent.md         # Pattern multi-agente
    └── api-reference.md       # Reference modulo shared
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

- [Guida Setup Completa](docs/getting-started.md)
- [Architettura del Sistema](docs/architecture.md)
- [Sviluppo Agenti](docs/agent-development.md)
- [Pattern Multi-Agent](docs/multi-agent.md)
- [Vector Storage e Retrieval (RAG)](docs/vector-storage.md)
- [API Reference](docs/api-reference.md)

## Dipendenze Principali

- [LangGraph](https://langchain-ai.github.io/langgraph/) - Framework per grafi agentici
- [LangChain](https://python.langchain.com/) - Interfacce model/tool
- [LiteLLM](https://docs.litellm.ai/) - Proxy multi-provider con API OpenAI-compatible
- [Pydantic](https://docs.pydantic.dev/) - Validazione schema I/O
- [Qdrant](https://qdrant.tech/) - Vector database ad alte prestazioni
- [pgvector](https://github.com/pgvector/pgvector) - Estensione vector search per PostgreSQL
- [sentence-transformers](https://www.sbert.net/) - Embedding locali e cross-encoder reranking
