# SkyPilot Experiment Orchestrator — Reference & Execution Guide

Orchestratore centralizzato per la pianificazione e l'esecuzione sequenziale di esperimenti DPO su macchine dedicate (ambiente Azure/Localhost a singola GPU). Questo sistema sfrutta la coda interna di un **SSH Node Pool** gestito da SkyPilot per ottimizzare l'allocazione hardware senza saturare la memoria della GPU, garantendo un'architettura robusta, isolata e priva di race condition.

---

## 📐 Visione ad Alto Livello & Architettura

Il sistema è strutturato per orchestrare $N$ varianti di configurazione (ad esempio, combinazioni di Learning Rate e Beta) ereditando i parametri da un file di configurazione base e iniettando automaticamente i metadati per il tracciamento della *lineage*.

### Struttura delle Directory

```
/dpo-setup/modules/skypilot/

├── .sky/                       # Contiene configurazione del cluster locale/ssh/k8/cloud
│   └── ssh_node_pools.yaml     # host configs, ssh 
├── schedules/
│   └── base_schedule.sh        # Script orchestratore principale (Python-backed)
├── tasks/
│   └── task_template.yaml      # Template del Task SkyPilot con tag di runtime
├── variants/                   # Contiene gli override da inserire nella configurazione
│   ├── lr_high_beta_strong.yml # Esempio: override learning rate e beta
│   └── lora_small.yml          # Esempio: override parametri LoRA
└── generated/                  # Output di runtime isolati (in .gitignore)
    └── run_[timestamp]_[i]/    # Sandbox univoca per singolo Job ID (Isolamento Totale)
        ├── config_variant.yml  # Config completo (Base + Lineage + Variante)
        └── task_variant.yaml   # Task YAML finale compilato per Sky Queue

```

### Il Flusso dei Dati (Workflow)

```
┌─────────────┐     ┌──────────────────────────────┐     ┌──────────────────────────────────┐
│ config.yml  │────>│                              │────>│ generated/run_[timestamp]_[i]/   │
│ (base)      │     │      base_schedule.sh        │     │  ├── config_variant.yml          │
└─────────────┘     │                              │     │  └── task_variant.yaml           │
                    │   - Estrazione HW Python     │     └────────────────┬─────────────────┘
┌─────────────┐     │   - Deep Merge Relazionale   │                      │
│ .lineage/   │────>│   - Lineage Injection        │                      v
│ exp.yml     │     │   - Compilazione Template    │         ┌──────────────────────────┐
└─────────────┘     │                              │         │       sky launch         │
                    └──────────────────────────────┘         │  (In coda sequenziale)   │
┌─────────────┐                    ▲                         └────────────┬─────────────┘
│ variants/   │────────────────────┘                                      │
│  *.yml      │                                                           v
└─────────────┘                                              ┌──────────────────────────┐
                                                             │     Sky Pilot Queue      │
                                                             │ ┌──────────────────────┐ │
                                                             │ │ Job 0: RUNNING (GPU) │ │
                                                             │ └──────────────────────┘ │
                                                             │ ┌──────────────────────┐ │
                                                             │ │ Job 1: PENDING       │ │
                                                             │ └──────────────────────┘ │
                                                             └──────────────────────────┘

```

**Passo per passo:**

