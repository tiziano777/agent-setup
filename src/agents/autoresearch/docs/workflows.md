# AutoResearch — Workflow Operativi

## Prerequisiti Comuni

Prima di utilizzare qualsiasi workflow, assicurarsi che:

1. **Infrastruttura attiva**: `make build` (avvia LiteLLM proxy + PostgreSQL + Qdrant + Phoenix + Neo4j)
2. **Almeno una API key LLM** configurata nel `.env` (verificare con `make env-check`)
3. **Directory `base_setup`** con uno script di training compatibile col protocollo EXPERIMENT_*

### Protocollo L1/L2: il contratto train.py

AutoResearch comunica con lo script di training tramite un protocollo semplice:

- **Input (AutoResearch → train.py):** variabili d'ambiente `HPARAM_*`
- **Output (train.py → AutoResearch):** linee `EXPERIMENT_*` su stdout

**Esempio minimale di `train.py` compatibile:**

```python
#!/usr/bin/env python3
"""Minimal training script compatible with AutoResearch."""
import json
import os

# 1. Leggere iperparametri dalle variabili HPARAM_*
lr = float(os.environ.get("HPARAM_LEARNING_RATE", "1e-4"))
batch_size = int(os.environ.get("HPARAM_BATCH_SIZE", "16"))
epochs = int(os.environ.get("HPARAM_NUM_EPOCHS", "3"))

# 2. Eseguire il training (qui simulato)
print(f"Training with lr={lr}, batch_size={batch_size}, epochs={epochs}")
eval_f1 = 0.75 + lr * 1000 - (batch_size / 100)  # simulazione

# 3. Emettere risultato nel formato EXPERIMENT_*
hparams = {"learning_rate": lr, "batch_size": batch_size, "num_epochs": epochs}
result = {"eval_f1": round(eval_f1, 4), "eval_loss": round(1 - eval_f1, 4)}

print(f"EXPERIMENT_STATUS=completed")
print(f"EXPERIMENT_HYPERPARAMS={json.dumps(hparams)}")
print(f"EXPERIMENT_RESULT={json.dumps(result)}")
```

> **Importante:** se lo script crasha senza stampare `EXPERIMENT_STATUS=completed`, l'esperimento viene marcato come `crashed`.

---

## Workflow 1: Quick Start — Random Sweep Minimale

### Obiettivo

Lanciare un piccolo sweep random per validare il setup. Non richiede LLM per la generazione degli iperparametri.

### Configurazione YAML

Creare `sweep_quick.yaml`:

```yaml
sweep:
  name: quick-validation
  base_setup: ./setups/my_model
  metric:
    name: eval_f1
    goal: maximize
  budget:
    max_experiments: 10
    max_wall_time_hours: 1.0
  search_space:
    learning_rate:
      type: log_uniform
      min: 1.0e-5
      max: 1.0e-3
    batch_size:
      type: choice
      values: [4, 8, 16]
  strategy:
    type: random
    waves_parallel: 2
```

### Invocazione Python

```python
from src.agents.autoresearch.agent import build_graph
from src.agents.autoresearch.config.models import SweepConfig

config = SweepConfig.from_yaml("sweep_quick.yaml")
graph = build_graph(strategy="random")

result = graph.invoke({
    "sweep_config": config.model_dump(mode="json"),
})

print(f"Sessione: {result['session_id']}")
print(f"Esperimenti completati: {result['experiments_completed']}")
print(f"Miglior F1: {result.get('best_metric_value')}")
print(f"Migliori HP: {result.get('best_hyperparams')}")
```

### Output Atteso

```
INFO: Sessione inizializzata: a1b2c3d4e5f6
INFO: === Wave 1 (2 esperimenti) ===
INFO:   exp_001: lr=3.2e-4, batch=8  → eval_f1=0.82 (completed, 95s)
INFO:   exp_002: lr=1.5e-5, batch=16 → eval_f1=0.71 (completed, 110s)
INFO: Wave analyst: should_continue=True
INFO: === Wave 2 (2 esperimenti) ===
INFO:   exp_003: lr=7.8e-4, batch=4  → eval_f1=0.79 (completed, 130s)
INFO:   exp_004: lr=4.1e-5, batch=16 → eval_f1=0.76 (completed, 105s)
...
INFO: === Wave 5 (2 esperimenti) ===
INFO:   exp_009: lr=2.5e-4, batch=8  → eval_f1=0.85 (completed, 98s)
INFO:   exp_010: lr=9.2e-5, batch=4  → eval_f1=0.80 (completed, 115s)
INFO: Budget esaurito (10/10 esperimenti)
INFO: Knowledge persistita: best_f1=0.85, best_config={lr=2.5e-4, batch=8}
```

