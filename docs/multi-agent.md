# Pattern Multi-Agent

Guida ai tre pattern di composizione multi-agente disponibili in `src/shared/orchestration.py`.

## Prerequisiti

Tutti i pattern richiedono che gli agenti siano registrati nel registry:

```python
from src.agents import discover_agents
from src.shared.registry import registry

discover_agents()  # Registra tutti gli agenti
```

## 1. Supervisor

Un agente centrale (il supervisor) riceve le richieste e decide quale agente worker attivare. I worker completano il task e restituiscono il controllo al supervisor.

```
         START
           |
           v
      [supervisor]  <-------+
       /    |    \          |
      v     v     v         |
  [agent1] [agent2] [agent3]
      \     |     /
       +----+----+
```

### Quando usarlo

- Task che richiedono specializzazione (es. uno traduce, uno analizza, uno scrive)
- Flussi dove serve un orchestratore che decide chi fa cosa
- Quando vuoi un unico punto di controllo

### Esempio

```python
from src.shared.orchestration import build_supervisor
from src.shared.registry import registry
from src.agents import discover_agents

discover_agents()

supervisor_graph = build_supervisor(
    agent_names=["researcher", "writer"],
    registry=registry,
    supervisor_model="llm",
    supervisor_prompt=(
        "You are a project manager. "
        "Use the researcher to gather information, "
        "then the writer to compose the final output."
    ),
)

result = supervisor_graph.invoke({
    "messages": [{"role": "user", "content": "Write a report about LLMs"}]
})
```

### Come funziona internamente

1. `build_supervisor()` crea un `StateGraph` con `MessagesState`
2. Il nodo `"supervisor"` e un `create_react_agent` con handoff tools
3. Per ogni worker, viene creato un `transfer_to_{name}` tool
4. Quando il supervisor chiama un transfer tool, il controllo passa al worker
5. Completato il worker, il flusso torna al supervisor via edge diretta
6. Il supervisor puo chiamare un altro worker o terminare

### Parametri

```python
build_supervisor(
    agent_names: list[str],          # Nomi agenti registrati
    registry: AgentRegistry,          # Istanza registry
    supervisor_model: str = "llm",    # Modello per il supervisor
    supervisor_prompt: str = "...",    # System prompt del supervisor
) -> CompiledGraph
```

## 2. Network (Swarm / P2P)

Ogni agente puo passare il controllo direttamente a qualsiasi altro agente nella rete. Non c'e orchestratore centrale.

```
      START
        |
        v
    [agent1] <----> [agent2]
        ^             ^
        |             |
        v             v
    [agent3] <----> [agent4]
```

### Quando usarlo

- Conversazioni collaborative tra agenti specializzati
- Flussi dove il prossimo step dipende dal contesto (non da un piano fisso)
- Quando ogni agente sa quando delegare e a chi

### Esempio

```python
from src.shared.orchestration import build_network
from src.shared.registry import registry
from src.agents import discover_agents
from src.agents.researcher.tools import search_web

discover_agents()

network_graph = build_network(
    agent_configs={
        "researcher": {
            "tools": [search_web],
            "prompt": "You research topics. Transfer to writer when done.",
        },
        "writer": {
            "tools": [],
            "prompt": "You write polished content based on research.",
        },
    },
    registry=registry,
)

result = network_graph.invoke({
    "messages": [{"role": "user", "content": "Write an article about AI safety"}]
})
```

### Come funziona internamente

1. `build_network()` crea un `StateGraph` con `MessagesState`
2. Per ogni agente, crea un `create_react_agent` con:
   - I tool custom dell'agente
   - Transfer tools per tutti gli altri agenti nella rete
3. Il flusso inizia dal primo agente nella lista
4. Ogni agente puo chiamare `transfer_to_{name}` per passare il controllo
5. La conversazione continua fino a quando un agente risponde senza trasferire

### Parametri

```python
build_network(
    agent_configs: dict[str, dict],   # {name: {"tools": [...], "prompt": "..."}}
    registry: AgentRegistry,           # Istanza registry
) -> CompiledGraph
```

Ogni entry di `agent_configs` accetta:
- `tools` (list): tool aggiuntivi specifici dell'agente
- `prompt` (str): system prompt dell'agente

