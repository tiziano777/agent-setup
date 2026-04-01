# Guida ai comandi del Makefile

Riferimento completo di tutti i comandi `make` disponibili, organizzati per sezione.

---

## Sviluppo Locale (Ecosistema Completo)

Comandi per gestire l'intero ecosistema locale (LiteLLM proxy, Qdrant, PostgreSQL, Phoenix, Neo4j, Fuseki) tramite `docker-compose.yml`. Il codice Python gira direttamente sul tuo PC.

| Comando | Cosa fa |
|---------|---------|
| `make build` | Builda le immagini e avvia l'intero ecosistema dev in background |
| `make down` | Ferma tutti i container dell'ecosistema locale |
| `make rebuild` | Ricostruisce le immagini Docker senza avviare i container |
| `make rebuild-up` | Ricostruisce le immagini e riavvia tutto |

---

## Infrastruttura Modulare (`docker-parts/`)

Avvio selettivo dei singoli moduli. Ogni modulo e un file compose autonomo in `docker-parts/`. Tutti condividono la rete `agent-net` e volumi con nomi espliciti, quindi sono componibili liberamente.

> **Nota**: LiteLLM e il gateway obbligatorio per ogni workflow agentico. Avviarlo sempre come primo modulo.

### Moduli Singoli

| Comando | Cosa fa | Compose |
|---------|---------|---------|
| `make llm-up` | Avvia LiteLLM proxy (porta 4000) | `docker-parts/llm.yml` |
| `make llm-down` | Ferma LiteLLM | |
| `make llm-logs` | Log LiteLLM | |
| `make vectordb-up` | Avvia Qdrant (porta 6333/6334) | `docker-parts/vectordb.yml` |
| `make vectordb-down` | Ferma Qdrant | |
| `make vectordb-logs` | Log Qdrant | |
| `make database-up` | Avvia PostgreSQL/pgvector (porta 5433) | `docker-parts/database.yml` |
| `make database-down` | Ferma PostgreSQL | |
| `make database-logs` | Log PostgreSQL | |
| `make observability-up` | Avvia Phoenix + PostgreSQL (auto-incluso) (porta 6006) | `docker-parts/observability.yml` |
| `make observability-down` | Ferma Phoenix + PostgreSQL | |
| `make observability-logs` | Log Phoenix | |
| `make graphdb-up` | Avvia Neo4j (porta 7474/7687) | `docker-parts/graphdb.yml` |
| `make graphdb-down` | Ferma Neo4j | |
| `make graphdb-logs` | Log Neo4j | |
| `make rdf-up` | Avvia Fuseki (porta 3030) | `docker-parts/rdf.yml` |
| `make rdf-down` | Ferma Fuseki | |
| `make rdf-logs` | Log Fuseki | |

> Legacy aliases: `make fuseki-up/down/logs` funzionano ancora (alias a `rdf-*`).

### Composizione Multi-Modulo

| Comando | Cosa fa |
|---------|---------|
| `make modules-up m="llm vectordb rdf"` | Avvia i moduli specificati insieme |
| `make modules-down m="llm vectordb rdf"` | Ferma i moduli specificati |
| `make modules-ps m="llm vectordb"` | Stato container dei moduli specificati |
| `make up-all` | Avvia tutti i moduli via `docker-parts/` |
| `make down-all` | Ferma tutti i moduli |
| `make ps-all` | Stato di tutti i container modulari |
| `make help-modules` | Guida completa moduli con matrice dipendenze |

### Matrice Dipendenze

| Modulo | Dipende da |
|--------|-----------|
| `llm` | nessuno (prerequisito per tutti) |
| `vectordb` | nessuno |
| `database` | nessuno |
| `observability` | `database` (auto-incluso) |
| `graphdb` | nessuno |
| `rdf` | nessuno |

---

## LLM Proxy

Comandi per monitorare e testare il proxy LiteLLM che gestisce la rotazione tra provider LLM.

| Comando | Cosa fa |
|---------|---------|
| `make llm-proxy-health` | Controlla se il proxy risponde su `localhost:4000` |
| `make llm-proxy-logs` | Mostra i log in tempo reale del proxy |
| `make llm-proxy-restart` | Riavvia il proxy (utile dopo modifica a `proxy_config.yml`) |
| `make llm-proxy-test` | Invia una richiesta di test al rotator (scelta casuale del provider) |
| `make test-all` | Testa ogni singolo modello/provider definito in `proxy_config.yml` |

---

## Agent Management

Comandi per creare e gestire gli agenti.