### Troubleshooting

| Problema | Causa | Soluzione |
|---|---|---|
| `ConnectionRefusedError` su PostgreSQL | Infrastruttura non attiva | Eseguire `make build` |
| `FileNotFoundError: train.py` | `base_setup` non punta alla directory corretta | Verificare il percorso in `base_setup` |
| Tutti gli esperimenti `crashed` | `train.py` non stampa `EXPERIMENT_STATUS` | Aggiungere le linee `EXPERIMENT_*` allo script |
| `ValueError: search_space must contain at least one parameter` | YAML malformato | Verificare indentazione e tipi nel file YAML |

---

## Workflow 2: Sweep Agent-Driven Completo

### Obiettivo

Sweep completo dove un LLM guida le decisioni: il `loop_operator` decide dopo ogni wave se continuare, l'`hyperparams_advisor` propone configurazioni data-driven, il `wave_analyst` fornisce insights, e il `crash_diagnostician` interviene se necessario.

### Configurazione YAML

Creare `sweep_agent.yaml`:

```yaml
sweep:
  name: llama7b-sentiment-agent
  base_setup: ./setups/llama_sentiment
  metric:
    name: eval_f1
    goal: maximize
  budget:
    max_experiments: 50
    max_wall_time_hours: 4.0
    max_run_time_seconds: 1800
  search_space:
    learning_rate:
      type: log_uniform
      min: 1.0e-5
      max: 1.0e-3
    batch_size:
      type: choice
      values: [4, 8, 16]
    warmup_ratio:
      type: uniform
      min: 0.0
      max: 0.2
    weight_decay:
      type: log_uniform
      min: 1.0e-4
      max: 0.1
    lora_r:
      type: choice
      values: [4, 8, 16, 32]
  agent_rules:
    exploration_strategy: balanced
  strategy:
    type: agent
    waves_parallel: 4
  hardware:
    backend: local
    max_concurrent_jobs: 4
  llm:
    enabled: true
    temperature: 0.7
    max_total_tokens: 500000
```

### Invocazione Python

```python
from src.agents.autoresearch.agent import build_graph
from src.agents.autoresearch.config.models import SweepConfig

config = SweepConfig.from_yaml("sweep_agent.yaml")
graph = build_graph(strategy="agent")

result = graph.invoke({
    "sweep_config": config.model_dump(mode="json"),
})
```

### Output Atteso

```
INFO: Sessione inizializzata: f8a2b1c9d3e7
INFO: Prior knowledge caricata: 2 sweep precedenti trovati
INFO: Query trajectory: 0 esperimenti esistenti
INFO: Similarity search: 3 esperimenti simili trovati via Cognee
INFO: Loop operator: action=next_wave, reason="Initial exploration phase"
INFO: === Wave 1 (4 esperimenti) — Advisor: random exploration ===
INFO:   exp_001: lr=2.1e-4, batch=8, warmup=0.05, wd=0.01, lora=8
INFO:     → eval_f1=0.82 (completed, 340s)
INFO:   exp_002: lr=7.3e-5, batch=16, warmup=0.12, wd=0.001, lora=16
INFO:     → eval_f1=0.79 (completed, 280s)
INFO:   exp_003: lr=5.0e-4, batch=4, warmup=0.0, wd=0.05, lora=4
INFO:     → CRASHED (OOM after 45s)
INFO:   exp_004: lr=1.2e-4, batch=8, warmup=0.08, wd=0.003, lora=32
INFO:     → eval_f1=0.84 (completed, 310s)
INFO: Wave analyst: should_continue=True, insights=["Promising with lr~1e-4"]
INFO: Query trajectory: 4 esperimenti, best=0.84
INFO: Loop operator: action=next_wave, reason="3/4 completed, crash rate 0.25"
INFO: === Wave 2 (4 esperimenti) — Advisor: exploit lr=1e-4, explore lora ===
...
INFO: === Wave 8 (4 esperimenti) ===
INFO: Wave analyst: should_continue=False, reason="Plateau: <0.5% improvement in 3 waves"
INFO: Loop operator: action=stop, reason="Wave analyst recommends early stop"
INFO: Knowledge persistita: best_f1=0.91, 32 esperimenti completati
```

