# AutoResearch — Riferimento Tecnico

## 1. Panoramica

AutoResearch e' un agente di ottimizzazione iperparametri ispirato ad **AutoEvolve&autoresearch**, costruito su **LangGraph**. Applica il metodo scientifico in modo iterativo:

1. **Osservazione** — recupera la traiettoria degli esperimenti passati e conoscenza pregressa
2. **Ipotesi** — un LLM propone nuove configurazioni di iperparametri data-driven
3. **Esperimento** — esegue un batch parallelo di training run su uno dei 4 backend hardware
4. **Analisi** — un LLM analizza i risultati, identifica trend e suggerisce early stopping
5. **Apprendimento** — persiste le conoscenze acquisite per sweep futuri

Il sistema supporta 3 strategie pipeline (Agent, Random, Grid) + una Functional API semplificata, 4 backend di esecuzione (locale, SSH, SLURM, SkyPilot), 2 modalita' operative (solo HP vs code-edit), escalation progressiva dello search space, e knowledge transfer semantico cross-sweep via Cognee.

---

## 2. Architettura

### 2.1 Diagramma dei Componenti

```mermaid
graph TD
    subgraph "config/"
        SweepConfig --> ParameterSpec
        SweepConfig --> BudgetConfig
        SweepConfig --> StrategyConfig
        SweepConfig --> HardwareConfig
        SweepConfig --> EscalationConfig
        Settings[AutoresearchSettings]
        TokenBudget[TokenTracker]
    end

    subgraph "pipelines/"
        AgentPipe[agent_pipeline]
        RandomPipe[random_pipeline]
        GridPipe[grid_pipeline]
        FuncPipe[functional pipeline]
    end

    subgraph "nodes/"
        InitSession[initialize_session]
        QueryTraj[query_trajectory]
        SimSearch[similarity_search]
        LoopOp[loop_operator]
        HPAdvice[hyperparams_advisor]
        ValidateP[validate_proposals]
        ExecWave[execute_wave]
        StoreRes[store_results]
        WaveAnal[wave_analyst]
        UpdateEsc[update_escalation]
        CrashDiag[crash_diagnostician]
        PersistKn[persist_knowledge]
        GenRandom[generate_random_wave]
        GenGrid[generate_grid]
        SliceWave[slice_next_wave]
    end

    subgraph "infrastructure"
        DB[(PostgreSQL)]
        Cognee[(Cognee KG)]
        LiteLLM[LiteLLM Proxy]
        Phoenix[Arize Phoenix]
    end

    SweepConfig --> AgentPipe
    SweepConfig --> RandomPipe
    SweepConfig --> GridPipe

    AgentPipe --> InitSession & QueryTraj & SimSearch & LoopOp
    AgentPipe --> HPAdvice & ValidateP & ExecWave & StoreRes
    AgentPipe --> WaveAnal & UpdateEsc & CrashDiag & PersistKn

    LoopOp & HPAdvice & WaveAnal & CrashDiag --> LiteLLM
    InitSession & StoreRes & QueryTraj & PersistKn --> DB
    SimSearch & PersistKn -.->|opzionale| Cognee
    LiteLLM --> Phoenix
```

### 2.2 Struttura delle Directory

```
src/agents/autoresearch/
├── __init__.py                  # Esporta graph + workflow; chiama setup_tracing()
├── agent.py                     # build_graph(strategy) -> pipeline compilato
├── config/
│   ├── models.py                # Pydantic v2: SweepConfig e sotto-modelli
│   ├── settings.py              # AutoresearchSettings (env-driven)
│   └── token_budget.py          # TokenTracker per budget LLM
├── db/
│   ├── connector.py             # PostgresConnector (psycopg3 pool)
│   ├── repositories.py          # 5 repository classes (CRUD per tabella)
│   └── schema.sql               # DDL schema autoresearch (5 tabelle)
├── escalation/
│   └── tracker.py               # EscalationTracker (plateau detection)
├── images/
│   ├── generate_diagrams.py     # Script generazione PNG Mermaid
│   ├── agent_pipeline.png       # Diagramma agent pipeline
│   ├── grid_pipeline.png        # Diagramma grid pipeline
│   ├── random_pipeline.png      # Diagramma random pipeline
│   └── functional_pipeline.png  # Diagramma functional pipeline
├── nodes/                       # 15 funzioni nodo (dettaglio in §6)
├── personas/
│   ├── agents/                  # 6 file .md persona (frontmatter YAML)
│   ├── prompts/                 # instructions.md, program.md.j2, program_code_edit.md.j2
│   └── rules/                   # default_rules.yaml
├── pipelines/
│   ├── agent_pipeline.py        # Agent pipeline (12 nodi, full LLM)
│   ├── grid_pipeline.py         # Grid pipeline (8 nodi, prodotto cartesiano)
│   ├── random_pipeline.py       # Random pipeline (7 nodi, sampling casuale)
│   └── pipeline.py              # Functional API (@entrypoint/@task)
├── prompts/
│   ├── system.py                # 5 prompt costanti (system, loop, advisor, analyst, crash)
│   └── personas.py              # AgentPersona loader da file .md
├── runners/
│   ├── base.py                  # BaseRunner ABC, RunHandle, RunStatus
│   ├── local_runner.py          # Subprocess locale
│   ├── ssh_runner.py            # rsync + SSH remoto
│   ├── slurm_runner.py          # SLURM sbatch/sacct
│   └── skypilot_runner.py       # SkyPilot cloud GPU
├── schemas/
│   ├── entities.py              # 5 dataclass entita' (SweepSession, Experiment, ...)
│   └── io.py                    # AutoresearchInput/Output Pydantic
├── states/
│   └── state.py                 # AutoresearchState TypedDict (27 campi)
├── tools/
│   ├── sweep_tools.py           # sample_random_config, validate_config
│   ├── experiment_tools.py      # query_history, get_trajectory, get_best_config
│   └── analysis_tools.py        # compute_parameter_importance, generate_sweep_report
├── tracking/
│   ├── aggregator.py            # best_config, top_k, parameter_importance
│   ├── reporter.py              # generate_report() markdown
│   └── result_parser.py         # Parser protocollo EXPERIMENT_*
├── tests/
│   ├── conftest.py              # Fixture: minimal_sweep_config, sample_trajectory
│   └── test_agent.py            # 6 classi, 18 test
├── memory/                      # Namespace (vuoto, memoria in PostgreSQL/Cognee)
└── docs/
    ├── autoresearch.md           # Questo documento
    └── workflows.md              # Guida operativa passo-passo
```

---

## 3. Configurazione

### 3.1 SweepConfig (top-level)

Modello Pydantic v2 in `config/models.py`. Caricabile da YAML con `SweepConfig.from_yaml(path)`, serializzabile con `to_yaml(path)`.