| Comando | Cosa fa | Parametri |
|---------|---------|-----------|
| `make new-agent name=mio_agente` | Crea un nuovo agente copiando il template `_template` | `name` (obbligatorio): nome dell'agente |
| `make list-agents` | Elenca tutti gli agenti disponibili (escluso `_template`) | - |

---

## Development

Comandi per lo sviluppo quotidiano: installazione, test, linting.

| Comando | Cosa fa | Parametri |
|---------|---------|-----------|
| `make install` | Installa il progetto in modalita development (`pip install -e ".[dev]"`) | - |
| `make test` | Esegue tutti i test con pytest | - |
| `make test-agent name=agent1` | Esegue i test di un singolo agente | `name` (obbligatorio): nome agente |
| `make lint` | Controlla il codice con ruff (senza modificare) | - |
| `make fmt` | Formatta automaticamente il codice con ruff | - |

---

## Produzione - Docker Compose (On-Prem)

Comandi per gestire lo stack completo containerizzato tramite `docker-compose.prod.yml`. In questo scenario **tutto** gira in Docker: app Python + infrastruttura.

### Lifecycle

| Comando | Cosa fa |
|---------|---------|
| `make prod-build` | Builda le immagini e avvia tutto lo stack produzione in background |
| `make prod-up` | Avvia lo stack produzione senza ricostruire le immagini |
| `make prod-down` | Ferma tutto lo stack produzione |
| `make prod-down-volumes` | Ferma tutto e **cancella i dati persistenti** (Qdrant + PostgreSQL) |
| `make prod-rebuild` | Ricostruisce solo le immagini, senza avviare |
| `make prod-rebuild-app` | Ricostruisce e riavvia solo il container dell'app (scelta rapida dopo modifiche al codice) |
| `make prod-restart service=app` | Riavvia un singolo servizio. Valori: `app`, `litellm-proxy`, `qdrant`, `postgres-vector`, `phoenix`, `neo4j`, `fuseki` |

### Monitoraggio

| Comando | Cosa fa |
|---------|---------|
| `make prod-logs` | Log in tempo reale di tutti i servizi |
| `make prod-logs-app` | Log in tempo reale solo dell'app |
| `make prod-logs-proxy` | Log in tempo reale solo del proxy LLM |
| `make prod-ps` | Mostra lo stato di tutti i container produzione |

---

## Test dei Moduli

Comandi per testare singolarmente ogni componente del sistema. Funzionano sia in locale che in produzione, purche' i servizi siano in ascolto sulle porte attese.

### Database

| Comando | Cosa fa |
|---------|---------|
| `make test-db-qdrant` | Verifica che Qdrant risponda su `localhost:6333` |
| `make test-db-postgres` | Verifica che PostgreSQL risponda su `localhost:5433` |
| `make test-db` | Esegue entrambi i test database |

### App (FastAPI / serve.py)

Questi test verificano l'app containerizzata su porta 8000. Richiedono che lo stack produzione sia avviato (`make prod-build`).

| Comando | Cosa fa |
|---------|---------|
| `make test-app-health` | Chiama `GET /health` e verifica la risposta |
| `make test-app-invoke` | Chiama `POST /invoke` con un messaggio di test e mostra la risposta |
| `make test-app` | Esegue health + invoke in sequenza |

### Agenti

| Comando | Cosa fa |
|---------|---------|
| `make test-agent name=agent1` | Esegue pytest sui test di un singolo agente |
| `make test-agents` | Esegue pytest su **tutti** gli agenti (esclude `_template`) |

### Observability e RDF

| Comando | Cosa fa |
|---------|---------|
| `make test-phoenix` | Healthcheck di Phoenix su `localhost:6006` |
| `make test-fuseki` | Healthcheck di Fuseki su `localhost:3030` |
| `make test-rdf` | Test di integrazione modulo rdf_memory |
| `make phoenix-logs` | Log Phoenix in tempo reale |

### Sandbox

| Comando | Cosa fa |
|---------|---------|
| `make sandbox-pull` | Pre-pull immagine Docker sandbox |
| `make sandbox-ps` | Lista container sandbox in esecuzione |
| `make sandbox-clean` | Pulizia container sandbox orfani |
| `make test-sandbox` | Test di integrazione sandbox |

### Tutto insieme

| Comando | Cosa fa |
|---------|---------|
| `make test-modules` | Esegue in sequenza: test DB, health proxy, test provider LLM, test agenti, test app, test Phoenix, test Fuseki, test RDF. Panoramica completa dello stato del sistema |