### Diagramma di Flusso Decisionale

```mermaid
flowchart TD
    A[query_trajectory] --> B[similarity_search]
    B --> C{loop_operator}
    C -->|next_wave| D[hyperparams_advisor]
    C -->|stop/pause| G[persist_knowledge]
    C -->|diagnostics| F[crash_diagnostician]
    F --> C
    D --> E[validate → execute → store → analyst → escalation]
    E -->|continue| A
    E -->|done| G
```

### Troubleshooting

| Problema | Causa | Soluzione |
|---|---|---|
| LLM risponde con JSON malformato | Modello free-tier con scarso supporto JSON | Il sistema fa fallback a random; verificare le key LLM |
| Token budget esaurito | Troppi cicli LLM-driven | Aumentare `llm.max_total_tokens` o ridurre `budget.max_experiments` |
| `loop_operator` decide `stop` troppo presto | Modello troppo conservativo | Cambiare `exploration_strategy` ad `aggressive` |

---

## Workflow 3: Grid Search Esaustivo

### Obiettivo

Sweep esaustivo su un search space discreto/piccolo. Copertura completa di tutte le combinazioni.

### Configurazione YAML

```yaml
sweep:
  name: grid-search-optimizer
  base_setup: ./setups/my_model
  metric:
    name: eval_accuracy
    goal: maximize
  budget:
    max_experiments: 200
    max_wall_time_hours: 6.0
  search_space:
    learning_rate:
      type: choice
      values: [1.0e-5, 5.0e-5, 1.0e-4, 5.0e-4, 1.0e-3]
    batch_size:
      type: choice
      values: [4, 8, 16]
    num_epochs:
      type: choice
      values: [1, 3, 5]
  strategy:
    type: grid
    waves_parallel: 4
```

**Combinazioni totali:** 5 x 3 x 3 = 45 esperimenti

### Invocazione Python

```python
graph = build_graph(strategy="grid")
result = graph.invoke({"sweep_config": config.model_dump(mode="json")})
```

### Output Atteso

```
INFO: Sessione inizializzata: c4d5e6f7a8b9
INFO: Grid generata: 45 configurazioni totali
INFO: === Wave 1 (4 esperimenti): offset 0→4 ===
INFO: === Wave 2 (4 esperimenti): offset 4→8 ===
...
INFO: === Wave 12 (1 esperimento): offset 44→45 ===
INFO: Grid completata: 45/45 esperimenti eseguiti
INFO: Knowledge persistita: best_accuracy=0.93
```

### Quando Usare Grid vs. Random vs. Agent

| Criterio | Grid | Random | Agent |
|---|---|---|---|
| **Search space** | Piccolo/discreto (<100 combo) | Qualsiasi | Ampio (5+ parametri) |
| **Budget** | Uguale al numero di combinazioni | Flessibile | Significativo (50+) |
| **LLM necessario** | No | No | Si |
| **Copertura** | 100% esaustiva | Campionamento casuale | Guidata da dati |
| **Tempo di setup** | Minimo | Minimo | Richiede config agent_rules |
| **Miglior caso d'uso** | Validation finale, HP discreti | Esplorazione iniziale | Produzione, search space ampi |

### Troubleshooting

| Problema | Causa | Soluzione |
|---|---|---|
| Troppe combinazioni | Esplosione combinatoria | Ridurre valori per parametro o passare a random |
| Timeout su grid grandi | Wall time insufficiente | Aumentare `max_wall_time_hours` |

---

## Workflow 4: Esecuzione Remota via SSH

### Obiettivo

Eseguire esperimenti su una macchina remota con GPU via SSH.

### Prerequisiti Specifici

- SSH key-based authentication configurato verso la macchina target
- `rsync` installato su entrambe le macchine
- Python + dipendenze di training installate sulla macchina remota
- La directory `~/autoresearch_runs` deve essere accessibile (creata automaticamente)

### Configurazione YAML

