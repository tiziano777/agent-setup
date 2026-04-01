# Guidance Structured Generation Toolkit

Toolkit per la generazione strutturata e vincolata di testo con agenti LLM. Costruito su `guidance-ai/guidance`, tutte le chiamate LLM passano per il proxy LiteLLM via `guidance.models.OpenAI`. Supporta vincoli JSON schema, regex, selezione da opzioni fisse e grammatiche context-free (CFG).

## Indice

- [Architettura](#architettura)
- [File del modulo](#file-del-modulo)
- [Configurazione](#configurazione)
- [Quick Start](#quick-start)
- [API Programs](#api-programs)
- [API Tools](#api-tools)
- [API Nodes](#api-nodes)
- [Grammatiche personalizzate](#grammatiche-personalizzate)
- [CFG e grammatiche parametriche](#cfg-e-grammatiche-parametriche)
- [Variabili d'ambiente](#variabili-dambiente)
- [Dipendenze Python](#dipendenze-python)

---

## Architettura

```
┌──────────────────────────────────────────────┐
│  LangGraph Agent / StateGraph / Pipeline     │
└───────────────────┬──────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────┐
│  guidance_toolkit/                           │
│                                              │
│  programs.py     ← 6 programmi built-in      │
│  tools.py        ← 3 @tool LangGraph         │
│  nodes.py        ← 2 node factory            │
│  llm_bridge.py   ← get_guidance_model()      │
│  config.py       ← GuidanceSettings          │
└───────────────────┬──────────────────────────┘
                    │
                    ▼
              LiteLLM Proxy (:4000)
              via guidance.models.OpenAI(base_url=...)
```

**Scelte architetturali:**

- **LLM via proxy**: `get_guidance_model()` crea un `guidance.models.OpenAI` con `base_url` del proxy LiteLLM per instradare tutte le chiamate tramite il pool di provider.
- **Funzioni standalone**: I programmi sono funzioni pure, non metodi di una classe. La generazione vincolata e stateless — ogni chiamata parte da un modello fresco.
- **Tools con parametri stringa**: I tools LangGraph usano parametri stringa (non tipi complessi) per massima affidabilita con il tool calling degli LLM.
- **Nodi StateGraph**: I node factory seguono il pattern `(state: dict) -> dict` con partial state update, compatibili con qualsiasi `AgentState` che ha una chiave `messages`.
- **Token fast-forwarding**: Quando i vincoli grammaticali rendono deterministici i token successivi, guidance li inserisce direttamente senza forward pass del modello, riducendo latenza e costi.

---

## File del modulo

```
src/shared/guidance_toolkit/
├── __init__.py       # Public API con lazy re-exports
├── config.py         # GuidanceSettings + setup_guidance()
├── llm_bridge.py     # get_guidance_model() → guidance.models.OpenAI via proxy
├── programs.py       # 4 programmi: structured_json, constrained_select, regex_generate, grammar_generate
├── tools.py          # get_guidance_tools() → [guidance_json_generate, guidance_select, guidance_regex_generate]
└── nodes.py          # create_guidance_structured_node(), create_guidance_select_node()
```

| File | Responsabilita |
|------|----------------|
| `config.py` | `GuidanceSettings` dataclass con env var defaults, `setup_guidance()` idempotente, guarded import |
| `llm_bridge.py` | Factory `get_guidance_model()` con `@lru_cache` che crea modelli guidance via proxy |
| `programs.py` | 6 funzioni di generazione vincolata: JSON schema, select, regex, grammar custom, cfg_generate, build_cfg_grammar |
| `tools.py` | Factory `get_guidance_tools()` che restituisce 3 tools `@tool` per agenti LangGraph |
| `nodes.py` | 2 node factory per `StateGraph`: output strutturato e selezione vincolata |

---

## Configurazione

### `GuidanceSettings`

```python
from src.shared.guidance_toolkit import GuidanceSettings

settings = GuidanceSettings(
    default_model="llm",                          # modello nel proxy
    litellm_base_url="http://localhost:4000/v1",
    default_temperature=0.7,
)
```

| Campo | Default | Env Var | Descrizione |
|-------|---------|---------|-------------|
| `litellm_base_url` | `http://localhost:4000/v1` | `LITELLM_BASE_URL` | URL proxy LiteLLM |
| `default_model` | `"llm"` | `DEFAULT_MODEL` | Modello nel proxy |
| `api_key` | `"sk-not-needed"` | `OPENAI_API_KEY` | API key (il proxy gestisce l'auth) |
| `default_temperature` | `0.7` | — | Temperatura di sampling |
| `default_max_tokens` | `2048` | — | Max token per generazione |

### `setup_guidance()`

```python
from src.shared.guidance_toolkit.config import setup_guidance

setup_guidance()  # auto-config da env vars
```

---

## Quick Start

### Uso programmatico

```python
from pydantic import BaseModel
from src.shared.guidance_toolkit import structured_json, constrained_select, regex_generate

# 1. JSON vincolato a schema Pydantic
class Person(BaseModel):
    name: str
    age: int
    city: str

result = structured_json(Person, "Extract: John is 30, lives in Rome")
# {"name": "John", "age": 30, "city": "Rome"}

# 2. Selezione vincolata
sentiment = constrained_select(
    ["positive", "negative", "neutral"],
    "The movie was absolutely fantastic!",
)
# "positive"

# 3. Generazione con regex
code = regex_generate(r"[A-Z]{3}-\d{4}", "Generate a product code for a laptop")
# "LAP-2847"
```

### Come tools LangGraph

```python
from langgraph.prebuilt import create_react_agent
from src.shared.llm import get_llm
from src.shared.guidance_toolkit import get_guidance_tools
from src.shared.sandbox import get_sandbox_tools

tools = get_guidance_tools() + get_sandbox_tools()
agent = create_react_agent(get_llm(), tools)

result = agent.invoke({"messages": [("user", "Classify this as positive/negative: Great job!")]})
```

### Come nodi StateGraph

```python
from langgraph.graph import END, START, StateGraph
from src.shared.guidance_toolkit import create_guidance_structured_node, create_guidance_select_node

builder = StateGraph(AgentState)
builder.add_node("classify", create_guidance_select_node(
    ["question", "command", "chitchat"],
    system_prompt="Classifica l'intento dell'utente.",
))
builder.add_node("extract", create_guidance_structured_node(PersonSchema))
builder.add_edge(START, "classify")
```

---

## API Programs

### `structured_json(schema, prompt, **kwargs)`

Genera JSON vincolato a uno schema Pydantic usando `guidance.json(schema=...)`.

```python
from pydantic import BaseModel, Field
from src.shared.guidance_toolkit import structured_json

class BloodPressure(BaseModel):
    systolic: int = Field(gt=60, le=200)
    diastolic: int = Field(gt=30, le=130)
    location: str = Field(max_length=50)

result = structured_json(
    BloodPressure,
    "Report the patient's blood pressure: 120/80 from left arm",
    system_prompt="You are a medical assistant.",
)
```

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `schema` | `type[BaseModel]` | — | Classe Pydantic per il vincolo JSON |
| `prompt` | `str` | — | Prompt utente |
| `model` | `guidance.Model` | `None` | Modello guidance (fallback a `get_guidance_model()`) |
| `temperature` | `float` | `None` | Temperatura di sampling |
| `system_prompt` | `str` | `None` | System prompt opzionale |
| `capture_name` | `str` | `"json_output"` | Nome della cattura nel programma guidance |

### `constrained_select(options, prompt, **kwargs)`

Forza la selezione esatta di un'opzione dalla lista.

```python
from src.shared.guidance_toolkit import constrained_select

answer = constrained_select(["A", "B", "C", "D"], "The capital of France is: ")
```

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `options` | `list[str]` | — | Lista di valori ammessi |
| `prompt` | `str` | — | Prompt utente |
| `model` | `guidance.Model` | `None` | Modello guidance |
| `temperature` | `float` | `None` | Temperatura |
| `system_prompt` | `str` | `None` | System prompt |
| `capture_name` | `str` | `"selection"` | Nome della cattura |

### `regex_generate(pattern, prompt, **kwargs)`

Genera testo garantito a matchare un'espressione regolare.

```python
from src.shared.guidance_toolkit import regex_generate

email = regex_generate(r"[a-z]+@[a-z]+\.[a-z]{2,3}", "Generate an email for John")
# "john@example.com"

date = regex_generate(r"\d{4}-\d{2}-\d{2}", "Today's date is")
# "2024-03-15"
```

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `pattern` | `str` | — | Regex che l'output deve matchare |
| `prompt` | `str` | — | Prompt utente |
| `max_tokens` | `int` | `256` | Max token da generare |
| `model` | `guidance.Model` | `None` | Modello guidance |
| `temperature` | `float` | `None` | Temperatura |
| `system_prompt` | `str` | `None` | System prompt |
| `capture_name` | `str` | `"regex_output"` | Nome della cattura |

### `grammar_generate(grammar_fn, prompt, **kwargs)`

Genera testo usando una funzione grammatica `@guidance` personalizzata.

```python
from guidance import gen, guidance, select
from src.shared.guidance_toolkit import grammar_generate

@guidance(stateless=True)
def sentiment_with_reason(lm):
    lm += "Sentiment: "
    lm += select(["positive", "negative", "neutral"], name="sentiment")
    lm += "\nReason: "
    lm += gen(name="reason", max_tokens=50)
    return lm

result = grammar_generate(sentiment_with_reason, "Analyze: Great product!")
```

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `grammar_fn` | `Callable` | — | Funzione `@guidance` |
| `prompt` | `str` | — | Prompt utente |
| `model` | `guidance.Model` | `None` | Modello guidance |
| `temperature` | `float` | `None` | Temperatura |
| `system_prompt` | `str` | `None` | System prompt |
| `capture_name` | `str` | `"grammar_output"` | Nome della cattura |
| `**grammar_kwargs` | `Any` | — | Args passati alla funzione grammar |

---

## API Tools

### `get_guidance_tools(settings=None)`

Restituisce 3 tools LangGraph pronti per `create_react_agent()`:

| Tool | Parametri | Descrizione |
|------|-----------|-------------|
| `guidance_json_generate` | `json_schema_description: str`, `prompt: str` | Genera JSON strutturato da una descrizione dello schema |
| `guidance_select` | `options: str` (comma-separated), `prompt: str` | Seleziona una sola opzione dalla lista |
| `guidance_regex_generate` | `pattern: str`, `prompt: str` | Genera testo che matcha la regex |

```python
from src.shared.guidance_toolkit import get_guidance_tools

tools = get_guidance_tools()

# Aggiungere a un agente esistente
from src.shared.sandbox import get_sandbox_tools
all_tools = get_guidance_tools() + get_sandbox_tools()
```

---

## API Nodes

### `create_guidance_structured_node(schema, **kwargs)`

Crea un nodo StateGraph che genera JSON vincolato dall'ultimo messaggio.

```python
from src.shared.guidance_toolkit import create_guidance_structured_node

node = create_guidance_structured_node(
    PersonSchema,
    result_key="guidance_output",    # chiave nello state per il risultato
    system_prompt="Extract entities.",
)
builder.add_node("extract", node)
```

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `schema` | `type[BaseModel]` | — | Schema Pydantic per il vincolo |
| `query_key` | `str` | `"messages"` | Chiave state da cui leggere la query |
| `result_key` | `str` | `"guidance_output"` | Chiave state dove scrivere il risultato |
| `system_prompt` | `str` | `None` | System prompt |
| `temperature` | `float` | `None` | Temperatura |

### `create_guidance_select_node(options, **kwargs)`

Crea un nodo StateGraph che forza la selezione da una lista.

```python
from src.shared.guidance_toolkit import create_guidance_select_node

node = create_guidance_select_node(
    ["question", "command", "chitchat"],
    result_key="guidance_selection",
    system_prompt="Classify user intent.",
)
builder.add_node("classify", node)
```

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `options` | `list[str]` | — | Lista di valori ammessi |
| `query_key` | `str` | `"messages"` | Chiave state da cui leggere la query |
| `result_key` | `str` | `"guidance_selection"` | Chiave state dove scrivere il risultato |
| `system_prompt` | `str` | `None` | System prompt |
| `temperature` | `float` | `None` | Temperatura |

---

## Grammatiche personalizzate

Guidance supporta la composizione di grammatiche context-free tramite il decoratore `@guidance`. Puoi creare programmi personalizzati e usarli con `grammar_generate()`.

### Esempio: lista strutturata

```python
from guidance import guidance, gen, select
from src.shared.guidance_toolkit import grammar_generate

@guidance(stateless=True)
def item_list(lm, categories):
    for i in range(3):
        lm += f"\n{i+1}. Category: "
        lm += select(categories, name=f"cat_{i}")
        lm += " - Item: "
        lm += gen(name=f"item_{i}", max_tokens=20, regex=r"[A-Za-z ]+")
    return lm

result = grammar_generate(
    item_list,
    "Generate a shopping list",
    categories=["Frutta", "Verdura", "Latticini"],
)
```

### Esempio: HTML vincolato

```python
from guidance import guidance, gen, select
from guidance.library import one_or_more, capture

@guidance(stateless=True)
def html_heading(lm, level=1):
    tag = f"h{level}"
    lm += f"<{tag}>"
    lm += gen(name="heading_text", max_tokens=30, regex=r"[A-Za-z0-9 ]+")
    lm += f"</{tag}>"
    return lm
```

### Principi chiave

1. **`@guidance(stateless=True)`** per funzioni composibili (grammatiche pure)
2. **`@guidance`** per funzioni che modificano lo stato del modello
3. **`lm += ...`** aggiunge al programma (il modello e immutabile, restituisce copie)
4. **`lm["nome"]`** recupera le catture con nome
5. Le funzioni grammatica si compongono per nesting: una `@guidance` function puo chiamare altre

---

## CFG e grammatiche parametriche

Guidance supporta grammatiche context-free (CFG) piu potenti delle semplici regex. Le CFG permettono vincoli annidati, ripetizioni e composizione di sotto-grammatiche. Il token fast-forwarding e automatico: quando i vincoli rendono deterministici i prossimi token, guidance li inserisce senza chiamare il LLM.

### `cfg_generate(grammar_fn, prompt, **kwargs)`

Come `grammar_generate` ma restituisce un **dict** con tutte le catture nominali.

```python
from guidance import guidance, gen, select
from src.shared.guidance_toolkit import cfg_generate

@guidance(stateless=True)
def product_entry(lm):
    lm += "Category: "
    lm += select(["Electronics", "Books", "Food"], name="category")
    lm += " | Item: "
    lm += gen(name="item", max_tokens=20, regex=r"[A-Za-z0-9 ]+")
    return lm

result = cfg_generate(product_entry, "Create a product entry")
# {"category": "Electronics", "item": "Laptop Pro 15"}
```

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `grammar_fn` | `Callable` | — | Funzione `@guidance(stateless=True)` che definisce la CFG |
| `prompt` | `str` | — | Prompt utente |
| `model` | `guidance.Model` | `None` | Modello guidance |
| `temperature` | `float` | `None` | Temperatura |
| `system_prompt` | `str` | `None` | System prompt |
| `capture_names` | `list[str]` | `None` | Catture da estrarre (auto-detect se `None`) |
| `**grammar_kwargs` | `Any` | — | Args passati alla funzione grammar |

### `build_cfg_grammar(steps)`

Builder dichiarativo — crea una grammatica `@guidance(stateless=True)` da una lista di step senza scrivere codice guidance. I token literal vengono fast-forwarded automaticamente.

```python
from src.shared.guidance_toolkit import build_cfg_grammar, cfg_generate

grammar = build_cfg_grammar([
    {"type": "literal", "text": "Type: "},
    {"type": "select", "name": "type", "options": ["bug", "feature", "task"]},
    {"type": "literal", "text": " | Priority: "},
    {"type": "select", "name": "priority", "options": ["low", "medium", "high"]},
    {"type": "literal", "text": " | Title: "},
    {"type": "gen", "name": "title", "max_tokens": 30},
])

result = cfg_generate(grammar, "Create a ticket")
# {"type": "bug", "priority": "high", "title": "Fix login crash"}
```

#### Step supportati

| type | parametri | primitiva guidance |
|------|-----------|-------------------|
| `"literal"` | `text` | `lm += text` (fast-forwarded) |
| `"gen"` | `name`, `max_tokens`, `regex` (tutti opzionali) | `gen()` |
| `"select"` | `name`, `options` | `select()` |
| `"one_or_more"` | `body` (step o lista step) | `guidance.library.one_or_more()` |
| `"capture"` | `name`, `body` (step o lista step) | `guidance.library.capture()` |
| `"with_temperature"` | `temperature`, `body` (step o lista step) | `guidance.library.with_temperature()` |

#### Esempio con primitive avanzate

```python
grammar = build_cfg_grammar([
    {"type": "one_or_more", "body": [
        {"type": "literal", "text": "- "},
        {"type": "gen", "name": None, "max_tokens": 20, "regex": r"[A-Za-z ]+"},
        {"type": "literal", "text": "\n"},
    ]},
])
```

---

## Variabili d'ambiente

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `LITELLM_BASE_URL` | `http://localhost:4000/v1` | URL proxy LiteLLM |
| `DEFAULT_MODEL` | `llm` | Modello LLM nel proxy |
| `OPENAI_API_KEY` | `sk-not-needed` | API key (il proxy gestisce l'autenticazione) |

---

## Dipendenze Python

```bash
uv pip install -e ".[guidance]"
```

| Pacchetto | Ruolo |
|-----------|-------|
| `guidance` | Generazione vincolata con grammatiche, regex, JSON schema, select |