---

## Kubernetes

Comandi per deployare e gestire il sistema su un cluster Kubernetes. Richiedono `kubectl` configurato.

### Deploy

| Comando | Cosa fa |
|---------|---------|
| `make k8s-namespace` | Crea il namespace `agent-setup` |
| `make k8s-configmap` | Applica il ConfigMap con gli URL interni dei servizi |
| `make k8s-proxy-config` | Carica `proxy_config.yml` come ConfigMap nel cluster |
| `make k8s-secrets` | Applica i secrets dal file `deploy/kubernetes/secrets.yml` |
| `make k8s-infra` | Deploya l'infrastruttura: LiteLLM + Qdrant + PostgreSQL (crea namespace, configmap e proxy-config automaticamente) |
| `make k8s-app` | Deploya l'app (crea namespace e configmap automaticamente) |
| `make k8s-deploy` | Deploy completo in ordine: infra poi app. Per chi gestisce i secrets via CLI |
| `make k8s-apply-all` | Applica tutto con Kustomize in un colpo solo (richiede secrets nel file YAML) |

### Monitoraggio

| Comando | Cosa fa |
|---------|---------|
| `make k8s-status` | Mostra lo stato dei pod nel namespace |
| `make k8s-status-all` | Mostra tutte le risorse Kubernetes nel namespace |
| `make k8s-logs-app` | Log in tempo reale dell'app |
| `make k8s-logs-proxy` | Log in tempo reale del proxy LLM |

### Accesso e Debug

| Comando | Cosa fa |
|---------|---------|
| `make k8s-port-forward-app` | Apre un tunnel: `localhost:8000` -> app nel cluster |
| `make k8s-port-forward-proxy` | Apre un tunnel: `localhost:4000` -> proxy nel cluster |
| `make k8s-debug` | Avvia un pod temporaneo con `curl` per testare la connettivita interna al cluster |

### Gestione

| Comando | Cosa fa | Parametri |
|---------|---------|-----------|
| `make k8s-scale replicas=3` | Scala il deployment dell'app al numero di repliche specificato | `replicas` (obbligatorio) |
| `make k8s-destroy` | **Elimina l'intero namespace** e tutte le risorse al suo interno | - |

---

## Docker Image (per push a registry)

Comandi per buildare, taggare e pushare l'immagine Docker a un container registry (Docker Hub, ECR, GCR, ACR).

| Comando | Cosa fa | Parametri |
|---------|---------|-----------|
| `make docker-build` | Builda l'immagine `agent-setup:latest` dal Dockerfile | - |
| `make docker-tag registry=user/agent-setup` | Tagga l'immagine per un registry remoto | `registry` (obbligatorio): path completo del registry |
| `make docker-push registry=user/agent-setup` | Pusha l'immagine al registry | `registry` (obbligatorio) |
| `make docker-release registry=user/agent-setup` | Build + tag + push in un solo comando | `registry` (obbligatorio) |

Esempi di registry:
```bash
# Docker Hub
make docker-release registry=tuousername/agent-setup

# AWS ECR
make docker-release registry=123456789.dkr.ecr.eu-west-1.amazonaws.com/agent-setup

# Google GCR
make docker-release registry=gcr.io/mio-progetto/agent-setup

# Azure ACR
make docker-release registry=mioregistry.azurecr.io/agent-setup
```

---

## Riepilogo rapido per scenario

### Sviluppo locale (ecosistema completo)
```bash
make build              # Avvia tutto (LLM + Qdrant + PostgreSQL + Phoenix + Neo4j + Fuseki)
make llm-proxy-health   # Verifica proxy
make test               # Esegui pytest
make down               # Ferma tutto
```

### Sviluppo locale (solo moduli necessari)
```bash
make llm-up                          # Solo LLM proxy (obbligatorio)
make modules-up m="llm vectordb"     # LLM + Qdrant
make modules-up m="llm graphdb database"  # LLM + Neo4j + PostgreSQL (per Cognee)
make help-modules                    # Guida completa moduli
```

### Produzione on-prem (tutto in Docker)
```bash
make prod-build         # Builda e avvia tutto
make test-modules       # Testa ogni componente
make prod-logs          # Vedi i log
make prod-down          # Ferma tutto
```

### Kubernetes
```bash
make docker-release registry=...   # Pusha immagine
make k8s-deploy                    # Deploya infra + app
make k8s-status                    # Verifica pod
make k8s-port-forward-app          # Accedi all'app
make k8s-destroy                   # Rimuovi tutto
```