```yaml
sweep:
  name: remote-gpu-sweep
  base_setup: ./setups/llama_cls
  metric:
    name: eval_f1
    goal: maximize
  budget:
    max_experiments: 30
    max_wall_time_hours: 3.0
    max_run_time_seconds: 3600
  search_space:
    learning_rate:
      type: log_uniform
      min: 1.0e-5
      max: 1.0e-3
    batch_size:
      type: choice
      values: [4, 8, 16, 32]
  strategy:
    type: random
    waves_parallel: 2
  hardware:
    backend: ssh
    ssh_host: gpu-server.lab.university.edu
    ssh_user: researcher
    ssh_key_path: ~/.ssh/id_ed25519
    max_concurrent_jobs: 2
```

### Cosa Succede Internamente

```
1. rsync -avz ./setups/llama_cls/ researcher@gpu-server:~/autoresearch_runs/<run_id>/
2. ssh researcher@gpu-server "cd ~/autoresearch_runs/<run_id> && \
     HPARAM_LEARNING_RATE=0.0003 HPARAM_BATCH_SIZE=16 \
     nohup python train.py > output.log 2>&1 &"
3. [polling] ssh researcher@gpu-server "kill -0 <pid>" (ogni 5s)
4. [completato] ssh researcher@gpu-server "cat ~/autoresearch_runs/<run_id>/output.log"
5. Parsing EXPERIMENT_* dal log
```

### Troubleshooting

| Problema | Causa | Soluzione |
|---|---|---|
| `ssh: connect to host ... port 22: Connection refused` | SSH non attivo o firewall | Verificare `ssh researcher@gpu-server` manualmente |
| `rsync: connection unexpectedly closed` | Permessi o path errato | Verificare `ssh_key_path` e accesso alla directory |
| Esperimenti in PENDING infinito | Processo non parte sul remote | Verificare che Python e dipendenze siano installati |
| `FileNotFoundError` su entrypoint | `train.py` non presente dopo rsync | Verificare struttura della directory `base_setup` |

---

## Workflow 5: Sweep su Cluster SLURM

### Obiettivo

Sottomettere esperimenti a un cluster HPC con SLURM scheduler.

### Prerequisiti Specifici

- Accesso a un cluster con SLURM (`sbatch`, `sacct`, `scancel` disponibili)
- Partizione configurata con risorse adeguate
- Moduli Python/CUDA caricati nel profilo o nello script

### Configurazione YAML

```yaml
sweep:
  name: slurm-hpc-sweep
  base_setup: ./setups/large_model
  metric:
    name: eval_loss
    goal: minimize
  budget:
    max_experiments: 100
    max_wall_time_hours: 24.0
    max_run_time_seconds: 7200
  search_space:
    learning_rate:
      type: log_uniform
      min: 1.0e-5
      max: 5.0e-4
    batch_size:
      type: choice
      values: [8, 16, 32, 64]
    warmup_ratio:
      type: uniform
      min: 0.0
      max: 0.15
  strategy:
    type: agent
    waves_parallel: 8
  hardware:
    backend: slurm
    partition: gpu-a100
    max_concurrent_jobs: 8
  llm:
    enabled: true
```

### Script sbatch Generato (esempio)

Per ogni esperimento, il SLURMRunner genera automaticamente:

```bash
#!/bin/bash
#SBATCH --job-name=autoresearch-exp_a1b2
#SBATCH --partition=gpu-a100
#SBATCH --time=02:00:00
#SBATCH --output=autoresearch-exp_a1b2.out
#SBATCH --error=autoresearch-exp_a1b2.err

export HPARAM_LEARNING_RATE=0.00015
export HPARAM_BATCH_SIZE=16
export HPARAM_WARMUP_RATIO=0.08

cd /path/to/setups/large_model
python train.py
```

### Output e Monitoraggio

```
INFO: === Wave 1 (8 esperimenti) ===
INFO:   Submitted SLURM job 12345678 for exp_001
INFO:   Submitted SLURM job 12345679 for exp_002
...
INFO: [polling sacct] Job 12345678: RUNNING → COMPLETED
INFO: [polling sacct] Job 12345679: RUNNING → FAILED (OUT_OF_MEMORY)
```

### Troubleshooting

