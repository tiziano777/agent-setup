# Getting Started

Guida completa per configurare l'ambiente e creare il primo agente.

## Prerequisiti

- **Python 3.11+** -- necessario per le type annotations moderne
- **Docker e Docker Compose** -- per il proxy LiteLLM
- **uv** (consigliato) -- gestore pacchetti veloce. Installazione: `curl -LsSf https://astral.sh/uv/install.sh | sh`

## 1. Configurazione API Key

Copia il template e inserisci le tue API key:

```bash
cp .env.template .env
```

Modifica `.env` con le chiavi dei provider che vuoi usare. Non servono tutte: il proxy ruota automaticamente tra quelli disponibili e salta quelli non configurati.

Elenco provider e dove ottenere le key:

| Provider | Variabile | Dove ottenerla |
|----------|-----------|---------------|
| Groq | `GROQ_API_KEY` | https://console.groq.com |
| Cerebras | `CEREBRAS_API_KEY` | https://cloud.cerebras.ai |
| Google AI Studio | `GOOGLE_API_KEY` | https://aistudio.google.com |
| NVIDIA NIM | `NVIDIA_API_KEY` | https://build.nvidia.com |
| Mistral | `MISTRAL_API_KEY` | https://console.mistral.ai |
| Mistral (Codestral) | `CODESTRAL_API_KEY` | https://console.mistral.ai |
| OpenRouter | `OPENROUTER_API_KEY` | https://openrouter.ai |
| Cohere | `COHERE_API_KEY` | https://dashboard.cohere.com |
| GitHub Models | `GITHUB_TOKEN` | https://github.com/settings/tokens |
| Cloudflare | `CLOUDFLARE_API_KEY` | https://dash.cloudflare.com |
| Vercel | `VERCEL_API_KEY` | https://vercel.com/account/tokens |
| OpenCode Zen | `OPENCODEZEN_API_KEY` | https://opencode.ai |

### Gestione Secrets

**Regola fondamentale:** I file `.env` contengono segreti e NON devono mai essere committati.

Il `.gitignore` protegge automaticamente tutti i file `.env*`:

```
.env           # Sviluppo locale
.env.docker    # Docker Compose produzione
.env.*         # Qualsiasi altra variante
```

Solo i template (`.env.template`, `.env.docker.template`) sono tracciati da git.

**Validazione:**

Dopo aver compilato `.env`, verifica che tutto sia configurato correttamente:

```bash
make env-check
```

Il comando controlla che almeno un provider LLM sia configurato e mostra un report.

**Per deployment Docker:**

```bash
cp .env.docker.template .env.docker
# Compila .env.docker con le API key di produzione
make prod-build
```

**Regole di sicurezza:**

1. **Mai committare** file `.env` -- il gitignore li esclude automaticamente
2. **Mai condividere** API key in chat, issue, o pull request
3. **Ruota le chiavi** se sospetti una compromissione
4. Per CI/CD, usa secrets del provider (GitHub Secrets, Vault, etc.)
5. Verifica sempre con `make env-check` dopo aver cambiato configurazione

## 2. Avvia il Proxy LLM

```bash
make build
```

Questo avvia l'intero ecosistema dev (LiteLLM proxy, Qdrant, PostgreSQL, Phoenix, Neo4j) sulla porta 4000 e altre porte. Per avviare solo moduli specifici, vedi `make help-modules`. Verifica che funzioni:

```bash
# Health check
make llm-proxy-health

# Test rapido del rotator
make llm-proxy-test

# Test di tutti i provider configurati
make test-all
```

Comandi utili per il proxy:

```bash
make llm-proxy-logs      # Log in tempo reale
make llm-proxy-restart   # Riavvia (utile dopo modifica proxy_config.yml)
make down                # Ferma l'ecosistema
```

## 3. Setup Ambiente Python

```bash
# Crea virtual environment con Python 3.11
uv venv .venv --python 3.11
source .venv/bin/activate

# Installa il progetto con dipendenze dev
uv pip install -e ".[dev]"

# (Opzionale) Installa moduli retrieval/RAG
uv pip install -e ".[retrieval,qdrant]"        # Embedding + Qdrant
# oppure
uv pip install -e ".[retrieval-all]"           # Tutto (Qdrant + pgvector + OpenAI + rerankers)
```

