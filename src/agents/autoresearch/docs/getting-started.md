# AutoResearch — Getting Started

Guida passo-passo per collegare il tuo progetto di training all'autoresearch agent ed eseguire il primo sweep di iperparametri.

---

## 1. Prerequisiti

```bash
# Avvia l'infrastruttura (LiteLLM proxy, PostgreSQL, Qdrant, Phoenix, Neo4j)
make build

# Verifica che almeno una API key LLM sia configurata in .env
make env-check
```

---

## 2. Preparare il progetto di training

### 2.1 Struttura della directory

Crea una directory dedicata al tuo progetto di training. Esempio:

```
setups/my_model/
├── train.py            # entrypoint (obbligatorio)
├── config.yaml         # configurazione del modello (opzionale)
├── requirements.txt    # dipendenze (opzionale)
└── data/               # dati (opzionale)
```

L'autoresearch runner cerca automaticamente l'entrypoint in questo ordine di priorità:

1. `train.py`
2. `run.py`
3. `main.py`

Se nessuno di questi file è presente nella directory, il runner lancia un `FileNotFoundError`.

### 2.2 Protocollo di comunicazione

Il tuo training script comunica con l'autoresearch agent tramite due meccanismi:

**Input — variabili d'ambiente `HPARAM_*`:**

Per ogni iperparametro definito nel search space, il runner inietta una variabile d'ambiente con prefisso `HPARAM_` e nome in maiuscolo. Esempio:

| Search space key | Variabile d'ambiente   |
| ---------------- | ---------------------- |
| `learning_rate`  | `HPARAM_LEARNING_RATE` |
| `batch_size`     | `HPARAM_BATCH_SIZE`    |
| `warmup_ratio`   | `HPARAM_WARMUP_RATIO`  |

Se nel budget è configurato un timeout per esperimento, viene anche settata `HPARAM_MAX_TRAIN_TIME` (in secondi).

La costruzione delle variabili d'ambiente avviene in `runners/base.py`, l'esecuzione del subprocess in `runners/local_runner.py`.

**Output — stampe `EXPERIMENT_*` su stdout:**

Al termine del training, lo script deve stampare su stdout delle righe con formato specifico:

| Chiave                   | Formato                                | Obbligatorio |
| ------------------------ | -------------------------------------- | ------------ |
| `EXPERIMENT_STATUS`      | `EXPERIMENT_STATUS=completed`          | Si           |
| `EXPERIMENT_RESULT`      | `EXPERIMENT_RESULT={"eval_f1": 0.85}`  | Si           |
| `EXPERIMENT_HYPERPARAMS` | `EXPERIMENT_HYPERPARAMS={"lr": 3e-5}`  | No           |
| `EXPERIMENT_RUN_ID`      | `EXPERIMENT_RUN_ID=run_042`            | No           |

Regole:
- Se `EXPERIMENT_STATUS=completed` non viene mai stampato, l'esperimento è marcato come **crashed**
- `EXPERIMENT_RESULT` deve essere un JSON dict. Solo i valori numerici (int, float) vengono estratti come metriche; valori non numerici vengono ignorati
- Se la stessa chiave appare più volte, vince l'ultima occorrenza

Il parsing è implementato in `tracking/result_parser.py`.

### 2.3 Esempio minimo di `train.py`

```python
#!/usr/bin/env python3
"""Training script compatibile con autoresearch."""
import json
import os

# Leggi iperparametri dalle variabili d'ambiente
lr = float(os.environ.get("HPARAM_LEARNING_RATE", "1e-4"))
batch_size = int(os.environ.get("HPARAM_BATCH_SIZE", "16"))

# --- Il tuo training qui ---
eval_f1 = 0.85  # sostituisci con la metrica reale
eval_loss = 0.42
# ---------------------------

# Stampa i risultati nel formato richiesto
hparams = {"learning_rate": lr, "batch_size": batch_size}
result = {"eval_f1": round(eval_f1, 4), "eval_loss": round(eval_loss, 4)}

print(f"EXPERIMENT_STATUS=completed")
print(f"EXPERIMENT_HYPERPARAMS={json.dumps(hparams)}")
print(f"EXPERIMENT_RESULT={json.dumps(result)}")
```

---

## 3. Scrivere la configurazione sweep (YAML)

Crea un file YAML (es. `sweep.yaml`) nella root del progetto o dove preferisci. Il campo **`base_setup`** punta alla directory del tuo progetto di training creata al passo 2.

### 3.1 Configurazione minimale

```yaml
sweep:
  name: my-first-sweep
  base_setup: ./setups/my_model       # path alla directory con train.py
  metric:
    name: eval_f1                      # chiave presente in EXPERIMENT_RESULT
    goal: maximize                     # "maximize" o "minimize"
  search_space:
    learning_rate:
      type: log_uniform
      min: 1.0e-5
      max: 1.0e-3
    batch_size:
      type: choice
      values: [4, 8, 16, 32]
```

Campi obbligatori: `name`, `base_setup`, `metric`, `search_space` (almeno un parametro).