| Problema | Causa | Soluzione |
|---|---|---|
| `sbatch: error: invalid partition` | Partizione non valida | Verificare con `sinfo` le partizioni disponibili |
| Job falliti con `OUT_OF_MEMORY` | HP troppo aggressivi (batch grande) | Il crash_diagnostician aggiungera' alla blacklist |
| `sacct` non ritorna risultati | Accounting non abilitato | Contattare admin del cluster |
| Job in `PENDING` molto a lungo | Coda del cluster piena | Ridurre `waves_parallel` o attendere |

---

## Workflow 6: GPU Cloud con SkyPilot

### Obiettivo

Eseguire esperimenti su GPU cloud (AWS, GCP, Azure, Lambda) via SkyPilot.

### Prerequisiti Specifici

- `pip install "skypilot[aws]"` (o `[gcp]`, `[azure]`, `[lambda]`)
- Credenziali cloud configurate (`sky check` per verificare)
- Tenere presente i costi: ogni esperimento lancia un cluster

### Configurazione YAML

```yaml
sweep:
  name: cloud-gpu-sweep
  base_setup: ./setups/llama_cls
  metric:
    name: eval_f1
    goal: maximize
  budget:
    max_experiments: 20
    max_wall_time_hours: 8.0
  search_space:
    learning_rate:
      type: log_uniform
      min: 1.0e-5
      max: 5.0e-4
    batch_size:
      type: choice
      values: [8, 16, 32]
  strategy:
    type: random
    waves_parallel: 2
  hardware:
    backend: skypilot
    max_concurrent_jobs: 2
    skypilot:
      accelerators: "A100:1"
      cloud: aws
      region: us-east-1
      use_spot: true
      num_nodes: 1
```

### Gestione Costi

| Parametro | Impatto sui costi |
|---|---|
| `use_spot: true` | ~70% risparmio, rischio preemption |
| `accelerators: "A100:1"` | ~$1-3/ora per istanza spot |
| `waves_parallel: 2` | 2 cluster contemporanei = 2x costo orario |
| `num_nodes: 1` | 1 nodo per esperimento (multi-node = costo proporzionale) |

Il metodo `teardown()` del SkyPilotRunner distrugge i cluster al termine. Verificare con `sky status` che non rimangano cluster orfani.

### Troubleshooting

| Problema | Causa | Soluzione |
|---|---|---|
| `sky check` fallisce | Credenziali cloud non configurate | Seguire documentazione SkyPilot per il provider |
| Quota exceeded | Limiti GPU nel cloud account | Richiedere aumento quota al provider |
| Spot preemption | Istanza recuperata dal provider | Il runner ritentera' automaticamente; considerare `use_spot: false` |
| Cluster orfani | Errore durante teardown | `sky status` per ispezionare, `sky down <name>` per distruggere |

---

## Workflow 7: Modalita' Code-Edit

### Obiettivo

L'agent non modifica solo gli iperparametri ma anche il codice di `train.py` — puo' cambiare optimizer, scheduler, loss function, data augmentation.

### Configurazione YAML

```yaml
sweep:
  name: code-edit-sweep
  base_setup: ./setups/llama_cls
  metric:
    name: eval_f1
    goal: maximize
  budget:
    max_experiments: 30
    max_wall_time_hours: 4.0
  search_space:
    learning_rate:
      type: log_uniform
      min: 1.0e-5
      max: 1.0e-3
    batch_size:
      type: choice
      values: [4, 8, 16]
  strategy:
    type: agent
    waves_parallel: 2
  agent_mode: code_edit
  code_edit:
    editable_files:
      - train.py
    protected_files:
      - prepare.py
      - config.yaml
      - requirements.txt
    git_tracking: true
    snapshot_per_experiment: true
  llm:
    enabled: true
```

### Come Funziona

```mermaid
flowchart TD
    A[Advisor propone HP + code change] --> B[Snapshot git -- baseline]
    B --> C[Applica modifica a train.py]
    C --> D[Esegue esperimento]
    D --> E{Metrica migliorata?}
    E -->|Si| F[Mantieni modifica]
    E -->|No| G[Revert a baseline]
    F --> H[Prossimo ciclo]
    G --> H
```

### Vincoli e Sicurezza

- I file in `protected_files` non possono essere modificati
- La funzione `resolve_hyperparams()` deve essere mantenuta intatta
- Le linee `EXPERIMENT_RESULT` non devono essere rimosse
- Con `git_tracking: true`, ogni modifica e' tracciata come commit
- Con `snapshot_per_experiment: true`, ogni esperimento ha il suo snapshot
- La persona `code-explorer` limita le modifiche a 1 cambiamento per volta
- Max 3 modifiche consecutive senza miglioramento = revert a solo HP tuning