Alternativa senza uv (pip classico, richiede Python 3.11+ gia installato):

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pip install -e ".[retrieval-all]"              # Opzionale: moduli RAG
```

## 4. Verifica l'Installazione

```bash
# Esegui i test
make test

# Lista agenti disponibili
make list-agents

# Verifica la discovery
python -c "from src.agents import discover_agents; print(discover_agents())"
```

Output atteso:

```
['agent1']
```

## 5. Crea il Tuo Primo Agente

```bash
make new-agent name=researcher
```

Questo crea `src/agents/researcher/` con tutta la struttura pre-compilata. I file principali da personalizzare:

### `prompts/system.py` -- Definisci la personalita

```python
SYSTEM_PROMPT = (
    "You are a research assistant specialized in scientific papers. "
    "Provide accurate citations and summarize findings concisely."
)
```

### `nodes/example_node.py` -- Personalizza la logica

Il nodo `process` e il punto in cui l'agente fa il suo lavoro. Puoi rinominarlo, aggiungere nodi, o modificare la logica:

```python
from src.agents.researcher.states.state import AgentState
from src.agents.researcher.prompts.system import SYSTEM_PROMPT
from src.shared.llm import get_llm


def process(state: AgentState) -> dict:
    llm = get_llm()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}
```

### `tools/example_tool.py` -- Aggiungi tool

```python
from langchain_core.tools import tool


@tool
def search_papers(query: str) -> str:
    """Search scientific papers by keyword."""
    # Implementa la logica di ricerca
    return f"Found 3 papers about: {query}"
```

### `agent.py` -- Modifica il grafo

```python
from langgraph.graph import END, START, StateGraph
from src.agents.researcher.states.state import AgentState
from src.agents.researcher.nodes.example_node import process


def build_graph() -> StateGraph:
    builder = StateGraph(AgentState)
    builder.add_node("process", process)
    builder.add_edge(START, "process")
    builder.add_edge("process", END)
    return builder

graph = build_graph().compile()
```

### `states/state.py` -- Estendi lo stato

```python
from typing import Annotated
from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    # Aggiungi campi specifici:
    papers_found: list[str]
    search_query: str
```

## 6. Testa il Tuo Agente

```bash
# Test unitari
make test-agent name=researcher

# Test tutti gli agenti
make test
```

## 7. Usa l'Agente da Codice

```python
from src.agents.researcher.agent import graph

# Graph API
result = graph.invoke({
    "messages": [{"role": "user", "content": "Find papers about transformers"}]
})
print(result["messages"][-1].content)

# Functional API
from src.agents.researcher.pipelines.pipeline import workflow

result = workflow.invoke(
    {"messages": [{"role": "user", "content": "Find papers about transformers"}]},
    config={"configurable": {"thread_id": "session-1"}}
)
print(result["response"])
```

## 8. Documentazione Esterna (opzionale)

Per avere accesso alla documentazione ufficiale LangChain/LangGraph e alle skill di riferimento:

```bash
# Clone iniziale (una volta sola)
make external-setup

# Aggiorna alla versione piu recente
make external-update

# Verifica lo stato dei repos
make external-status
```

Dopo il clone, i documenti sono disponibili in:

- `external/docs/src/oss/langgraph/` -- Documentazione ufficiale LangGraph
- `external/docs/src/oss/langchain/` -- Documentazione ufficiale LangChain
- `external/docs/src/oss/deepagents/` -- Documentazione Deep Agents
- `external/langchain-skills/config/skills/` -- 11 skill con pattern e codice funzionante

## Prossimi Passi

- [Sviluppo Agenti](agent-development.md) -- guida approfondita su nodi, tool, stato, conditional routing
- [Pattern Multi-Agent](multi-agent.md) -- supervisor, swarm, indipendente
- [Vector Storage e Retrieval (RAG)](vector-storage.md) -- vector DB, embedding, ricerca ibrida, reranking
- [API Reference](api-reference.md) -- reference del modulo shared