1. **Fase di Parsing:** Un motore Python interno *inline* analizza in modo sicuro il file `config.yml` base del progetto e il file `.lineage/experiment.yml`. Estrae le risorse hardware pulendole dai modificatori di stringa (come il simbolo `+` dai core CPU o dalla memoria RAM) per renderle conformi agli standard di SkyPilot.
2. **Generazione della Sandbox (Isolamento Totale Antimutazione):** Per ciascuna variante passata come argomento CLI, viene creata una sottocartella "sandbox" temporanea e univoca marchiata con timestamp e indice all'interno di `generated/`. Python esegue un *deep-merge* ricorsivo integrando il Config Base, la Variante e i metadati di Lineage.
3. **Iniezione Lineage:** Viene estratto l'UUID del *Base Experiment* e iniettato automaticamente nel campo `experiment.base_experiment_id` del config generato. Questo permette al tracker (`@envelope.tracker()`) di mappare una topologia a stella nel grafo degli esperimenti, dove tutte le varianti sottomesse in coda sanno di derivare dallo stesso identico esperimento radice.
4. **Compilazione del Task:** Il file `tasks/task_template.yaml` viene letto e i tag statici di runtime (`__TAG__`) vengono sostituiti con i percorsi assoluti e relativi corretti della sandbox, generando il file `task_variant.yaml`.
5. **Accodamento Centralizzato:** L'orchestratore invia il task compilato a SkyPilot tramite `sky launch -c <cluster_name> <task.yaml> -y --detach`. Grazie al flag `--detach`, il controllo viene restituito immediatamente alla shell Bash: lo script carica istantaneamente tutte le varianti nella coda di esecuzione dell'SSH Node Pool locale.
6. **Esecuzione Protetta sulla GPU:** SkyPilot esegue un job alla volta rispettando la disponibilità dell'unica GPU del cluster finto-localhost. Durante la fase di `setup` del task, la configurazione unita viene copiata nella directory `/tmp/` della macchina e viene attivato il `.venv` locale in modalità *Read-Only*, garantendo un avvio immediato senza reinstallazioni ridondanti.

---

## ⚙️ Configurazione Iniziale dell'Infrastruttura Locale (SSH Node Pool)

Prima di poter utilizzare l'orchestratore, SkyPilot deve conoscere e inizializzare la macchina Azure locale come pool di calcolo. **Questa operazione va eseguita una sola volta (una tantum)** o in caso di riavvio del server.

1. Creare (se non presente) il file di mappatura degli host:
```bash
mkdir -p ~/.sky
nano ~/.sky/ssh_node_pools.yaml

```
**NOTA**: questa operazione richiede setup delle chiavi rsa e dei relativi permessi! Permission denied o key not found potrebbe succedere!
#### esempio: 
```bash
Failed to deploy 1 cluster(s): 
cluster: SSH Identity File Missing: /home/velvet/.ssh/* 
RuntimeError: Failed to deploy SkyPilot on some Node Pools.
```

2. Configurare il cluster associando l'IP di loopback (o l'IP privato della macchina Azure) al nome utilizzato dall'orchestratore (`azure-gpu-cluster`):
```yaml
azure-gpu-cluster:
  hosts:
    - 127.0.0.1

```


3. Lanciare il comando di provisioning e accoppiamento SSH di SkyPilot:
```bash
sky ssh up

```


4. Verificare lo stato di attivazione con `sky check`. Una volta abilitato, il cluster è pronto a ricevere i job dell'orchestratore.

---

## 🛠️ Componenti del Sistema

### `schedules/base_schedule.sh`

Il motore di orchestrazione. Centralizza la logica di estrazione dei dati hardware, risolve le dipendenze di configurazione tramite script Python integrati ed esegue il deployment asincrono dei task sulla coda hardware locale tramite `sky launch`.

### `tasks/task_template.yaml`

Il blueprint dei compiti di SkyPilot. Mappa le risorse minime richieste, imposta il puntamento corretto alla cartella radice (`workdir`), mette in sicurezza il file yaml di configurazione duplicandolo a runtime in `/tmp/skypilot_configs/runtime_config.yml` e lancia il comando di addestramento:

```yaml
python train.py --config /tmp/skypilot_configs/runtime_config.yml

```

### `variants/`

File YAML minimali che contengono **esclusivamente le chiavi e i parametri da sovrascrivere** (es. variazioni di `learning_rate` o coefficienti `beta`).