---

## Workflow 8: Configurazione Stadi di Escalation

### Obiettivo

Configurare una ricerca progressiva che inizia con pochi parametri ed espande lo search space automaticamente quando rileva un plateau.

### Configurazione YAML

```yaml
sweep:
  name: escalation-demo
  base_setup: ./setups/llama_cls
  metric:
    name: eval_f1
    goal: maximize
  budget:
    max_experiments: 80
    max_wall_time_hours: 6.0
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
    weight_decay:
      type: log_uniform
      min: 1.0e-4
      max: 0.1
    lora_r:
      type: choice
      values: [4, 8, 16, 32]
    num_epochs:
      type: choice
      values: [1, 2, 3, 5]
  strategy:
    type: agent
    waves_parallel: 4
  escalation:
    enabled: true
    stages:
      - name: core_params
        parameters: [learning_rate, batch_size]
        min_experiments: 8
        plateau_patience: 5
        plateau_threshold: 0.01
      - name: regularization
        parameters: [warmup_ratio, weight_decay]
        min_experiments: 8
        plateau_patience: 5
        plateau_threshold: 0.005
      - name: architecture
        parameters: [lora_r, num_epochs]
        min_experiments: 8
        plateau_patience: 8
        plateau_threshold: 0.002
  llm:
    enabled: true
```

### Come Funziona il Rilevamento Plateau

**Passo per passo:**

1. **Stadio 0 (core_params):** Solo `learning_rate` e `batch_size` sono attivi
2. L'agent esplora queste 2 dimensioni per almeno 8 esperimenti
3. Dopo ogni wave, `update_escalation` controlla gli ultimi 5 esperimenti
4. Se il miglioramento e' < 1% (threshold 0.01) → **plateau rilevato**
5. **Stadio 1 (regularization):** Aggiunge `warmup_ratio` e `weight_decay` allo search space
6. L'esplorazione continua con 4 parametri attivi
7. Nuovo plateau con threshold 0.5% → avanza a stadio 2
8. **Stadio 2 (architecture):** Aggiunge `lora_r` e `num_epochs`
9. L'esplorazione continua con tutti i 6 parametri

### Output Atteso

```
INFO: === Stadio 0: core_params (learning_rate, batch_size) ===
INFO: Wave 1-3: best_f1 = 0.72 → 0.81 → 0.84 → 0.845 → 0.848
INFO: Escalation: plateau rilevato (improvement 0.35% < threshold 1.0%)
INFO: Avanzamento a stadio 1: + warmup_ratio, weight_decay

INFO: === Stadio 1: regularization (4 parametri attivi) ===
INFO: Wave 4-6: best_f1 = 0.855 → 0.87 → 0.88 → 0.884 → 0.886
INFO: Escalation: plateau rilevato (improvement 0.23% < threshold 0.5%)
INFO: Avanzamento a stadio 2: + lora_r, num_epochs

INFO: === Stadio 2: architecture (6 parametri attivi) ===
INFO: Wave 7-10: best_f1 = 0.89 → 0.91 → 0.92
```

---

## Workflow 9: Ripresa di uno Sweep Interrotto

### Obiettivo

Riprendere uno sweep che e' stato messo in pausa dal `loop_operator` o interrotto manualmente.

### Come Funziona il Resume

1. Si passa il `session_id` esistente come input
2. `initialize_session` lo recupera dal database PostgreSQL
3. Lo state viene ricostruito dai dati persistiti: esperimenti, best result, escalation stage
4. Lo sweep riprende dal punto in cui si era fermato

### Invocazione

```python
from src.agents.autoresearch.agent import build_graph
from src.agents.autoresearch.config.models import SweepConfig

# Caricare la stessa configurazione originale
config = SweepConfig.from_yaml("sweep_agent.yaml")
graph = build_graph(strategy="agent")

# Riprendere passando il session_id
result = graph.invoke({
    "session_id": "a1b2c3d4e5f6",  # ID dalla sessione precedente
    "sweep_config": config.model_dump(mode="json"),
})
```

### Verifica Stato Prima del Resume

Per ispezionare lo stato della sessione prima di riprendere:

