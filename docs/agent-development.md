# Sviluppo Agenti

Guida approfondita per sviluppare agenti personalizzati: nodi, tool, stato, conditional routing, memory e testing.

## Struttura di un Agente

```
agent_n/
├── __init__.py          # Esporta graph + workflow
├── agent.py             # Graph API (StateGraph)
├── config/settings.py   # Dataclass configurazione
├── states/state.py      # TypedDict stato
├── nodes/               # Funzioni nodo
├── tools/               # @tool functions
├── prompts/system.py    # System prompt
├── schemas/io.py        # Pydantic models
├── pipelines/pipeline.py # Functional API
├── scorers/scorer.py    # Funzioni valutazione
├── memory/store.py      # Namespace memory
├── image/               # Asset visivi
└── tests/test_agent.py  # Test
```

## Definire lo Stato

Lo stato e il cuore dell'agente. Ogni nodo riceve lo stato corrente e ritorna un aggiornamento parziale.

```python
# states/state.py
from typing import Annotated
from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    # messages usa il reducer add_messages: le liste vengono concatenate
    messages: Annotated[list[AnyMessage], add_messages]

    # Campi custom (sovrascrittura diretta, no reducer)
    context: str
    iteration_count: int
    results: list[dict]
```

**Regola chiave**: `messages` usa il reducer `add_messages`, quindi ogni nodo ritorna nuovi messaggi da *aggiungere*. Gli altri campi vengono sovrascritti direttamente.

```python
# Un nodo che aggiorna lo stato
def my_node(state: AgentState) -> dict:
    return {
        "messages": [new_message],       # Viene AGGIUNTO alla lista
        "context": "nuovo contesto",     # Viene SOVRASCRITTO
        "iteration_count": state["iteration_count"] + 1,  # Manuale
    }
```

## Scrivere Nodi

Un nodo e una funzione Python che riceve lo stato e ritorna un dict di aggiornamento parziale.

```python
# nodes/analyze.py
from src.agents.my_agent.states.state import AgentState
from src.shared.llm import get_llm


def analyze(state: AgentState) -> dict:
    """Analizza l'input utente e produce un piano."""
    llm = get_llm()
    messages = state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}
```

### Nodo con Tool Calling

```python
# nodes/tool_caller.py
from src.agents.my_agent.states.state import AgentState
from src.agents.my_agent.tools import search_tool, calc_tool
from src.shared.llm import get_llm


def call_tools(state: AgentState) -> dict:
    """Chiama l'LLM con tool binding."""
    llm = get_llm()
    llm_with_tools = llm.bind_tools([search_tool, calc_tool])
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}
```

### Nodo di Validazione (Scorer)

```python
# nodes/validate.py
from src.agents.my_agent.states.state import AgentState
from src.agents.my_agent.scorers.scorer import relevance_score


def validate(state: AgentState) -> dict:
    """Valida la risposta e decide se riprovare."""
    last_msg = state["messages"][-1].content
    query = state["messages"][0].content
    score = relevance_score(query, last_msg)
    return {"score": score, "iteration_count": state["iteration_count"] + 1}
```

## Scrivere Tool

I tool sono funzioni decorate con `@tool` di LangChain. L'LLM puo decidere di chiamarli autonomamente.

```python
# tools/search.py
from langchain_core.tools import tool


@tool
def search_web(query: str) -> str:
    """Search the web for information about a topic."""
    # Implementa la logica
    return f"Results for: {query}"


@tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression."""
    try:
        result = eval(expression)  # In produzione usa un parser sicuro
        return str(result)
    except Exception as e:
        return f"Error: {e}"
```

Ricorda di esportare i tool nel `tools/__init__.py`:

```python
from src.agents.my_agent.tools.search import search_web, calculate

__all__ = ["search_web", "calculate"]
```

## Costruire il Grafo

### Grafo Lineare (Semplice)

```python
# agent.py
from langgraph.graph import END, START, StateGraph
from src.agents.my_agent.states.state import AgentState
from src.agents.my_agent.nodes.analyze import analyze

def build_graph() -> StateGraph:
    builder = StateGraph(AgentState)
    builder.add_node("analyze", analyze)
    builder.add_edge(START, "analyze")
    builder.add_edge("analyze", END)
    return builder

graph = build_graph().compile()
```