## 3. Independent (Parallelo)

Tutti gli agenti eseguono in parallelo sullo stesso input. I risultati vengono accumulati nei messaggi.

```
          START
        /   |   \
       v    v    v
  [agent1] [agent2] [agent3]
       \    |    /
        v   v   v
           END
```

### Quando usarlo

- Raccogliere prospettive diverse sullo stesso problema
- Esecuzione parallela di task indipendenti
- Voting/consensus tra agenti

### Esempio

```python
from src.shared.orchestration import build_independent
from src.shared.registry import registry
from src.agents import discover_agents

discover_agents()

parallel_graph = build_independent(
    agent_names=["analyst", "critic", "synthesizer"],
    registry=registry,
)

result = parallel_graph.invoke({
    "messages": [{"role": "user", "content": "Evaluate this business plan"}]
})

# result["messages"] contiene le risposte di tutti e tre
```

### Come funziona internamente

1. `build_independent()` crea un `StateGraph` con `MessagesState`
2. Ogni agente viene aggiunto come nodo
3. Da `START`, viene creato un edge verso *ogni* agente (fan-out)
4. Da ogni agente, viene creato un edge verso `END` (fan-in)
5. LangGraph esegue tutti i nodi in parallelo
6. I messaggi vengono accumulati via `add_messages` reducer

### Parametri

```python
build_independent(
    agent_names: list[str],           # Nomi agenti registrati
    registry: AgentRegistry,           # Istanza registry
) -> CompiledGraph
```

## Handoff Tool

Alla base dei pattern supervisor e network c'e il concetto di handoff tool:

```python
from src.shared.orchestration import create_handoff_tool

# Crea un tool che trasferisce il controllo a "writer"
transfer_to_writer = create_handoff_tool(
    agent_name="writer",
    description="Transfer to the writer agent for content creation"
)
```

L'handoff tool usa `Command(goto=agent_name, graph=Command.PARENT)` per navigare nel grafo padre, passando il controllo all'agente target con il contesto dei messaggi.

## Combinare Pattern

I pattern possono essere combinati. Ad esempio, un supervisor che gestisce due team, ciascuno composto da agenti in rete:

```python
# Team 1: research network
research_network = build_network(
    agent_configs={
        "searcher": {"tools": [search_tool], "prompt": "..."},
        "analyzer": {"tools": [], "prompt": "..."},
    },
    registry=registry,
)

# Team 2: writing network
writing_network = build_network(
    agent_configs={
        "drafter": {"tools": [], "prompt": "..."},
        "editor": {"tools": [], "prompt": "..."},
    },
    registry=registry,
)

# Supervisor come grafo padre
# (richiede registrazione manuale dei sub-grafi come nodi)
```

## Confronto Pattern

| Aspetto | Supervisor | Network | Independent |
|---------|-----------|---------|-------------|
| Controllo | Centralizzato | Distribuito | Nessuno (parallelo) |
| Comunicazione | Hub-and-spoke | Peer-to-peer | Nessuna |
| Flessibilita | Media | Alta | Bassa |
| Determinismo | Alto | Basso | Alto |
| Uso tipico | Orchestrazione task | Conversazione collaborativa | Analisi multi-prospettiva |

## RAG nei Pattern Multi-Agent

Un agente RAG-enabled puo essere usato come worker in qualsiasi pattern multi-agent. Ad esempio, un supervisor che gestisce un agente di ricerca con knowledge base:

```python
from src.shared.orchestration import build_supervisor
from src.shared.registry import registry
from src.agents import discover_agents

discover_agents()

# L'agente "rag_researcher" ha un nodo `retrieve` nel suo grafo
# che usa src.shared.retrieval per cercare nella knowledge base
supervisor_graph = build_supervisor(
    agent_names=["rag_researcher", "writer"],
    registry=registry,
    supervisor_prompt=(
        "Use the rag_researcher to find relevant information, "
        "then the writer to compose the final response."
    ),
)
```

L'infrastruttura retrieval (`src/shared/retrieval/`) e condivisa tra tutti gli agenti: ogni worker puo accedere alla stessa knowledge base vettoriale (Qdrant, pgvector) tramite le factory functions. Vedi [Vector Storage e Retrieval](vector-storage.md) per i dettagli.