* **Constraints per i file `variants/*.yml`:**
* **DEVE contenere:** `experiment.id` compilato con un identificativo human-readable.
* **NON DEVE contenere:** `experiment.base_experiment_id` o `experiment.previous_experiment_id` (gestiti automaticamente dall'orchestratore).



---

## 🚀 Guida di Esecuzione del Workflow

Posizionarsi nella directory dell'orchestratore all'interno della macchina Azure:

```bash
cd /home/velvet/DPO-unsloth-setup/modules/accelerators/orchestrator/skypilot

```

### 1. Fase di Validazione (Dry Run)

Il dry-run permette di ispezionare l'output generato, la struttura del deep-merge e i file di task compilati senza impegnare la GPU o inviare istruzioni di calcolo a SkyPilot:

```bash
bash schedules/base_schedule.sh --dry-run variants/*.yml

```

### 2. Esecuzione della Coda (Lancio Reale)

Per lanciare la pipeline sequenziale di tutti gli esperimenti e le varianti trovate nella cartella, invia il comando all'orchestratore. È consigliato reindirizzare l'output su un file di log:

```bash
# Esecuzione nativa sequenziale della coda
bash schedules/base_schedule.sh variants/*.yml

# Esecuzione raccomandata con storicizzazione del log dell'orchestratore
bash schedules/base_schedule.sh variants/*.yml 2>&1 | tee generated/submission_$(date +%Y%m%d_%H%M%S).log

# Lancio impostando un prefisso personalizzato per identificare i compiti nel cluster
bash schedules/base_schedule.sh --cluster-prefix dpo-sweep-1 variants/*.yml

```

### 3. Gestione di Interruzioni o Errori Mid-Run

Se un esperimento all'interno della coda fallisce (es. crash del codice Python, Out of Memory della VRAM), **la coda di SkyPilot non si interrompe**. L'esperimento fallito viene marcato come `FAILED`, la GPU viene rilasciata e il job successivo in stato `PENDING` viene avviato immediatamente.

Se interrompi bruscamente l'orchestratore (Ctrl+C) mentre sta sottomettendo i job, i compiti già inviati rimarranno memorizzati al sicuro all'interno della coda della macchina. Per riprendere l'esecuzione in un secondo momento con le varianti escluse, basterà indicarle esplicitamente:

```bash
bash schedules/base_schedule.sh variants/lr_2e-07_beta_03.yml variants/lr_1e-06_beta_01.yml
```

---

## 📊 Monitoraggio & Amministrazione del Runtime

Lavorando su un pool SSH locale (finto-localhost), la gestione dell'infrastruttura si sposta interamente sui comandi nativi di controllo della coda di SkyPilot (`sky queue`, `sky logs`, `sky cancel`).

### Comandi Fondamentali di Gestione

| Comando | Scopo | Descrizione |
| --- | --- | --- |
| `sky queue azure-gpu-cluster` | **Ispezione Coda** | Mostra l'elenco in tempo reale di tutti i job inviati al cluster locale, l'ID univoco, lo stato attuale (`RUNNING`, `PENDING`, `SUCCEEDED`, `FAILED`) e le risorse allocate. |
| `sky logs azure-gpu-cluster <JOB_ID> -f` | **Log in Tempo Reale** | Aggancia lo stream di output (`stdout`/`stderr`) dell'esperimento selezionato sul cluster, mostrando l'avanzamento del training. |
| `sky cancel azure-gpu-cluster <JOB_ID>` | **Uccidere un Esperimento** | Interrompe immediatamente il job specificato se in esecuzione (liberando la GPU) o lo rimuove dalla lista d'attesa se in stato `PENDING`. |
| `nvidia-smi -l 1` | **Stato Hardware Reale** | Verificato direttamente sulla macchina host per monitorare l'uso dei core CUDA e della VRAM dell'A100/H100 Azure. |

### Strategie di Storicizzazione dei Log

* **Log di SkyPilot:** I log completi dei task e delle fasi di setup sono memorizzati localmente da SkyPilot nella cartella home dell'utente: `~/.sky/logs/`.
* **Storicizzazione delle varianti:** Grazie all'architettura a sandbox isolata, ogni file di configurazione effettivo utilizzato da un esperimento rimane salvato e accessibile in `generated/run_*/config_*.yml`.

---

## 🆘 Comandi di Emergenza

```bash
# Interrompe e cancella IMMEDIATAMENTE tutti i job (attivi e pendenti) nella coda del cluster
sky cancel azure-gpu-cluster --all

# Pulisce i file temporanei locali generati dall'orchestratore (Reset dello staging locale)
rm -rf generated/run_*

# Verifica lo stato di salute generale di SkyPilot e dei backend
sky check

```