```python
from src.agents.autoresearch.db.connector import PostgresConnector
from src.agents.autoresearch.db.repositories import SweepSessionRepository

connector = PostgresConnector()
repo = SweepSessionRepository(connector)
session = repo.get("a1b2c3d4e5f6")

print(f"Status: {session.status}")
print(f"Esperimenti: {session.total_experiments}/{session.budget_max_experiments}")
print(f"Best metric: {session.best_metric_value}")
print(f"Escalation stage: {session.escalation_stage}")
```

### Troubleshooting

| Problema | Causa | Soluzione |
|---|---|---|
| `ValueError: Session not found` | session_id errato o DB diverso | Verificare l'ID e che `PGVECTOR_URI` punti allo stesso database |
| Config mismatch | La config YAML e' stata modificata | Usare la stessa config dell'esecuzione originale |
| Sessione gia' completata | Lo status e' `completed` | Creare una nuova sessione (non passare session_id) |

---

## Workflow 10: Trasferimento Conoscenza Cross-Sweep

### Obiettivo

Sfruttare la conoscenza accumulata da sweep precedenti per guidare un nuovo sweep sullo stesso setup o su uno simile.

### Come Funziona

Il knowledge transfer e' **automatico** — non richiede configurazione speciale:

1. **`initialize_session`** carica automaticamente `prior_knowledge` dalla tabella `knowledge` del database, cercando sweep con lo stesso `base_setup` e metrica
2. **`similarity_search`** interroga il knowledge graph Cognee (se configurato) per trovare esperimenti semanticamente simili, anche da setup diversi
3. **`hyperparams_advisor`** usa entrambe le fonti nel contesto inviato all'LLM, che puo' cosi' partire da configurazioni informate anziche' da zero

### Prerequisiti

- Almeno uno sweep precedente completato sullo stesso `base_setup`
- Per ricerca semantica cross-setup: Cognee configurato e attivo (`NEO4J_*` env vars)

### Invocazione

Nessuna configurazione speciale. Basta lanciare un nuovo sweep normalmente:

```python
config = SweepConfig.from_yaml("sweep_agent.yaml")
graph = build_graph(strategy="agent")
result = graph.invoke({"sweep_config": config.model_dump(mode="json")})
```

### Verificare il Knowledge Transfer

Nei log si vedranno messaggi come:

```
INFO: Prior knowledge caricata: 3 sweep precedenti per "./setups/llama_cls" + "eval_f1"
INFO:   - llama7b-v1: best_f1=0.88, 45 esperimenti
INFO:   - llama7b-v2: best_f1=0.91, 50 esperimenti
INFO:   - llama7b-quick: best_f1=0.82, 10 esperimenti
INFO: Similarity search (Cognee): 2 esperimenti simili trovati
INFO: Similarity search (PostgreSQL): 3 knowledge entries trovate
```

### Troubleshooting

| Problema | Causa | Soluzione |
|---|---|---|
| `Prior knowledge: 0 sweep trovati` | Nessuno sweep precedente con lo stesso setup | Eseguire prima almeno uno sweep sullo stesso `base_setup` |
| `Similarity search (Cognee): fallback` | Cognee non configurato | Avviare Neo4j con `make build` e configurare `NEO4J_*` |
| Knowledge non rilevante | base_setup diverso | Cognee cerca semanticamente; PostgreSQL cerca exact match |

---

## Appendice A: Tabella Riepilogativa dei Workflow

| # | Workflow | Strategia | Backend | LLM | Complessita' |
|---|---|---|---|---|---|
| 1 | Quick Start | random | local | No | Bassa |
| 2 | Agent-Driven | agent | local | Si | Alta |
| 3 | Grid Search | grid | local | No | Bassa |
| 4 | SSH Remote | qualsiasi | ssh | Dipende | Media |
| 5 | SLURM Cluster | qualsiasi | slurm | Dipende | Media |
| 6 | SkyPilot Cloud | qualsiasi | skypilot | Dipende | Alta |
| 7 | Code-Edit | agent | qualsiasi | Si | Alta |
| 8 | Escalation | qualsiasi | qualsiasi | Dipende | Media |
| 9 | Resume | originale | originale | Dipende | Bassa |
| 10 | Cross-Sweep | agent | qualsiasi | Si | Media |

---