| Campo | Tipo | Default | Descrizione |
|---|---|---|---|
| `name` | `str` | *obbligatorio* | Nome identificativo dello sweep |
| `base_setup` | `Path` | *obbligatorio* | Directory contenente `train.py` |
| `metric` | `MetricConfig` | *obbligatorio* | Metrica da ottimizzare |
| `budget` | `BudgetConfig` | vedi §3.4 | Limiti budget esperimenti/tempo |
| `search_space` | `dict[str, ParameterSpec]` | *obbligatorio* | Spazio di ricerca (almeno 1 param) |
| `agent_rules` | `AgentRules` | vedi §3.7 | Regole e vincoli per l'agent |
| `strategy` | `StrategyConfig` | type=agent, parallel=4 | Tipo di strategia |
| `hardware` | `HardwareConfig` | backend=local | Backend di esecuzione |
| `agent_mode` | `AgentMode` | `hparam_only` | Modalita' operativa |
| `code_edit` | `CodeEditConfig` | vedi §3.8 | Configurazione code-edit |
| `escalation` | `EscalationConfig` | enabled=false | Escalation progressiva |
| `llm` | `LLMSettings` | vedi §3.10 | Impostazioni LLM |

### 3.2 ParameterSpec e Search Space

Tipo alias: `SearchSpace = dict[str, ParameterSpec]`

| ParamType | Campi richiesti | Validazione | Metodo `sample_uniform()` |
|---|---|---|---|
| `log_uniform` | `min`, `max` | `min > 0`, `min < max` | `exp(uniform(log(min), log(max)))` |
| `uniform` | `min`, `max` | `min < max` | `uniform(min, max)` |
| `choice` | `values` | lista non vuota | `random.choice(values)` |

Esempio:

```yaml
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
```

### 3.3 MetricConfig

| Campo | Tipo | Default | Descrizione |
|---|---|---|---|
| `name` | `str` | *obbligatorio* | Nome della metrica (es. `eval_f1`, `loss`) |
| `goal` | `MetricGoal` | `maximize` | `maximize` o `minimize` |

### 3.4 BudgetConfig

| Campo | Tipo | Default | Descrizione |
|---|---|---|---|
| `max_experiments` | `int` | `100` | Numero massimo di esperimenti (>=1) |
| `max_wall_time_hours` | `float` | `8.0` | Tempo muro massimo in ore (>0) |
| `max_run_time_seconds` | `float \| None` | `None` | Timeout per singolo esperimento (>=60) |
| `calibration` | `CalibrationConfig` | vedi sotto | Calibrazione dinamica timeout |

**CalibrationConfig:**

| Campo | Tipo | Default | Descrizione |
|---|---|---|---|
| `enabled` | `bool` | `False` | Attiva calibrazione automatica |
| `calibration_runs` | `int` | `3` | Numero run di calibrazione (>=1) |
| `timeout_multiplier` | `float` | `2.0` | Moltiplicatore tempo misurato (>1.0) |
| `min_timeout_seconds` | `float` | `120` | Timeout minimo (>=30) |
| `max_timeout_seconds` | `float \| None` | `None` | Timeout massimo opzionale |

### 3.5 StrategyConfig

| Campo | Tipo | Default | Descrizione |
|---|---|---|---|
| `type` | `StrategyType` | `agent` | `agent`, `random`, o `grid` |
| `waves_parallel` | `int` | `4` | Esperimenti per wave (>=1) |

**Confronto strategie:**

| Strategia | Generazione HP | LLM necessario | Caso d'uso |
|---|---|---|---|
| `agent` | LLM-driven (data-driven) | Si | Sweep complessi, search space ampi |
| `random` | Sampling casuale | No (analyst opzionale) | Baseline rapida, esplorazione iniziale |
| `grid` | Prodotto cartesiano | No (analyst opzionale) | Search space piccoli/discreti, sweep esaustivi |

### 3.6 HardwareConfig

| Campo | Tipo | Default | Descrizione |
|---|---|---|---|
| `backend` | `HardwareBackend` | `local` | `local`, `ssh`, `slurm`, `skypilot` |
| `max_concurrent_jobs` | `int` | `4` | Job paralleli massimi (>=1) |
| `ssh_host` | `str \| None` | `None` | Hostname SSH |
| `ssh_user` | `str \| None` | `None` | Utente SSH |
| `ssh_key_path` | `Path \| None` | `None` | Percorso chiave SSH |
| `partition` | `str \| None` | `None` | Partizione SLURM |
| `skypilot` | `SkyPilotConfig \| None` | `None` | Configurazione SkyPilot |

**SkyPilotConfig:**

| Campo | Tipo | Default | Descrizione |
|---|---|---|---|
| `accelerators` | `str` | `"A100:1"` | Tipo e quantita' GPU |
| `cloud` | `str \| None` | `None` | Provider cloud (aws, gcp, azure) |
| `region` | `str \| None` | `None` | Regione cloud |
| `instance_type` | `str \| None` | `None` | Tipo istanza specifica |
| `use_spot` | `bool` | `False` | Usa istanze spot/preemptible |
| `num_nodes` | `int` | `1` | Numero nodi per esperimento (>=1) |

### 3.7 AgentRules

| Campo | Tipo | Default | Descrizione |
|---|---|---|---|
| `rules_file` | `Path \| None` | `None` | File YAML regole aggiuntive |
| `constraints` | `list[str]` | `[]` | Vincoli hard (inviolabili) |
| `preferences` | `list[str]` | `[]` | Preferenze soft (best-effort) |
| `exploration_strategy` | `ExplorationStrategy` | `balanced` | `conservative`, `balanced`, `aggressive` |

Il file `personas/rules/default_rules.yaml` definisce le regole predefinite:

- **constraints** (7): base_setup read-only, meccanismo HPARAM_\*, rispetto budget, limiti concorrenza, parsing EXPERIMENT_RESULT, registrazione storico, timeout per-run
- **preferences** (7): priorita' parametri importanti, decisioni data-driven, evitare regioni crash, bilanciare miglioramento/stabilita', audit logging, early stopping su plateau, semplicita'
- **exploration**: `initial_random_waves: 2`, `explore_exploit_ratio: 0.3`, `patience_runs: 10`, `min_runs_for_importance: 5`
- **safety**: `max_crash_rate: 0.4`, `crash_blacklist_threshold: 3`, `gpu_hour_confirmation_threshold: 100`

### 3.8 AgentMode e CodeEditConfig

Due modalita' operative:

| Modalita' | Descrizione |
|---|---|
| `hparam_only` | L'agent modifica solo gli iperparametri (default) |
| `code_edit` | L'agent puo' anche modificare il codice di `train.py` |

