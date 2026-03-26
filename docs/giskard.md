# Vulnerability Scanning (Giskard)

Toolkit per vulnerability scanning degli agenti LLM, basato su Giskard. Rileva 9 categorie di vulnerabilita: prompt injection, contenuti dannosi, sycophancy, stereotipi e altro. Tutte le chiamate LLM passano per il proxy LiteLLM.

## Indice

- [Architettura](#architettura)
- [File del modulo](#file-del-modulo)
- [Configurazione](#configurazione)
- [Quick Start](#quick-start)
- [9 Categorie di vulnerabilita](#9-categorie-di-vulnerabilita)
- [Preset di detector](#preset-di-detector)
- [Model wrapping](#model-wrapping)
- [VulnerabilityScanner](#vulnerabilityscanner)
- [ScanResult](#scanresult)
- [Convenience functions](#convenience-functions)
- [Standalone script](#standalone-script)
- [Variabili d'ambiente](#variabili-dambiente)
- [Dipendenze Python](#dipendenze-python)

---

## Architettura

```
┌──────────────────────────────────────────────┐
│  Agent / predict_fn / LangGraph graph        │
└───────────────────┬──────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────┐
│  VulnerabilityScanner                        │
│                                              │
│  from_predict_fn()  / from_langgraph()       │
│          │                                   │
│          ▼                                   │
│  giskard.Model  →  giskard.scan()            │
│                    (genera probe input,       │
│                     chiama il modello,        │
│                     analizza le risposte)     │
└───────────────────┬──────────────────────────┘
                    │
                    ▼
              LiteLLM Proxy
              :4000
```

**Scelte architetturali:**

- **LLM via proxy**: Giskard usa `litellm` internamente. Configuriamo `OPENAI_API_BASE` per instradare tutto tramite il proxy con il prefisso `openai/`.
- **Toolkit compatto**: 2 soli file — un `__init__.py` per i re-export e `scanner.py` per tutto il resto.
- **Nessun database**: Giskard e puramente computazionale, non richiede storage esterno.

---

## File del modulo

```
src/shared/giskard_vulnerability_eval/
├── __init__.py    # Re-export di tutte le API pubbliche
└── scanner.py     # LLM bridge, model wrappers, scanner, detector enum
```

---

## Configurazione

### `configure_giskard_llm()`

Configura Giskard per usare il proxy LiteLLM (chiamata automaticamente al primo uso):

```python
from src.shared.giskard_vulnerability_eval import configure_giskard_llm

configure_giskard_llm()  # usa env vars
configure_giskard_llm(model="llm", base_url="http://localhost:4000/v1")
```

| Parametro | Default | Env Var | Descrizione |
|-----------|---------|---------|-------------|
| `model` | `"llm"` | `DEFAULT_MODEL` | Modello nel proxy |
| `base_url` | `http://localhost:4000/v1` | `LITELLM_BASE_URL` | URL proxy LiteLLM |

---

## Quick Start

### Da una predict function

```python
import pandas as pd
from src.shared.giskard_vulnerability_eval import VulnerabilityScanner
from src.shared.llm import get_llm

def my_predict(df: pd.DataFrame) -> list[str]:
    llm = get_llm()
    return [llm.invoke(row["question"]).content for _, row in df.iterrows()]

scanner = VulnerabilityScanner.from_predict_fn(
    my_predict,
    name="My Agent",
    description="Un chatbot per assistenza clienti",
)
result = scanner.scan()
print(f"Vulnerabilita trovate: {result.issues_found}")
```

### Da un LangGraph graph

```python
from src.shared.giskard_vulnerability_eval import VulnerabilityScanner

# graph = build_graph().compile()  # il tuo grafo compilato
scanner = VulnerabilityScanner.from_langgraph(
    graph,
    name="agent1",
    description="Agente per rispondere a domande tecniche",
)
result = scanner.scan(only=["prompt_injection", "harmfulness"])
```

### Scan selettivo con report HTML

```python
result = scanner.scan(
    only=["prompt_injection", "information_disclosure"],
    output_html="report.html",
)
```

---

## 9 Categorie di vulnerabilita

```python
from src.shared.giskard_vulnerability_eval import DetectorTag
```

| Tag | Descrizione |
|-----|-------------|
| `prompt_injection` | Iniezione di istruzioni malevole nel prompt |
| `harmfulness` | Generazione di contenuti dannosi o pericolosi |
| `stereotypes` | Risposte con stereotipi o bias |
| `sycophancy` | Eccessiva compiacenza verso l'utente |
| `information_disclosure` | Rivelazione di informazioni sensibili (system prompt, dati interni) |
| `control_chars_injection` | Iniezione di caratteri di controllo |
| `faithfulness` | Risposte non fedeli al contesto fornito (RAG) |
| `implausable_outputs` | Risposte implausibili o inventate |
| `output_formatting` | Problemi di formato nell'output |

---

## Preset di detector

```python
from src.shared.giskard_vulnerability_eval import (
    ALL_DETECTORS,
    SECURITY_DETECTORS,
    RAG_DETECTORS,
)

ALL_DETECTORS       # Tutti e 9 i detector
SECURITY_DETECTORS  # ["prompt_injection", "control_chars_injection",
                    #  "information_disclosure", "harmfulness"]
RAG_DETECTORS       # ["faithfulness", "sycophancy", "implausable_outputs"]
```

Utilizzo:

```python
result = scanner.scan(only=SECURITY_DETECTORS)
```

---

## Model wrapping

### `wrap_predict_fn()`

Wrappa una funzione predittiva come `giskard.Model`:

```python
from src.shared.giskard_vulnerability_eval import wrap_predict_fn

model = wrap_predict_fn(
    my_predict,
    name="My Agent",
    description="Customer support bot",
    feature_names=["question"],  # default
)
```

### `wrap_langgraph_agent()`

Wrappa un grafo LangGraph compilato come `giskard.Model`:

```python
from src.shared.giskard_vulnerability_eval import wrap_langgraph_agent

model = wrap_langgraph_agent(
    graph,
    name="LangGraph Agent",
    description="A LangGraph agent",
    input_key="question",  # default
)
```

---

## VulnerabilityScanner

Classe principale per eseguire scan di vulnerabilita:

```python
class VulnerabilityScanner:
    @classmethod
    def from_predict_fn(cls, predict_fn, *, name, description, feature_names=None)
    @classmethod
    def from_langgraph(cls, graph, *, name, description, input_key="question")
    def set_model(self, model)       # per giskard.Model pre-costruiti
    def scan(self, *, only=None, dataset=None, output_html=None) -> ScanResult
    @property
    def last_result(self) -> ScanResult | None
```

---

## ScanResult

```python
@dataclass
class ScanResult:
    raw_results: Any                       # Risultati giskard grezzi
    issues_found: int                      # Numero totale di problemi
    issues_by_detector: dict[str, int]     # Problemi per detector
    html_path: str | None                  # Path report HTML (se generato)

    @property
    def has_vulnerabilities(self) -> bool
    def to_html(self, path: str) -> str
    def generate_test_suite(self, suite_name: str) -> Any
    def summary(self) -> dict[str, Any]
```

---

## Convenience functions

```python
from src.shared.giskard_vulnerability_eval import scan_model, scan_model_selective

# Scan completo (tutti i detector)
result = scan_model(giskard_model, output_html="report.html")

# Scan selettivo
result = scan_model_selective(giskard_model, ["prompt_injection", "harmfulness"])
```

---

## Standalone script

Esegui uno scan di demo direttamente:

```bash
python -m src.shared.giskard_vulnerability_eval.scanner
```

Genera automaticamente un `vulnerability_report.html` con i risultati.

---

## Variabili d'ambiente

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `DEFAULT_MODEL` | `llm` | Modello LLM nel proxy |
| `LITELLM_BASE_URL` | `http://localhost:4000/v1` | URL proxy LiteLLM |

---

## Dipendenze Python

```bash
uv pip install -e ".[giskard]"
```

| Pacchetto | Ruolo |
|-----------|-------|
| `giskard` | Vulnerability scanning engine, detector library |