## Appendice B: Esempio Completo train.py

Script realistico per fine-tuning con LoRA, compatibile con il protocollo AutoResearch:

```python
#!/usr/bin/env python3
"""Fine-tuning script compatible with AutoResearch EXPERIMENT_* protocol.

Reads hyperparameters from HPARAM_* environment variables and emits
structured results on stdout for AutoResearch to parse.
"""
import json
import os
import sys
import time

def resolve_hyperparams() -> dict:
    """Read hyperparameters from HPARAM_* environment variables."""
    return {
        "learning_rate": float(os.environ.get("HPARAM_LEARNING_RATE", "1e-4")),
        "batch_size": int(os.environ.get("HPARAM_BATCH_SIZE", "16")),
        "warmup_ratio": float(os.environ.get("HPARAM_WARMUP_RATIO", "0.05")),
        "weight_decay": float(os.environ.get("HPARAM_WEIGHT_DECAY", "0.01")),
        "num_epochs": int(os.environ.get("HPARAM_NUM_EPOCHS", "3")),
        "lora_r": int(os.environ.get("HPARAM_LORA_R", "8")),
    }

def emit(status: str, hparams: dict, metrics: dict | None = None) -> None:
    """Emit EXPERIMENT_* lines for AutoResearch to parse."""
    print(f"EXPERIMENT_STATUS={status}")
    print(f"EXPERIMENT_HYPERPARAMS={json.dumps(hparams)}")
    if metrics:
        print(f"EXPERIMENT_RESULT={json.dumps(metrics)}")

def main():
    hparams = resolve_hyperparams()
    print(f"[train] Starting with: {json.dumps(hparams, indent=2)}")

    try:
        # === YOUR TRAINING CODE HERE ===
        # from transformers import AutoModelForSequenceClassification, Trainer, ...
        # model = AutoModelForSequenceClassification.from_pretrained(...)
        # trainer = Trainer(model=model, args=TrainingArguments(
        #     learning_rate=hparams["learning_rate"],
        #     per_device_train_batch_size=hparams["batch_size"],
        #     ...
        # ))
        # trainer.train()
        # eval_results = trainer.evaluate()

        # Simulated training (replace with real training code):
        time.sleep(2)
        eval_f1 = 0.75 + hparams["learning_rate"] * 500
        eval_loss = 1.0 - eval_f1

        metrics = {
            "eval_f1": round(eval_f1, 4),
            "eval_loss": round(eval_loss, 4),
            "train_loss": round(eval_loss * 0.8, 4),
        }
        emit("completed", hparams, metrics)

    except Exception as e:
        print(f"[train] FATAL: {e}", file=sys.stderr)
        emit("failed", hparams)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

---

## Appendice C: Variabili d'Ambiente

| Variabile | Default | Descrizione |
|---|---|---|
| `DEFAULT_MODEL` | `llm` | Modello LLM da usare via proxy |
| `PGVECTOR_URI` | `postgresql://postgres:postgres@localhost:5433/vectors` | URI PostgreSQL |
| `LITELLM_BASE_URL` | `http://localhost:4000/v1` | URL proxy LiteLLM |
| `PHOENIX_COLLECTOR_ENDPOINT` | `http://localhost:6006` | Endpoint Phoenix per tracing |
| `PHOENIX_PROJECT_NAME` | `agent-setup` | Nome progetto Phoenix |
| `PHOENIX_TRACING_ENABLED` | `true` | Abilitare/disabilitare tracing |
| `NEO4J_URL` | `bolt://localhost:7687` | URL Neo4j per Cognee |
| `NEO4J_USERNAME` | `neo4j` | Username Neo4j |
| `NEO4J_PASSWORD` | `password` | Password Neo4j |
| `COGNEE_VECTOR_DB_HOST` | `localhost` | Host PGVector per Cognee |
| `COGNEE_VECTOR_DB_PORT` | `5433` | Porta PGVector per Cognee |
| `COGNEE_VECTOR_DB_NAME` | `vectors` | Database PGVector per Cognee |
| `COGNEE_VECTOR_DB_USERNAME` | `postgres` | Username PGVector Cognee |
| `COGNEE_VECTOR_DB_PASSWORD` | `postgres` | Password PGVector Cognee |
| `QDRANT_URL` | `http://localhost:6333` | URL Qdrant (se usato) |