### 3.2 Configurazione completa

```yaml
sweep:
  name: my-sweep
  base_setup: ./setups/my_model

  metric:
    name: eval_f1
    goal: maximize

  search_space:
    learning_rate:
      type: log_uniform
      min: 1.0e-5
      max: 1.0e-3
    batch_size:
      type: choice
      values: [4, 8, 16, 32]
    warmup_ratio:
      type: uniform
      min: 0.0
      max: 0.2

  budget:
    max_experiments: 50          # massimo numero totale di esperimenti
    max_wall_time_hours: 4.0     # tempo totale massimo
    max_run_time_seconds: 600    # timeout per singolo esperimento (null = nessun limite)

  strategy:
    type: agent                  # "agent" (LLM-driven), "random", o "grid"
    waves_parallel: 4            # esperimenti per wave

  hardware:
    backend: local               # "local", "ssh", "slurm", o "skypilot"
```

La struttura completa di `SweepConfig` con tutti i campi opzionali (escalation, agent_rules, code_edit, llm) è definita in `config/models.py`.

### 3.3 Tipi di search space

| Tipo          | Parametri    | Descrizione                                          |
| ------------- | ------------ | ---------------------------------------------------- |
| `log_uniform` | `min`, `max` | Campionamento logaritmico — ideale per learning rate |
| `uniform`     | `min`, `max` | Campionamento uniforme lineare                       |
| `choice`      | `values`     | Scelta tra un elenco di valori discreti              |

---

## 4. Avviare il workflow

### 4.1 Da YAML (consigliato)

```python
from src.agents.autoresearch.agent import build_graph
from src.agents.autoresearch.config.models import SweepConfig

# 1. Carica la configurazione dal file YAML
config = SweepConfig.from_yaml("sweep.yaml")

# 2. Costruisci il graph con la strategy scelta
#    Opzioni: "agent" (default, LLM-driven), "random", "grid"
graph = build_graph(strategy=config.strategy.type.value)

# 3. Avvia lo sweep
result = graph.invoke({
    "sweep_config": config.model_dump(mode="json"),
})
```

### 4.2 Con il graph di default

Se vuoi usare la strategy di default (`agent`) senza specificarla esplicitamente:

```python
from src.agents.autoresearch import graph
from src.agents.autoresearch.config.models import SweepConfig

config = SweepConfig.from_yaml("sweep.yaml")
result = graph.invoke({
    "sweep_config": config.model_dump(mode="json"),
})
```

### 4.3 Config inline (senza file YAML)

```python
from src.agents.autoresearch.agent import build_graph

graph = build_graph(strategy="random")

result = graph.invoke({
    "sweep_config": {
        "name": "quick-sweep",
        "base_setup": "./setups/my_model",
        "metric": {"name": "eval_f1", "goal": "maximize"},
        "budget": {"max_experiments": 10, "max_wall_time_hours": 1.0},
        "search_space": {
            "learning_rate": {"type": "log_uniform", "min": 1e-5, "max": 1e-3},
            "batch_size": {"type": "choice", "values": [4, 8, 16]},
        },
        "strategy": {"type": "random", "waves_parallel": 2},
    },
})
```

### 4.4 Quale strategy scegliere

| Strategy | Quando usarla                                                    |
| -------- | ---------------------------------------------------------------- |
| `agent`  | Spazio di ricerca ampio, vuoi che l'LLM guidi l'esplorazione     |
| `random` | Baseline veloce, nessuna dipendenza dall'LLM per la generazione  |
| `grid`   | Spazio di ricerca piccolo, vuoi coprire tutte le combinazioni    |

---

## 5. Leggere i risultati

`graph.invoke()` restituisce un dizionario con tutto lo stato finale. I campi principali:

```python
result["session_id"]            # ID della sessione (per riprendere)
result["experiments_completed"] # numero totale di esperimenti eseguiti
result["best_metric_value"]     # miglior valore della metrica
result["best_hyperparams"]      # iperparametri del miglior run
result["best_run_id"]           # ID del miglior run
```

Tutti i risultati vengono anche persistiti automaticamente in PostgreSQL dal nodo `store_results`.

---

## 6. Riprendere una sessione interrotta

Per riprendere uno sweep interrotto, passa il `session_id` della sessione precedente:

```python
result = graph.invoke({
    "session_id": "a1b2c3d4e5f6",
    "sweep_config": config.model_dump(mode="json"),
})
```

Il nodo `initialize_session` rileva l'ID esistente, carica lo stato dalla base dati e riparte da dove si era fermato.

---

## Riepilogo rapido

```
1. Scrivi train.py     → legge HPARAM_*, stampa EXPERIMENT_*
2. Mettilo in una dir  → es. setups/my_model/
3. Scrivi sweep.yaml   → base_setup punta a quella directory
4. Carica config       → config = SweepConfig.from_yaml("sweep.yaml")
5. Avvia               → result = graph.invoke({"sweep_config": config.model_dump(mode="json")})
6. Leggi risultati     → result["best_hyperparams"], result["best_metric_value"]
```