### Grafo con Conditional Routing

```python
# agent.py
from langgraph.graph import END, START, StateGraph
from src.agents.my_agent.states.state import AgentState
from src.agents.my_agent.nodes.analyze import analyze
from src.agents.my_agent.nodes.tool_caller import call_tools
from src.agents.my_agent.nodes.validate import validate


def should_use_tools(state: AgentState) -> str:
    """Routing condizionale: se l'LLM ha chiesto tool, vai a call_tools."""
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "call_tools"
    return "validate"


def should_retry(state: AgentState) -> str:
    """Se lo score e basso e non abbiamo superato il limite, riprova."""
    if state.get("score", 1.0) < 0.5 and state.get("iteration_count", 0) < 3:
        return "analyze"
    return "end"


def build_graph() -> StateGraph:
    builder = StateGraph(AgentState)

    builder.add_node("analyze", analyze)
    builder.add_node("call_tools", call_tools)
    builder.add_node("validate", validate)

    builder.add_edge(START, "analyze")
    builder.add_conditional_edges("analyze", should_use_tools)
    builder.add_edge("call_tools", "analyze")
    builder.add_conditional_edges("validate", should_retry, {"analyze": "analyze", "end": END})

    return builder

graph = build_graph().compile()
```

### Grafo con ToolNode (Esecuzione Automatica Tool)

```python
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from src.agents.my_agent.states.state import AgentState
from src.agents.my_agent.tools import search_web, calculate
from src.shared.llm import get_llm

tools = [search_web, calculate]


def agent_node(state: AgentState) -> dict:
    llm = get_llm().bind_tools(tools)
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


def build_graph() -> StateGraph:
    builder = StateGraph(AgentState)

    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(tools))

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")

    return builder

graph = build_graph().compile()
```

Questo pattern crea un loop ReAct: l'agente chiama tool, i tool vengono eseguiti, i risultati tornano all'agente.

## Prompt Engineering

### Prompt Statico

```python
# prompts/system.py
SYSTEM_PROMPT = (
    "You are a data analyst. Analyze data accurately. "
    "Always cite your sources and provide confidence levels."
)
```

### Prompt Dinamico

```python
# prompts/system.py
SYSTEM_PROMPT = "You are a specialized assistant."

def get_prompt(context: str = "", tools_available: list[str] = None) -> str:
    parts = [SYSTEM_PROMPT]
    if context:
        parts.append(f"\nContext:\n{context}")
    if tools_available:
        parts.append(f"\nTools available: {', '.join(tools_available)}")
    return "\n".join(parts)
```

## Configurazione Agente

```python
# config/settings.py
from dataclasses import dataclass, field

@dataclass
class AgentSettings:
    name: str = "my_agent"
    description: str = "A specialized agent"
    model: str = "llm"              # Usa il pool di rotazione
    temperature: float = 0.7
    max_tokens: int = 2048
    tags: list[str] = field(default_factory=lambda: ["analysis"])

settings = AgentSettings()
```

Usa nei nodi:

```python
from src.agents.my_agent.config.settings import settings
from src.shared.llm import get_llm

def process(state):
    llm = get_llm(model=settings.model, temperature=settings.temperature)
    ...
```

## Schema I/O

```python
# schemas/io.py
from pydantic import BaseModel, Field

class AgentInput(BaseModel):
    query: str = Field(..., description="The user query")
    thread_id: str | None = Field(None, description="Thread ID for persistence")
    max_iterations: int = Field(3, description="Max retry iterations")

class AgentOutput(BaseModel):
    response: str = Field(..., description="The agent's response")
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    sources: list[str] = Field(default_factory=list)
```

## Memory

### Short-term (Checkpointer)

Abilita la persistenza della conversazione tra invocazioni:

```python
# agent.py
from src.shared.memory import get_checkpointer

graph = build_graph().compile(checkpointer=get_checkpointer())

# Uso con thread_id
result = graph.invoke(
    {"messages": [{"role": "user", "content": "Ciao"}]},
    config={"configurable": {"thread_id": "user-123"}}
)
```

### Long-term (Store)

Per memoria che persiste tra thread diversi:

```python
# memory/store.py
def get_memory_namespace(user_id: str) -> tuple:
    return (user_id, "my_agent")
```