**CodeEditConfig** (attiva solo in modalita' `code_edit`):

| Campo | Tipo | Default | Descrizione |
|---|---|---|---|
| `editable_files` | `list[str]` | `["train.py"]` | File modificabili dall'agent |
| `protected_files` | `list[str]` | `["prepare.py", "config.yaml", "requirements.txt"]` | File protetti (read-only) |
| `git_tracking` | `bool` | `True` | Tracciamento git delle modifiche |
| `snapshot_per_experiment` | `bool` | `True` | Snapshot git per ogni esperimento |

### 3.9 EscalationConfig

| Campo | Tipo | Default | Descrizione |
|---|---|---|---|
| `enabled` | `bool` | `False` | Attiva il sistema di escalation |
| `stages` | `list[EscalationStage]` | `[]` | Definizione degli stadi |
| `auto_generate` | `bool` | `True` | Generazione automatica degli stadi |

**EscalationStage:**

| Campo | Tipo | Default | Descrizione |
|---|---|---|---|
| `name` | `str` | *obbligatorio* | Nome descrittivo dello stadio |
| `parameters` | `list[str]` | *obbligatorio* | Parametri attivi in questo stadio |
| `min_experiments` | `int` | `5` | Esperimenti minimi prima di poter escalare |
| `plateau_patience` | `int` | `5` | Esperimenti senza miglioramento per escalare |
| `plateau_threshold` | `float` | `0.01` | Soglia di miglioramento minimo |

### 3.10 LLMSettings

| Campo | Tipo | Default | Descrizione |
|---|---|---|---|
| `enabled` | `bool` | `False` | Attiva nodi LLM-driven |
| `temperature` | `float` | `0.7` | Temperatura globale LLM |
| `max_tokens_per_call` | `int` | `4096` | Token massimi per singola chiamata |
| `max_total_tokens` | `int` | `500_000` | Budget token totale per lo sweep |

> **Nota:** Il routing LLM effettivo passa per `src.shared.llm.get_llm()` → LiteLLM proxy. Queste impostazioni controllano solo il comportamento dell'agent.

### 3.11 AutoresearchSettings (variabili d'ambiente)

Dataclass in `config/settings.py`, singleton `settings`:

| Campo | Tipo | Default | Env Var |
|---|---|---|---|
| `name` | `str` | `"autoresearch"` | — |
| `description` | `str` | `"AutoEvolve-inspired hyperparameter optimization"` | — |
| `model` | `str` | `"llm"` | `DEFAULT_MODEL` |
| `temperature` | `float` | `0.7` | — |
| `max_tokens` | `int` | `4096` | — |
| `max_total_tokens` | `int` | `500_000` | — |
| `db_uri` | `str` | `"postgresql://postgres:postgres@localhost:5433/vectors"` | `PGVECTOR_URI` |
| `db_schema` | `str` | `"autoresearch"` | — |
| `default_strategy` | `str` | `"agent"` | — |
| `tags` | `list[str]` | `["hyperparameter-optimization", "autoevolve", "multi-agent"]` | — |

### 3.12 Esempio YAML Completo

Scenario: fine-tuning LLaMA-7B su un task di classificazione testo.

```yaml
sweep:
  name: llama7b-text-classification
  base_setup: ./setups/llama_cls
  metric:
    name: eval_f1
    goal: maximize
  budget:
    max_experiments: 50
    max_wall_time_hours: 4.0
    max_run_time_seconds: 1800
    calibration:
      enabled: true
      calibration_runs: 3
      timeout_multiplier: 2.0
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
    num_epochs:
      type: choice
      values: [1, 2, 3, 5]
  agent_rules:
    rules_file: personas/rules/default_rules.yaml
    exploration_strategy: balanced
  strategy:
    type: agent
    waves_parallel: 4
  hardware:
    backend: local
    max_concurrent_jobs: 4
  agent_mode: hparam_only
  escalation:
    enabled: true
    stages:
      - name: core_params
        parameters: [learning_rate, batch_size]
        min_experiments: 5
        plateau_patience: 5
        plateau_threshold: 0.01
      - name: regularization
        parameters: [warmup_ratio, weight_decay]
        min_experiments: 5
        plateau_patience: 5
        plateau_threshold: 0.005
      - name: full_space
        parameters: [lora_r, num_epochs]
        min_experiments: 5
        plateau_patience: 8
        plateau_threshold: 0.002
  llm:
    enabled: true
    temperature: 0.7
    max_tokens_per_call: 4096
    max_total_tokens: 500000
```

---

## 4. State (AutoresearchState)

`AutoresearchState` e' un `TypedDict` con `total=False` (tutti i campi opzionali). L'unico campo con reducer e' `messages` (pattern `add_messages`). I nodi ritornano aggiornamenti parziali che sovrascrivono i campi corrispondenti.

| Campo | Tipo | Gruppo | Descrizione |
|---|---|---|---|
| `messages` | `Annotated[list[AnyMessage], add_messages]` | Core | Canale messaggi LangGraph (accumulatore) |
| `session_id` | `str` | Sessione | Identificativo univoco sessione (UUID hex[:16]) |
| `sweep_config` | `dict[str, Any]` | Sessione | Configurazione sweep serializzata |
| `wave_number` | `int` | Wave Control | Numero onda corrente (0-indexed) |
| `wave_configs` | `list[dict[str, Any]]` | Wave Control | Configurazioni HP dell'onda corrente |
| `wave_results` | `list[dict[str, Any]]` | Wave Control | Risultati dell'onda corrente |
| `trajectory` | `list[dict[str, Any]]` | Trajectory | Ultimi N esperimenti (storico per decisioni) |
| `experiments_completed` | `int` | Budget | Esperimenti completati totali |
| `experiments_remaining` | `int` | Budget | Esperimenti rimanenti nel budget |
| `wall_time_used_hours` | `float` | Budget | Tempo muro consumato (ore) |
| `best_run_id` | `str \| None` | Best Result | ID del miglior esperimento |
| `best_metric_value` | `float \| None` | Best Result | Valore migliore della metrica |
| `best_hyperparams` | `dict[str, Any]` | Best Result | HP della miglior configurazione |
| `parameter_importance` | `dict[str, float]` | Analysis | Importanza dei parametri [0..1] |
| `crash_patterns` | `list[str]` | Analysis | Pattern di crash identificati |
| `blacklist` | `list[dict[str, Any]]` | Analysis | Regioni HP da evitare |
| `loop_action` | `str` | Loop Control | `next_wave` \| `stop` \| `pause` \| `request_diagnostics` |
| `loop_reason` | `str` | Loop Control | Motivazione leggibile della decisione |
| `should_continue` | `bool` | Loop Control | Flag di continuazione dal wave analyst |
| `escalation_stage` | `int` | Escalation | Indice stadio di escalation corrente |
| `active_search_space` | `dict[str, Any]` | Escalation | Search space attivo (sottoinsieme progressivo) |
| `similar_experiments` | `list[dict[str, Any]]` | Knowledge | Esperimenti simili da Cognee/DB |
| `prior_knowledge` | `list[dict[str, Any]]` | Knowledge | Conoscenza pregressa da sweep passati |
| `token_usage` | `dict[str, int]` | Token Budget | `prompt_tokens`, `completion_tokens`, `calls` |
| `grid_configs` | `list[dict[str, Any]]` | Grid | Tutte le configurazioni del prodotto cartesiano |
| `grid_offset` | `int` | Grid | Offset corrente nella griglia |

---

## 5. Pipeline

### 5.1 Agent Pipeline (LLM-driven)

La pipeline piu' complessa: un loop supervisore dove agenti LLM decidono quali iperparametri provare, quando fermarsi, e quando diagnosticare crash. Implementa il pattern "metodo scientifico" di AutoEvolve.

![Agent Pipeline](../images/agent_pipeline.png)

**Nodi (12):** `initialize_session`, `query_trajectory`, `similarity_search`, `loop_operator`, `crash_diagnostician`, `hyperparams_advisor`, `validate_proposals`, `execute_wave`, `store_results`, `wave_analyst`, `update_escalation`, `persist_knowledge`

**Routing condizionale:**

- `_route_loop_action(state)` — legge `loop_action`:
  - `"stop"` o `"pause"` → `persist_knowledge`
  - `"request_diagnostics"` → `crash_diagnostician`
  - `"next_wave"` (default) → `hyperparams_advisor`
- `_route_after_escalation(state)` — legge `experiments_remaining` e `should_continue`:
  - Budget esaurito o analyst dice stop → `persist_knowledge`
  - Altrimenti → `query_trajectory` (loop back)

**Quando usarla:** sweep complessi dove le decisioni data-driven del LLM superano il valore del sampling casuale. Search space ampi (5+ parametri), budget significativi (50+ esperimenti).

### 5.2 Random Pipeline

Pipeline semplificata con sampling casuale. Nessun LLM per la generazione HP, ma il wave analyst LLM rimane attivo per early stop detection.

![Random Pipeline](../images/random_pipeline.png)

**Nodi (7):** `initialize_session`, `generate_random_wave`, `execute_wave`, `store_results`, `wave_analyst`, `update_escalation`, `persist_knowledge`

**Routing condizionale:**

- `_should_continue(state)`: `experiments_remaining <= 0` o `!should_continue` → `persist_knowledge`, altrimenti → `generate_random_wave`

**Quando usarla:** baseline rapida, esplorazione iniziale dello search space, validazione del setup prima di un agent sweep.

### 5.3 Grid Pipeline

Sweep esaustivo a prodotto cartesiano. Per parametri continui, discretizza in 5 punti equidistanti (log-scale per `log_uniform`).

![Grid Pipeline](../images/grid_pipeline.png)

**Nodi (8):** `initialize_session`, `generate_grid`, `slice_next_wave`, `execute_wave`, `store_results`, `wave_analyst`, `update_escalation`, `persist_knowledge`

**Routing condizionale:**

- `_should_continue(state)`: `experiments_remaining <= 0` o `grid_offset >= len(grid_configs)` o `!should_continue` → `persist_knowledge`, altrimenti → `slice_next_wave`

**Quando usarla:** search space piccoli/discreti dove si vuole copertura esaustiva. Attenzione all'esplosione combinatoria: 3 parametri con 5 valori ciascuno = 125 esperimenti.

### 5.4 Functional Pipeline (@entrypoint/@task)

Pipeline semplificata usando la Functional API di LangGraph. 5 task con loop Python imperativo e `InMemorySaver` checkpointer.

![Functional Pipeline](../images/functional_pipeline.png)

**Task (5):** `init_task` → `generate_task` → `execute_task` → `store_task` → `finish_task`

Nessun wave analyst, nessuna escalation. Il loop continua finche' `experiments_remaining > 0`.

**Quando usarla:** prototyping rapido, pipeline minimalista senza analisi LLM nel loop.

### 5.5 Selezione della Pipeline

`agent.py` espone `build_graph(strategy=None)`:

```python
from src.agents.autoresearch.agent import build_graph

graph = build_graph(strategy="agent")   # Pipeline agent
graph = build_graph(strategy="random")  # Pipeline random
graph = build_graph(strategy="grid")    # Pipeline grid
graph = build_graph()                   # Default da settings.default_strategy
```

Il `graph` e `workflow` esportati in `__init__.py` usano il default (`"agent"`).

---

## 6. Nodi

### 6.1 Tabella Riassuntiva

| Nodo | File | LLM | Pipeline | Comportamento chiave |
|---|---|---|---|---|
| `initialize_session` | `nodes/initialize_session.py` | No | Tutte | Crea/riprende sessione, carica prior knowledge |
| `query_trajectory` | `nodes/query_trajectory.py` | No | Agent | Recupera ultimi 100 esperimenti, ricalcola best e importance |
| `similarity_search` | `nodes/similarity_search.py` | No | Agent | Cerca esperimenti simili via Cognee + PostgreSQL |
| `loop_operator` | `nodes/loop_operator.py` | Si (T=0.3) | Agent | Decide: next_wave / stop / pause / request_diagnostics |
| `hyperparams_advisor` | `nodes/hyperparams_advisor.py` | Si (T=0.7) | Agent | Propone `waves_parallel` configurazioni HP |
| `validate_proposals` | `nodes/validate_proposals.py` | No | Agent | Clamp, deduplica, riempie proposte mancanti |
| `execute_wave` | `nodes/execute_wave.py` | No | Tutte | Esegue batch esperimenti sul runner selezionato |
| `store_results` | `nodes/store_results.py` | No | Tutte | Persiste risultati in PostgreSQL, aggiorna contatori |
| `wave_analyst` | `nodes/wave_analyst.py` | Si (T=0.3) | Agent, Random, Grid | Analisi post-wave, determina `should_continue` |
| `update_escalation` | `nodes/update_escalation.py` | No | Agent, Random, Grid | Rileva plateau, avanza stadio escalation |
| `crash_diagnostician` | `nodes/crash_diagnostician.py` | Si (T=0.2) | Agent | Classifica crash, aggiorna blacklist |
| `persist_knowledge` | `nodes/persist_knowledge.py` | No | Tutte | Salva conoscenza in DB + Cognee, chiude sessione |
| `generate_random_wave` | `nodes/generate_random_wave.py` | No | Random, Functional | Campiona N config casuali |
| `generate_grid` | `nodes/generate_grid.py` | No | Grid | Calcola prodotto cartesiano completo |
| `slice_next_wave` | `nodes/slice_next_wave.py` | No | Grid | Estrae prossimo batch dalla griglia |

### 6.2 initialize_session

Crea o riprende una sessione sweep in PostgreSQL. Se `session_id` e' presente nello state, carica la sessione esistente. Altrimenti crea un nuovo `session_id` (UUID hex[:16]), valida la `sweep_config` via `SweepConfig.model_validate()`, e persiste una nuova `SweepSession`. Carica prior knowledge dalla tabella `knowledge` tramite `KnowledgeRepository.find_relevant()`.

- **Legge:** `session_id`, `sweep_config`
- **Scrive:** `session_id`, `sweep_config`, `wave_number` (=0), `experiments_completed`, `experiments_remaining`, `wall_time_used_hours`, `best_run_id`, `best_metric_value`, `best_hyperparams`, `escalation_stage`, `active_search_space`, `prior_knowledge`, `parameter_importance` (={}), `crash_patterns` (=[]), `blacklist` (=[]), `should_continue` (=True), `loop_action` (="next_wave"), `token_usage`

### 6.3 query_trajectory

Recupera gli ultimi 100 esperimenti dalla tabella `experiments`. Ricalcola il best result iterando tutti gli esperimenti completati. Calcola crash rate e parameter importance (tramite variance analysis da `tracking.aggregator`) quando ci sono 3+ esperimenti completati.

- **Legge:** `session_id`, `sweep_config`
- **Scrive:** `trajectory`, `best_run_id`, `best_metric_value`, `best_hyperparams`, `parameter_importance`, `crash_patterns`, `experiments_completed`

### 6.4 similarity_search

Cerca esperimenti con setup simili per informare decisioni future. Prima tenta Cognee semantic search (`CogneeMemory.search_sync()`, top_k=5). Fallback silenzioso se Cognee non e' disponibile. Supplementa sempre con `KnowledgeRepository.find_relevant()` da PostgreSQL.

- **Legge:** `sweep_config` (estrae `base_setup` e `metric.name`)
- **Scrive:** `similar_experiments`

### 6.5 loop_operator

Nodo decisionale centrale. Carica la persona `loop-operator`. Invia all'LLM (T=0.3) un riassunto dello stato corrente: esperimenti completati/max, wall time, crash rate, best metric, wave number, crash patterns. L'LLM risponde con JSON `{action, reason}`. Override automatico: se `experiments_remaining <= 0`, forza `stop`. Registra la decisione in `agent_decisions` via `AgentDecisionRepository`.

- **Legge:** `sweep_config`, `experiments_completed`, `experiments_remaining`, `wall_time_used_hours`, `crash_patterns`, `best_metric_value`, `wave_number`, `trajectory`, `session_id`
- **Scrive:** `loop_action`, `loop_reason`, `wave_number` (+1 se next_wave)

### 6.6 hyperparams_advisor

Propone la prossima wave di configurazioni HP. Carica la persona `hyperparams-advisor`. Costruisce contesto con: search space, ultimi 10 esperimenti, parameter importance, esperimenti simili (top 3), blacklist. L'LLM (T=0.7) propone esattamente `waves_parallel` configurazioni come JSON.

- **Legge:** `sweep_config`, `trajectory`, `parameter_importance`, `similar_experiments`, `blacklist`, `active_search_space`, `wave_number`, `session_id`
- **Scrive:** `wave_configs`, `messages`

### 6.7 validate_proposals

Nodo deterministico (no LLM). Clamp delle proposte ai bounds dello search space. Valori numerici fuori range vengono clamped; choice non valide sostituite con random; parametri mancanti campionati a caso. Deduplica contro la traiettoria esistente tramite fingerprint `key=value|key=value`. Se le proposte valide sono meno di `waves_parallel`, riempie con sampling random.

- **Legge:** `wave_configs`, `active_search_space`, `trajectory`, `sweep_config`
- **Scrive:** `wave_configs` (validato)

### 6.8 execute_wave

Sottomette e monitora un batch di esperimenti. Crea il runner appropriato in base a `hardware.backend`. Per ogni configurazione in `wave_configs`, crea un `Experiment` con UUID, lo sottomette via `runner.submit()`. Polling ogni 5 secondi (max 720 poll = 1 ora). Parsa i risultati via `parse_experiment_output()`.

- **Legge:** `wave_configs`, `session_id`, `sweep_config`, `wave_number`
- **Scrive:** `wave_results`

### 6.9 store_results

Persiste i risultati in PostgreSQL. Per ogni risultato in `wave_results`, salva un `Experiment` via `ExperimentRepository.save()`. Aggiorna contatori sessione (`total_experiments`, `best_*`). Ricalcola `experiments_remaining`.

- **Legge:** `session_id`, `wave_results`, `sweep_config`, `experiments_completed`
- **Scrive:** `experiments_completed` (+N), `experiments_remaining`

### 6.10 wave_analyst

Analisi post-wave via LLM. Carica la persona `report-analyst`. Invia risultati della wave, progresso budget, wall time. L'LLM (T=0.3) risponde con JSON: `{should_continue, early_stop_reason, insights}`. Registra in `agent_decisions`.

- **Legge:** `sweep_config`, `experiments_completed`, `wall_time_used_hours`, `wave_results`, `wave_number`, `session_id`
- **Scrive:** `should_continue`

### 6.11 update_escalation

Controlla plateau e avanza lo stadio di escalation. Plateau = nessun miglioramento superiore a `plateau_threshold` negli ultimi `plateau_patience` esperimenti. Se rilevato, avanza `escalation_stage` e aggiunge i parametri dello stadio successivo ad `active_search_space`.

- **Legge:** `sweep_config`, `escalation_stage`, `trajectory`, `best_metric_value`, `active_search_space`
- **Scrive:** `escalation_stage` (+1, condizionale), `active_search_space` (espanso, condizionale)

### 6.12 crash_diagnostician

Analisi dei crash via LLM. Carica persona `crash-diagnostician`. Se non ci sono crash nella traiettoria, ritorna immediatamente. Altrimenti invia gli ultimi 5 crash all'LLM (T=0.2) che classifica i fallimenti (OOM, NaN, CUDA, timeout, dependency, data). Aggiorna `blacklist` e `crash_patterns`.

- **Legge:** `trajectory`, `blacklist`, `crash_patterns`
- **Scrive:** `blacklist` (esteso), `crash_patterns` (esteso)

### 6.13 persist_knowledge

Nodo terminale. Salva le conoscenze acquisite: sweep name, base setup, metric, best config, parameter importance, crash patterns, total experiments. Marca la sessione come COMPLETED. Opzionalmente scrive nel knowledge graph Cognee (dataset `"autoresearch"`). Fallback silenzioso se Cognee non e' disponibile.

- **Legge:** `session_id`, `sweep_config`, `best_hyperparams`, `best_metric_value`, `parameter_importance`, `crash_patterns`, `experiments_completed`
- **Scrive:** `messages`

### 6.14 generate_random_wave

Campiona `min(waves_parallel, experiments_remaining)` configurazioni casuali dallo `active_search_space`. Usa `ParameterSpec.sample_uniform()` per ogni parametro. Incrementa `wave_number`.

- **Legge:** `active_search_space`, `sweep_config`, `experiments_remaining`, `wave_number`
- **Scrive:** `wave_configs`, `wave_number` (+1)

### 6.15 generate_grid

Calcola il prodotto cartesiano completo dello search space. Per CHOICE: usa tutti i valori. Per UNIFORM: 5 punti equidistanti. Per LOG_UNIFORM: 5 punti log-spaced. Usa `itertools.product`. Inizializza `grid_offset = 0`.

- **Legge:** `active_search_space`
- **Scrive:** `grid_configs`, `grid_offset` (=0)

### 6.16 slice_next_wave

Estrae il prossimo batch di `min(waves_parallel, remaining, len(grid) - offset)` configurazioni dalla griglia pre-calcolata. Avanza `grid_offset`. Incrementa `wave_number`.

- **Legge:** `grid_configs`, `grid_offset`, `sweep_config`, `experiments_remaining`, `wave_number`
- **Scrive:** `wave_configs`, `grid_offset` (+N), `wave_number` (+1)

---

## 7. Tool LangGraph

| Tool | File | Parametri | Output |
|---|---|---|---|
| `sample_random_config` | `tools/sweep_tools.py` | `search_space_json: str` | JSON config casuale |
| `validate_config` | `tools/sweep_tools.py` | `config_json: str`, `search_space_json: str` | JSON `{config, valid, issues}` |
| `query_history` | `tools/experiment_tools.py` | `sweep_name: str`, `status: str = "completed"`, `limit: int = 20` | JSON array esperimenti |
| `get_trajectory` | `tools/experiment_tools.py` | `session_id: str`, `n: int = 50` | JSON array ultimi N esperimenti |
| `get_best_config` | `tools/experiment_tools.py` | `session_id: str`, `metric_name: str`, `goal: str = "maximize"`, `top_k: int = 3` | JSON array top-k esperimenti |
| `compute_parameter_importance` | `tools/analysis_tools.py` | `session_id: str`, `metric_name: str` | JSON dict parametro -> score [0,1] |
| `generate_sweep_report` | `tools/analysis_tools.py` | `session_id: str`, `metric_name: str`, `goal: str = "maximize"` | Report markdown completo |

---

## 8. Personas Agent

### 8.1 Tabella Riassuntiva

| Persona | Ruolo | Model Hint | Nodo Associato | Trigger Principale |
|---|---|---|---|---|
| `loop-operator` | Controllore ciclo sweep | sonnet | `loop_operator` | Inizio sweep, wave completata, soglia budget |
| `hyperparams-advisor` | Propone configurazioni HP | sonnet | `hyperparams_advisor` | loop_operator richiede next_wave |
| `crash-diagnostician` | Analizza esperimenti falliti | sonnet | `crash_diagnostician` | Crash rate > threshold |
| `report-analyst` | Analisi post-wave e report | sonnet | `wave_analyst` | Ogni wave completata, stop, checkpoint budget |
| `code-explorer` | Modifica train.py (CODE_EDIT) | sonnet | *(futuro)* | `agent_mode = code_edit` |
| `dependency-resolver` | Risolve conflitti dipendenze | haiku | *(futuro)* | Crash tipo dependency/import |

### 8.2 Formato File Persona

I file `.md` in `personas/agents/` usano frontmatter YAML + sezioni markdown:

```markdown
---
name: loop-operator
role: Orchestrate full sweep lifecycle
model_hint: sonnet
tools: [Read, Grep, Bash]
triggers: [sweep start, wave complete, budget threshold]
---

## System Prompt
...testo del system prompt...

## Protocol
...protocollo input/output...

## Examples
...esempi di utilizzo...

## Guardrails
...vincoli di sicurezza...
```

Il loader `prompts/personas.py` parsa il frontmatter e le sezioni in un `AgentPersona` dataclass.

---

## 9. Runner Backends

### 9.1 Interfaccia BaseRunner

Classe astratta in `runners/base.py`. Tutti i runner implementano:

| Metodo | Firma | Descrizione |
|---|---|---|
| `submit()` | `(run_id, setup_path, hparams, timeout_seconds) -> RunHandle` | Sottomette un esperimento |
| `poll()` | `(handle) -> RunStatus` | Controlla lo stato |
| `get_logs()` | `(handle) -> str` | Recupera i log |
| `cancel()` | `(handle) -> None` | Cancella l'esperimento |

**RunStatus** enum: `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`

**RunHandle** dataclass: `run_id`, `backend`, `pid`, `job_id`, `extra: dict`

Il metodo helper `_build_env(hparams)` converte il dict HP in variabili d'ambiente `HPARAM_*` (es. `HPARAM_LEARNING_RATE=0.001`).

### 9.2 LocalRunner

Esegue esperimenti come subprocess locale. Risoluzione entrypoint: `train.py` > `run.py` > `main.py`. Log in `autoresearch/.runs/<run_id>.log`. Gestisce timeout per singolo esperimento.

### 9.3 SSHRunner

Trasferisce il setup via `rsync`, lancia via `nohup` in background, monitora con `kill -0 <pid>`, legge log remoti. Directory remota: `~/autoresearch_runs`. Requisiti: SSH key-based auth, rsync installato su entrambe le macchine.

### 9.4 SLURMRunner

Genera script `sbatch` con direttive `#SBATCH`, sottomette via `sbatch --parsable`, monitora con `sacct`. Mapping stati SLURM:

| Stato SLURM | RunStatus |
|---|---|
| PENDING | PENDING |
| RUNNING | RUNNING |
| COMPLETED | COMPLETED |
| FAILED, TIMEOUT, NODE_FAIL, OUT_OF_MEMORY | FAILED |
| CANCELLED | CANCELLED |

### 9.5 SkyPilotRunner

Renderizza template Jinja2 `experiment_task.yaml.j2` per task YAML SkyPilot. Lancia con `sky launch -y -d`, monitora con `sky status --format json`, legge log con `sky logs --no-follow`. Ha metodo `teardown()` per distruggere cluster.

### 9.6 Protocollo EXPERIMENT_*

Contratto di comunicazione tra L1 (training script) e L2 (autoresearch):

**Input (L2 → L1):** variabili d'ambiente `HPARAM_*`

```bash
HPARAM_LEARNING_RATE=0.0003
HPARAM_BATCH_SIZE=16
HPARAM_WARMUP_RATIO=0.1
```

**Output (L1 → L2):** linee su stdout

```
EXPERIMENT_STATUS=completed
EXPERIMENT_RUN_ID=exp_abc123
EXPERIMENT_HYPERPARAMS={"learning_rate": 0.0003, "batch_size": 16}
EXPERIMENT_RESULT={"eval_f1": 0.87, "eval_loss": 0.42, "train_loss": 0.31}
```

---

## 10. Database PostgreSQL

Schema `autoresearch` dentro il database `vectors` (condiviso con PGVector). DDL in `db/schema.sql`.

### 10.1 sweep_sessions

| Colonna | Tipo | Default | Descrizione |
|---|---|---|---|
| `session_id` | `TEXT` | PK | Identificativo sessione |
| `sweep_name` | `TEXT` | NOT NULL | Nome sweep |
| `config_json` | `JSONB` | NOT NULL | Configurazione sweep completa |
| `strategy_type` | `TEXT` | NOT NULL | agent / random / grid |
| `status` | `TEXT` | `'active'` | active / paused / completed / cancelled |
| `created_at` | `TIMESTAMPTZ` | `NOW()` | Timestamp creazione |
| `updated_at` | `TIMESTAMPTZ` | `NOW()` | Timestamp ultimo aggiornamento |
| `wall_time_used_s` | `REAL` | `0.0` | Tempo muro consumato (secondi) |
| `escalation_stage` | `INT` | `0` | Stadio escalation corrente |
| `total_experiments` | `INT` | `0` | Esperimenti totali |
| `budget_max_experiments` | `INT` | NOT NULL | Limite budget esperimenti |
| `budget_max_wall_time_hours` | `REAL` | NOT NULL | Limite budget ore |
| `best_run_id` | `TEXT` | | ID miglior run |
| `best_metric_value` | `REAL` | | Valore miglior metrica |
| `best_hyperparams` | `JSONB` | `'{}'` | HP migliori |

### 10.2 experiments

| Colonna | Tipo | Default | Descrizione |
|---|---|---|---|
| `run_id` | `TEXT` | PK | Identificativo esperimento |
| `session_id` | `TEXT` | FK → sweep_sessions | Sessione di appartenenza |
| `sweep_name` | `TEXT` | NOT NULL | Nome sweep |
| `base_setup` | `TEXT` | NOT NULL | Directory setup |
| `hyperparams` | `JSONB` | NOT NULL | Iperparametri usati |
| `status` | `TEXT` | `'pending'` | pending / running / completed / crashed / cancelled |
| `parent_run_id` | `TEXT` | | Run genitore (se derivato) |
| `wave_number` | `INT` | | Numero onda |
| `metrics` | `JSONB` | `'{}'` | Metriche risultanti |
| `created_at` | `TIMESTAMPTZ` | `NOW()` | Timestamp creazione |
| `started_at` | `TIMESTAMPTZ` | | Timestamp inizio |
| `completed_at` | `TIMESTAMPTZ` | | Timestamp completamento |
| `wall_time_seconds` | `REAL` | | Durata in secondi |
| `agent_reasoning` | `TEXT` | | Motivazione dell'agent |
| `hardware_used` | `TEXT` | | Backend hardware usato |
| `notes` | `TEXT` | | Note libere |
| `code_diff` | `TEXT` | | Diff code-edit (se applicabile) |
| `runner_backend` | `TEXT` | | Tipo runner |
| `log_path` | `TEXT` | | Percorso file log |

Indici: `session_id`, `sweep_name`, `status`, `created_at`, `wave_number`

### 10.3 agent_decisions

| Colonna | Tipo | Descrizione |
|---|---|---|
| `decision_id` | `TEXT` PK | ID decisione |
| `session_id` | `TEXT` FK | Sessione |
| `agent_role` | `TEXT` | Persona agent |
| `decision_type` | `TEXT` | Tipo decisione |
| `input_summary` | `TEXT` | Riassunto input |
| `output_json` | `JSONB` | Output strutturato |
| `reasoning` | `TEXT` | Ragionamento LLM |
| `wave_number` | `INT` | Onda corrente |
| `token_usage` | `JSONB` | Token consumati |
| `created_at` | `TIMESTAMPTZ` | Timestamp |

### 10.4 knowledge

| Colonna | Tipo | Descrizione |
|---|---|---|
| `knowledge_id` | `TEXT` PK | ID conoscenza |
| `sweep_name` | `TEXT` | Nome sweep |
| `base_setup` | `TEXT` | Directory setup |
| `metric_name` | `TEXT` | Metrica ottimizzata |
| `best_config` | `JSONB` | Migliore configurazione HP |
| `best_metric_value` | `REAL` | Valore migliore |
| `parameter_importance` | `JSONB` | Importanza parametri |
| `parameter_recommendations` | `JSONB` | Raccomandazioni |
| `crash_patterns` | `JSONB` | Pattern di crash |
| `total_experiments` | `INT` | Esperimenti totali |
| `notes` | `TEXT` | Note |
| `created_at` | `TIMESTAMPTZ` | Timestamp |

### 10.5 checkpoints

| Colonna | Tipo | Descrizione |
|---|---|---|
| `checkpoint_id` | `TEXT` PK | ID checkpoint |
| `session_id` | `TEXT` FK | Sessione |
| `checkpoint_data` | `JSONB` | Stato serializzato |
| `created_at` | `TIMESTAMPTZ` | Timestamp |

### 10.6 Repository Classes

| Classe | Metodi principali |
|---|---|
| `SweepSessionRepository` | `save()`, `get()`, `update_status()`, `update_best()` |
| `ExperimentRepository` | `save()`, `list_by_sweep()`, `list_by_session()`, `get_trajectory()`, `get_best()`, `update_status()`, `count()` |
| `AgentDecisionRepository` | `save()`, `list_by_session()` |
| `KnowledgeRepository` | `save()`, `find_relevant()` |
| `CheckpointRepository` | `save()`, `get_latest()` |

`PostgresConnector`: lazy connection pool via `psycopg_pool.ConnectionPool` (min=1, max=5). Metodi: `execute()`, `execute_returning()`, `apply_schema()`, `close()`.

---

## 11. Sistema di Escalation

### 11.1 Concetto

Lo search space inizia ristretto ai parametri piu' importanti (stadio 0) e si espande progressivamente quando il sistema rileva un plateau. Questo permette di focalizzare l'esplorazione iniziale e aggiungere complessita' solo quando necessario.

### 11.2 Rilevamento Plateau

**Algoritmo:**

1. Dopo ogni wave, `update_escalation` controlla se l'escalation e' abilitata e ci sono stadi definiti
2. Verifica che siano stati completati almeno `min_experiments` esperimenti nello stadio corrente
3. Prende gli ultimi `plateau_patience` esperimenti
4. Calcola il miglioramento relativo: `|current_best - previous_best| / |previous_best|`
5. Se il miglioramento e' sotto `plateau_threshold`, dichiara plateau e avanza allo stadio successivo
6. Aggiunge i parametri del nuovo stadio ad `active_search_space`

**Esempio numerico:**

```
Stadio 0: learning_rate, batch_size
  Esperimenti 1-10: best = 0.72 → 0.81 → 0.84 → 0.845 → 0.848
  Miglioramento ultimi 5: (0.848 - 0.845) / 0.845 = 0.0035 < threshold 0.01
  → Plateau! Avanzo a stadio 1.

Stadio 1: + warmup_ratio, weight_decay
  Esperimenti 11-20: best = 0.855 → 0.87 → 0.88 ...
```

---

## 12. Token Budget

`TokenTracker` in `config/token_budget.py` traccia il consumo cumulativo di token LLM.

| Proprieta'/Metodo | Tipo | Descrizione |
|---|---|---|
| `max_total_tokens` | `int` | Budget massimo (default: 500,000) |
| `prompt_tokens` | `int` | Token prompt consumati |
| `completion_tokens` | `int` | Token completion consumati |
| `calls` | `int` | Numero chiamate LLM |
| `total_tokens` | `property` | `prompt_tokens + completion_tokens` |
| `budget_remaining` | `property` | `max(0, max_total - total)` |
| `exhausted` | `property` | `total >= max_total` |
| `record(usage)` | `method` | Registra uso da una singola chiamata |
| `can_afford(n)` | `method` | Verifica se il budget permette N token aggiuntivi |
| `to_state_dict()` | `method` | Serializza per embedding nello state |
| `summary()` | `method` | `"Token: 12,340/500,000 (...)"` |

---

## 13. Tracking e Analytics

### 13.1 Aggregator

| Funzione | Descrizione |
|---|---|
| `best_config(entries, metric_name, goal)` | Ritorna il singolo miglior esperimento completato |
| `top_k_configs(entries, metric_name, goal, k)` | Ritorna i top-k per metrica |
| `parameter_importance(entries, metric_name)` | Importanza parametri via variance-of-group-means, normalizzato a [0,1] |

### 13.2 Reporter

`generate_report()` produce un report markdown completo: migliore configurazione, top-10 tabella, parameter importance con bar chart inline, distribuzioni parametri, suggerimenti automatici.

### 13.3 Result Parser

`parse_experiment_output(log_text)` → `ParsedResult` dataclass. `extract_metric(log_text, metric_name)` → float.

---

## 14. Knowledge Graph (Cognee)

Integrazione **opzionale** con Cognee per knowledge transfer semantico cross-sweep.

| Nodo | Operazione | Fallback |
|---|---|---|
| `similarity_search` | `CogneeMemory.search_sync(query, top_k=5)` | Solo PostgreSQL `knowledge` table |
| `persist_knowledge` | `CogneeMemory.add_and_cognify_sync(text, dataset="autoresearch")` | Solo PostgreSQL |

---

## 15. Schema I/O

### AutoresearchInput

| Campo | Tipo | Default | Descrizione |
|---|---|---|---|
| `sweep_config_path` | `str \| None` | `None` | Percorso file YAML |
| `sweep_config` | `dict \| None` | `None` | Config inline (alternativa a file) |
| `session_id` | `str \| None` | `None` | Riprendi sessione esistente |
| `strategy_override` | `str \| None` | `None` | Override strategia |

### AutoresearchOutput

| Campo | Tipo | Default | Descrizione |
|---|---|---|---|
| `session_id` | `str` | | ID sessione |
| `sweep_name` | `str` | | Nome sweep |
| `strategy` | `str` | | Strategia usata |
| `experiments_completed` | `int` | | Esperimenti completati |
| `best_run_id` | `str \| None` | `None` | ID miglior esperimento |
| `best_metric_value` | `float \| None` | `None` | Valore migliore |
| `best_hyperparams` | `dict` | `{}` | HP migliori |
| `parameter_importance` | `dict[str, float]` | `{}` | Importanza parametri |
| `summary` | `str` | `""` | Riassunto testuale |

---

## 16. Osservabilita'

`__init__.py` chiama `setup_tracing()` da `src.shared.tracing` prima della compilazione del graph. `phoenix.otel.register(auto_instrument=True)` instrumenta automaticamente tutte le operazioni LangGraph via OpenTelemetry.

- **Phoenix UI:** http://localhost:6006 (dev) o via `make k8s-port-forward-phoenix` (K8s)
- **Backend:** PostgreSQL (database `phoenix`)
- **Audit:** I nodi LLM registrano `token_usage` in `agent_decisions` per audit granulare

---

## 17. Test

```bash
pytest src/agents/autoresearch/tests/ -v
```

**Fixture** (`conftest.py`): `minimal_sweep_config` (2 HP, 5 esperimenti), `sample_trajectory` (3 esperimenti)

| Classe | Test | Verifica |
|---|---|---|
| `TestGraphCompilation` | 5 | Compilazione pipeline, import default, build_graph() |
| `TestState` | 1 | Campi attesi in AutoresearchState |
| `TestConfig` | 3 | SweepConfig validation, sampling |
| `TestEntities` | 2 | Round-trip Experiment e SweepSession |
| `TestTools` | 3 | Importabilita' e nomi dei 7 tool |
| `TestNodes` | 4 | validate_proposals, generate_random_wave, generate_grid, slice_next_wave |

---

## 18. Mappa dei File

| File | Descrizione |
|---|---|
| `__init__.py` | Setup tracing, esporta `graph` e `workflow` |
| `agent.py` | `build_graph(strategy)` dispatcher |
| `config/models.py` | Pydantic v2: SweepConfig + 14 sotto-modelli |
| `config/settings.py` | AutoresearchSettings dataclass (env-driven) |
| `config/token_budget.py` | TokenTracker per budget LLM |
| `db/connector.py` | PostgresConnector (psycopg3 pool) |
| `db/repositories.py` | 5 repository classes CRUD |
| `db/schema.sql` | DDL schema autoresearch (5 tabelle) |
| `escalation/tracker.py` | EscalationTracker (plateau detection) |
| `images/generate_diagrams.py` | Script generazione PNG Mermaid |
| `nodes/initialize_session.py` | Crea/riprende sessione sweep |
| `nodes/query_trajectory.py` | Recupera storico esperimenti |
| `nodes/similarity_search.py` | Ricerca semantica Cognee + DB |
| `nodes/loop_operator.py` | Decisione LLM: continue/stop/pause/diagnostics |
| `nodes/hyperparams_advisor.py` | Proposta HP via LLM |
| `nodes/validate_proposals.py` | Validazione e clamp proposte |
| `nodes/execute_wave.py` | Esecuzione batch esperimenti |
| `nodes/store_results.py` | Persistenza risultati |
| `nodes/wave_analyst.py` | Analisi post-wave LLM |
| `nodes/update_escalation.py` | Plateau detection e escalation |
| `nodes/crash_diagnostician.py` | Diagnosi crash via LLM |
| `nodes/persist_knowledge.py` | Salvataggio conoscenza |
| `nodes/generate_random_wave.py` | Sampling casuale HP |
| `nodes/generate_grid.py` | Prodotto cartesiano search space |
| `nodes/slice_next_wave.py` | Batch dalla griglia |
| `pipelines/agent_pipeline.py` | Agent pipeline (12 nodi, full LLM) |
| `pipelines/grid_pipeline.py` | Grid pipeline (8 nodi) |
| `pipelines/random_pipeline.py` | Random pipeline (7 nodi) |
| `pipelines/pipeline.py` | Functional API (@entrypoint/@task) |
| `prompts/system.py` | 5 prompt costanti |
| `prompts/personas.py` | AgentPersona loader da .md |
| `runners/base.py` | BaseRunner ABC, RunHandle, RunStatus |
| `runners/local_runner.py` | Subprocess locale |
| `runners/ssh_runner.py` | rsync + SSH remoto |
| `runners/slurm_runner.py` | SLURM sbatch/sacct |
| `runners/skypilot_runner.py` | SkyPilot cloud GPU |
| `schemas/entities.py` | 5 dataclass entita' |
| `schemas/io.py` | AutoresearchInput / AutoresearchOutput |
| `states/state.py` | AutoresearchState TypedDict (27 campi) |
| `tools/sweep_tools.py` | sample_random_config, validate_config |
| `tools/experiment_tools.py` | query_history, get_trajectory, get_best_config |
| `tools/analysis_tools.py` | compute_parameter_importance, generate_sweep_report |
| `tracking/aggregator.py` | best_config, top_k_configs, parameter_importance |
| `tracking/reporter.py` | generate_report() markdown |
| `tracking/result_parser.py` | Parser protocollo EXPERIMENT_* |
| `tests/conftest.py` | Fixture test |
| `tests/test_agent.py` | 6 classi, 18 test |