```python
# Uso nello store
from src.shared.memory import get_store
from src.agents.my_agent.memory import get_memory_namespace

store = get_store()
ns = get_memory_namespace("user-123")
store.put(ns, "preferences", {"language": "it", "style": "concise"})
```

## Testing

Ogni agente ha la sua directory `tests/`:

```python
# tests/test_agent.py
from src.agents.my_agent.agent import graph, build_graph
from src.agents.my_agent.states.state import AgentState


class TestGraph:
    def test_compiles(self):
        assert graph is not None

    def test_has_required_nodes(self):
        builder = build_graph()
        assert "analyze" in builder.nodes
        assert "validate" in builder.nodes

    def test_state_schema(self):
        assert "messages" in AgentState.__annotations__
        assert "context" in AgentState.__annotations__


class TestNodes:
    def test_analyze_returns_messages(self):
        # Mock del nodo con stato fittizio
        from src.agents.my_agent.nodes.analyze import analyze
        state = {"messages": [{"role": "user", "content": "test"}]}
        # Nota: questo richiede il proxy attivo o un mock dell'LLM
```

Esegui:

```bash
make test-agent name=my_agent
```

## Checklist Nuovo Agente

1. `make new-agent name=my_agent`
2. Modifica `prompts/system.py` -- definisci la personalita
3. Modifica `states/state.py` -- aggiungi campi custom allo stato
4. Scrivi nodi in `nodes/` -- logica di ogni step
5. Scrivi tool in `tools/` -- strumenti per l'agente
6. Modifica `agent.py` -- componi il grafo con nodi e edge
7. Modifica `schemas/io.py` -- definisci schema input/output
8. Scrivi test in `tests/` -- verifica struttura e logica
9. `make test-agent name=my_agent` -- verifica che tutto funzioni
10. Opzionale: aggiungi entry in `langgraph.json` per deployment

## Agente RAG (con Retrieval)

Per creare un agente che usa la knowledge base vettoriale, combina il retrieval con il pattern standard.

### 1. Stato con contesto

```python
# states/state.py
from src.shared.types import BaseAgentState

class RAGAgentState(BaseAgentState):
    context: str           # Documenti recuperati
    sources: list[str]     # ID dei documenti usati
```

### 2. Nodo di retrieval

```python
# nodes/retrieve.py
from src.agents.my_rag_agent.states.state import RAGAgentState
from src.shared.retrieval import get_retriever

def retrieve(state: RAGAgentState) -> dict:
    query = state["messages"][-1].content
    retriever = get_retriever()
    results = retriever.search(query, k=5)
    context = "\n\n".join(doc["content"] for doc in results)
    sources = [doc["id"] for doc in results]
    return {"context": context, "sources": sources}
```

### 3. Nodo di generazione con contesto

```python
# nodes/generate.py
from src.agents.my_rag_agent.states.state import RAGAgentState
from src.agents.my_rag_agent.prompts.system import SYSTEM_PROMPT
from src.shared.llm import get_llm

def generate(state: RAGAgentState) -> dict:
    llm = get_llm()
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Contesto dalla knowledge base:\n{state['context']}\n\n"
        f"Rispondi basandoti sul contesto fornito."
    )
    messages = [{"role": "system", "content": prompt}] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}
```

### 4. Grafo RAG

```python
# agent.py
from langgraph.graph import END, START, StateGraph
from src.agents.my_rag_agent.states.state import RAGAgentState
from src.agents.my_rag_agent.nodes.retrieve import retrieve
from src.agents.my_rag_agent.nodes.generate import generate

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

### 5. Retrieval come tool (alternativa)

Se preferisci che sia l'LLM a decidere quando cercare:

```python
# tools/search.py
from langchain_core.tools import tool
from src.shared.retrieval import get_retriever

@tool
def search_knowledge_base(query: str) -> str:
    """Cerca nella knowledge base e ritorna i documenti piu rilevanti."""
    retriever = get_retriever()
    results = retriever.search(query, k=3)
    return "\n\n---\n\n".join(doc["content"] for doc in results)
```

Poi usa il pattern ToolNode descritto sopra per creare un loop ReAct con ricerca automatica.

Per la guida completa su embedding, vector stores, chunking e pipeline vedi [Vector Storage e Retrieval](vector-storage.md).
