# Guida al Deployment

Questa guida copre tutti gli scenari di deployment del progetto, dal funzionamento locale alla produzione su Kubernetes. Ogni sezione spiega quali file sono coinvolti, cosa configurare, e come verificare che tutto funzioni.

## Panoramica Scenari

| Scenario | File coinvolti | Difficolta | Quando usarlo |
|----------|---------------|------------|---------------|
| [Sviluppo locale](#1-sviluppo-locale) | `docker-compose.yml` + `.env` | Bassa | Sviluppo e test sul tuo Mac/PC |
| [On-prem containerizzato](#2-on-prem-containerizzato-docker-compose) | `Dockerfile` + `docker-compose.prod.yml` + `.env.docker` | Media | Server dedicato, VM, o PC con Docker |
| [Kubernetes](#3-kubernetes-qualsiasi-cloud) | `deploy/kubernetes/*.yml` | Alta | AWS EKS, Google GKE, Azure AKS, K8s on-prem |
| [LangGraph Cloud](#4-langgraph-cloud) | `langgraph.json` | Bassa | Deploy gestito da LangChain |

## Mappa dei file di deployment

```
agent-setup/
  .env.template              # Template env per sviluppo locale
  .env                       # Le tue API key (NON committare)
  .env.docker.template       # Template env per Docker
  .env.docker                # Le tue API key per Docker (NON committare)
  docker-compose.yml         # Solo infrastruttura (sviluppo locale)
  docker-compose.prod.yml    # Full stack containerizzato (produzione)
  Dockerfile                 # Immagine Docker dell'app Python
  serve.py                   # Server API REST (entry point Docker)
  proxy_config.yml           # Configurazione rotazione provider LLM
  langgraph.json             # Entry point per LangGraph Cloud
  deploy/
    kubernetes/
      namespace.yml          # Namespace isolato
      configmap.yml          # Variabili non sensibili
      secrets.yml            # Template per API key
      app.yml                # Deployment + Service dell'app
      infra.yml              # LiteLLM + Qdrant + PostgreSQL
      kustomization.yml      # Aggregatore per kubectl apply
```

---

## 1. Sviluppo Locale

Questo e' lo scenario piu semplice: l'infrastruttura (proxy LLM, database) gira in Docker, ma il tuo codice Python gira direttamente sul tuo Mac/PC nel virtual environment.

### File coinvolti

| File | Ruolo |
|------|-------|
| `.env.template` | Template da copiare |
| `.env` | Le tue API key (compilato da te) |
| `docker-compose.yml` | Avvia proxy LLM + Qdrant + PostgreSQL |
| `proxy_config.yml` | Configurazione dei 12 provider LLM |

### Passo 1: Configura le API key

```bash
cp .env.template .env
```

Apri `.env` con un editor e inserisci le API key. Non servono tutte: il proxy ruota solo tra i provider con chiave valida.

```bash
# Esempio: compila solo Groq e Google
GROQ_API_KEY=gsk_abc123...
GOOGLE_API_KEY=AIza...
```

Le altre variabili gia presenti nel file:

| Variabile | Valore default | Quando modificare |
|-----------|---------------|-------------------|
| `QDRANT_URL` | `http://localhost:6333` | Mai (in locale) |
| `PGVECTOR_URI` | `postgresql://postgres:postgres@localhost:5433/vectors` | Mai (in locale) |
| `OPENAI_API_KEY` | (vuoto) | Solo se usi embeddings OpenAI |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Solo se preferisci un altro modello |

### Passo 2: Avvia l'infrastruttura

```bash
make build
```

Questo esegue `docker compose up -d --build` e avvia tre container:

| Container | Porta | Cosa fa |
|-----------|-------|---------|
| `litellm-proxy` | 4000 | Gateway LLM, riceve le chiamate dal tuo codice |
| `qdrant` | 6333 | Database vettoriale per RAG |
| `postgres-vector` | 5433 | PostgreSQL con estensione pgvector |

### Passo 3: Verifica

```bash
# Il proxy risponde?
make llm-proxy-health

# Prova una chiamata LLM
make llm-proxy-test

# Testa tutti i provider configurati
make test-all
```

### Passo 4: Avvia il codice Python

```bash
# Se non l'hai gia fatto: crea il venv e installa
source .venv/bin/activate
pip install -e ".[dev]"

# Esegui i test
make test
```

### Come funziona il collegamento

Il tuo codice Python chiama `get_llm()` in `src/shared/llm.py`. Questa funzione legge la variabile `LITELLM_BASE_URL` (default: `http://localhost:4000/v1`) e crea un client che punta al proxy Docker. Il proxy riceve la richiesta, sceglie un provider a caso tra quelli configurati, e inoltra la chiamata.

```
Python (sul tuo Mac)
  |
  v  http://localhost:4000/v1
Docker: litellm-proxy
  |
  v  (scelta casuale)
Provider esterno (Groq, Google, Mistral, ...)
```

### Per fermare

```bash
make down
```

---

## 2. On-Prem Containerizzato (Docker Compose)

In questo scenario **tutto** gira in Docker: sia l'infrastruttura che la tua app Python. E' il modo piu semplice per fare deploy su un server (fisico o VM) senza bisogno di Kubernetes.

### File coinvolti

| File | Ruolo |
|------|-------|
| `.env.docker.template` | Template env specifico per Docker |
| `.env.docker` | Le tue API key per Docker (compilato da te) |
| `Dockerfile` | Istruzioni per costruire l'immagine della tua app |
| `docker-compose.prod.yml` | Avvia TUTTO: app + proxy + Qdrant + PostgreSQL |
| `serve.py` | Server API REST che espone il grafo LangGraph |
| `proxy_config.yml` | Configurazione dei provider LLM (uguale al locale) |

### Capire il Dockerfile

Il `Dockerfile` costruisce un'immagine Docker che contiene la tua app Python pronta da eseguire. Ecco cosa fa, layer per layer:

```dockerfile
FROM python:3.11-slim AS base        # Immagine base leggera con Python 3.11
```
Parte da un'immagine ufficiale Python. La variante `slim` e' piu leggera (~150 MB vs ~900 MB della versione completa).

```dockerfile
RUN apt-get update && apt-get install -y curl build-essential
```
Installa due pacchetti di sistema:
- `curl`: serve per l'healthcheck (Docker controlla periodicamente che l'app sia viva)
- `build-essential`: compilatore C, necessario per installare certi pacchetti Python (psycopg, sentence-transformers)

```dockerfile
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[retrieval-all,postgres,dev]" && \
    pip install --no-cache-dir fastapi uvicorn
```
Copia il file delle dipendenze e le installa. Il trucco: copiare `pyproject.toml` **prima** del codice sorgente significa che se cambi solo il codice, Docker riusa le dipendenze dalla cache (build piu veloce).

Le dipendenze installate:
- `retrieval-all`: tutti i moduli RAG (Qdrant, pgvector, embeddings, rerankers)
- `postgres`: checkpoint persistente su PostgreSQL
- `dev`: tool di sviluppo (pytest, ruff, mypy)
- `fastapi` + `uvicorn`: server web per esporre l'API

```dockerfile
COPY src/ src/
COPY serve.py .
```
Copia il codice sorgente nell'immagine.

```dockerfile
CMD ["uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8000"]
```
Quando il container parte, avvia il server API sulla porta 8000.

### Capire serve.py

`serve.py` e' un piccolo server che "wrappa" il tuo grafo LangGraph in un'API REST. Non contiene logica di business, e' pura infrastruttura.

Espone due endpoint:

| Metodo | Path | Cosa fa |
|--------|------|---------|
| GET | `/health` | Ritorna `{"status": "ok"}`. Usato da Docker/K8s per sapere se l'app e' viva |
| POST | `/invoke` | Riceve messaggi, li passa al grafo, ritorna la risposta |

Esempio di chiamata:

```bash
curl -X POST http://localhost:8000/invoke \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "ciao, come stai?"}]}'
```

Risposta:

```json
{
  "messages": [
    {"role": "user", "content": "ciao, come stai?"},
    {"role": "assistant", "content": "Ciao! Sto bene, grazie..."}
  ]
}
```

### Capire docker-compose.prod.yml

Questo file descrive **tutti** i servizi necessari e come si collegano tra loro.

```
docker-compose.prod.yml
  |
  +-- app            (la tua app Python, porta 8000)
  |     |
  |     +-- dipende da: litellm-proxy, qdrant, postgres-vector, phoenix, neo4j, fuseki
  |
  +-- litellm-proxy  (gateway LLM, porta 4000)
  +-- qdrant          (vector DB, porta 6333)
  +-- postgres-vector (PostgreSQL, porta 5433)
  +-- phoenix         (observability, porta 6006)
  +-- neo4j           (graph DB, porta 7474/7687)
  +-- fuseki          (RDF store, porta 3030)
  |
  +-- agent-net       (rete privata tra i container)
  +-- agent-qdrant-data    (volume persistente)
  +-- agent-pgvector-data  (volume persistente)
  +-- agent-neo4j-data     (volume persistente)
  +-- agent-fuseki-data    (volume persistente)
```

Differenze chiave rispetto allo sviluppo locale:

| Aspetto | Locale (`docker-compose.yml`) | Produzione (`docker-compose.prod.yml`) |
|---------|-------------------------------|----------------------------------------|
| App Python | Gira sul tuo PC | Gira in Docker |
| URL LiteLLM | `http://localhost:4000` | `http://litellm-proxy:4000` |
| URL Qdrant | `http://localhost:6333` | `http://qdrant:6333` |
| URL PostgreSQL | `localhost:5433` | `postgres-vector:5432` |
| URL Phoenix | `http://localhost:6006` | `http://phoenix:6006` |
| URL Neo4j | `bolt://localhost:7687` | `bolt://neo4j:7687` |
| URL Fuseki | `http://localhost:3030` | `http://fuseki:3030` |
| Rete | Porte esposte sull'host | Rete Docker interna (`agent-net`) |

In Docker, i container si parlano usando i **nomi dei servizi** come hostname (es. `litellm-proxy`, `qdrant`). La porta e' quella interna del container (es. `5432` per Postgres, non `5433`).

### Passo 1: Configura le API key

```bash
cp .env.docker.template .env.docker
```

Apri `.env.docker` con un editor e inserisci le API key:

```bash
# Apri con il tuo editor preferito
nano .env.docker    # o vim, code, ecc.
```

Compila almeno una API key tra quelle disponibili:

```
GROQ_API_KEY=gsk_abc123...
GOOGLE_API_KEY=AIza...
```

**Non modificare gli URL dei servizi** (LITELLM_BASE_URL, QDRANT_URL, ecc.) -- sono gia configurati correttamente nel `docker-compose.prod.yml` nella sezione `environment` del servizio `app`.

### Passo 2: Builda e avvia

```bash
docker compose -f docker-compose.prod.yml up --build
```

Cosa succede:
1. Docker costruisce l'immagine della tua app dal `Dockerfile`
2. Avvia PostgreSQL e aspetta che sia pronto (healthcheck)
3. Avvia Qdrant e aspetta che sia pronto
4. Avvia il LiteLLM proxy e aspetta che sia pronto
5. Avvia la tua app (che dipende da tutti gli altri)

La prima volta ci vogliono alcuni minuti per scaricare le immagini e installare le dipendenze. Le volte successive sara molto piu veloce grazie alla cache Docker.

Per avviare in background (senza occupare il terminale):

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

### Passo 3: Verifica

```bash
# L'app risponde?
curl http://localhost:8000/health
# Atteso: {"status":"ok"}

# Il proxy LLM risponde?
curl http://localhost:4000/health
# Atteso: {"healthy_deployments":[...]}

# Prova una chiamata completa
curl -X POST http://localhost:8000/invoke \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "rispondi solo: ok"}]}'
```

### Passo 4: Vedi i log

```bash
# Log di tutti i servizi
docker compose -f docker-compose.prod.yml logs -f

# Log solo dell'app
docker compose -f docker-compose.prod.yml logs -f app

# Log solo del proxy
docker compose -f docker-compose.prod.yml logs -f litellm-proxy
```

### Per fermare

```bash
docker compose -f docker-compose.prod.yml down
```

Per fermare **e cancellare i dati persistenti** (Qdrant, PostgreSQL):

```bash
docker compose -f docker-compose.prod.yml down -v
```

### Per rifare il build dopo modifiche al codice

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

Il flag `--build` forza Docker a ricostruire l'immagine dell'app. Grazie alla cache dei layer, se hai solo modificato il codice Python (non le dipendenze) il rebuild e' veloce.

### Configurazioni avanzate

#### Cambiare le credenziali PostgreSQL

Nel file `.env.docker`, decommenta e modifica:

```
POSTGRES_USER=myuser
POSTGRES_PASSWORD=una_password_sicura
POSTGRES_DB=vectors
```

**Attenzione**: se cambi le credenziali, devi aggiornare anche `PGVECTOR_URI` nel `docker-compose.prod.yml`, sezione `environment` del servizio `app`:

```yaml
PGVECTOR_URI: postgresql://myuser:una_password_sicura@postgres-vector:5432/vectors
```

#### Cambiare i limiti di risorse

Nel `docker-compose.prod.yml`, ogni servizio ha una sezione `deploy.resources`:

```yaml
deploy:
  resources:
    limits:
      memory: 2G         # Massimo RAM per il container
    reservations:
      memory: 512M       # RAM minima garantita
```

Valori consigliati per un server con 8 GB di RAM:

| Servizio | RAM consigliata | CPU consigliata |
|----------|----------------|-----------------|
| app | 1-2 GB | 1 core |
| litellm-proxy | 256-512 MB | 0.5 core |
| qdrant | 512 MB - 1 GB | 0.5 core |
| postgres-vector | 256-512 MB | 0.5 core |

#### Non esporre le porte di infrastruttura

In produzione, probabilmente non vuoi che Qdrant e PostgreSQL siano raggiungibili dall'esterno. Commenta le sezioni `ports` dei servizi che non devono essere esposti:

```yaml
# Nel docker-compose.prod.yml
qdrant:
  # ports:                    # <-- Commenta per non esporre
  #   - "6333:6333"
  #   - "6334:6334"
```

L'app continuera a raggiungerli via la rete Docker interna (`agent-net`).

---

## 3. Kubernetes (qualsiasi cloud)

Kubernetes e' un sistema di orchestrazione container che funziona su qualsiasi cloud (AWS EKS, Google GKE, Azure AKS) e anche on-prem. I manifesti YAML nella directory `deploy/kubernetes/` descrivono come deployare tutto il sistema.

### Prerequisiti

- Un cluster Kubernetes funzionante (locale con `minikube`/`kind`, o cloud)
- `kubectl` installato e configurato per parlare con il cluster
- Un container registry per pushare l'immagine (Docker Hub, ECR, GCR, ecc.)

### File coinvolti

Tutti i file sono in `deploy/kubernetes/`:

| File | Cosa contiene | Tipo Kubernetes |
|------|---------------|-----------------|
| `namespace.yml` | Namespace `agent-setup` | Namespace |
| `configmap.yml` | URL dei servizi interni, model name | ConfigMap |
| `secrets.yml` | Template per le API key | Secret |
| `app.yml` | L'app Python + Service + Ingress opzionale | Deployment, Service |
| `infra.yml` | LiteLLM + Qdrant + PostgreSQL | Deployment, StatefulSet, Service, PVC |
| `kustomization.yml` | Aggrega tutto per un unico `kubectl apply` | Kustomization |

### Concetti base di Kubernetes

Se non hai mai usato Kubernetes, ecco i concetti principali usati nei manifesti:

| Concetto | Cosa fa | Analogia Docker Compose |
|----------|---------|-------------------------|
| **Namespace** | Raggruppa risorse isolandole da altri progetti | Non esiste (tutto e' nello stesso scope) |
| **Deployment** | Gestisce N repliche di un container (app stateless) | `services.app` |
| **StatefulSet** | Come Deployment ma per servizi con dati persistenti | `services.postgres-vector` (con volume) |
| **Service** | Dà un nome DNS stabile a un gruppo di pod | Automatico in Compose (nome del servizio) |
| **ConfigMap** | Variabili di configurazione non sensibili | `env_file` o `environment` |
| **Secret** | Variabili sensibili (API key, password) | `.env` file |
| **PersistentVolumeClaim** | Disco persistente che sopravvive ai riavvii | `volumes` in Compose |
| **Ingress** | Espone un servizio su internet con dominio e HTTPS | `ports` con un reverse proxy |

### Capire namespace.yml

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: agent-setup
```

Crea un namespace chiamato `agent-setup`. Tutte le altre risorse verranno create dentro questo namespace, isolate dal resto del cluster.

### Capire configmap.yml

```yaml
data:
  LITELLM_BASE_URL: "http://litellm-proxy:4000/v1"
  QDRANT_URL: "http://qdrant:6333"
  PGVECTOR_URI: "postgresql://postgres:postgres@postgres-vector:5432/vectors"
```

Contiene gli URL interni al cluster. In Kubernetes, come in Docker Compose, i servizi si raggiungono tramite il **nome del Service** (che diventa un hostname DNS). Questi valori sovrascrivono i default `localhost` nel codice Python.

### Capire secrets.yml

Il Secret contiene le API key. I valori devono essere **codificati in base64** (non e' crittografia, e' solo codifica):

```bash
# Per codificare un valore:
echo -n "gsk_abc123..." | base64
# Output: Z3NrX2FiYzEyMy4uLg==

# Per decodificare:
echo "Z3NrX2FiYzEyMy4uLg==" | base64 -d
# Output: gsk_abc123...
```

**Metodo rapido** (senza modificare il file YAML): crea i secrets via CLI:

```bash
kubectl create secret generic llm-api-keys \
  --from-literal=GROQ_API_KEY=gsk_abc123... \
  --from-literal=GOOGLE_API_KEY=AIza... \
  -n agent-setup
```

```bash
kubectl create secret generic postgres-credentials \
  --from-literal=POSTGRES_USER=postgres \
  --from-literal=POSTGRES_PASSWORD=postgres \
  --from-literal=POSTGRES_DB=vectors \
  -n agent-setup
```

### Capire app.yml

Tre risorse in un file:

1. **Deployment**: avvia un pod con la tua app

```yaml
spec:
  replicas: 1                      # Quante copie dell'app
  containers:
    - image: agent-setup:latest    # <-- DA CAMBIARE con il tuo registry
      envFrom:
        - configMapRef:            # Carica variabili dal ConfigMap
            name: agent-config
        - secretRef:               # Carica API key dal Secret
            name: llm-api-keys
      livenessProbe:               # Se fallisce, K8s riavvia il pod
        httpGet: /health
      readinessProbe:              # Se fallisce, K8s non manda traffico
        httpGet: /health
      resources:
        requests:                  # Risorse minime garantite
          cpu: 250m
          memory: 512Mi
        limits:                    # Risorse massime
          cpu: "1"
          memory: 2Gi
```

2. **Service**: rende l'app raggiungibile via DNS `agent-app` dentro il cluster

3. **Ingress** (commentato): per esporre l'app su internet con un dominio

### Capire infra.yml

Contiene i tre servizi di infrastruttura:

- **LiteLLM Proxy**: Deployment + Service (stateless, non serve disco)
- **Qdrant**: StatefulSet + Service + PersistentVolumeClaim (10 GB di disco)
- **PostgreSQL**: StatefulSet + Service + PersistentVolumeClaim (10 GB di disco)

Il proxy ha bisogno del file `proxy_config.yml`. In Kubernetes si carica come ConfigMap:

```bash
kubectl create configmap proxy-config \
  --from-file=proxy_config.yml=./proxy_config.yml \
  -n agent-setup
```

### Passo 1: Builda e pusha l'immagine

```bash
# Builda l'immagine localmente
docker build -t agent-setup .

# Tagga per il tuo registry (esempio con Docker Hub)
docker tag agent-setup:latest tuousername/agent-setup:latest

# Pusha al registry
docker push tuousername/agent-setup:latest
```

Esempi per altri registry:

```bash
# AWS ECR
docker tag agent-setup:latest 123456789.dkr.ecr.eu-west-1.amazonaws.com/agent-setup:latest
docker push 123456789.dkr.ecr.eu-west-1.amazonaws.com/agent-setup:latest

# Google GCR
docker tag agent-setup:latest gcr.io/mio-progetto/agent-setup:latest
docker push gcr.io/mio-progetto/agent-setup:latest

# Azure ACR
docker tag agent-setup:latest mioregistry.azurecr.io/agent-setup:latest
docker push mioregistry.azurecr.io/agent-setup:latest
```

### Passo 2: Aggiorna il riferimento all'immagine

In `deploy/kubernetes/app.yml`, trova questa riga:

```yaml
image: agent-setup:latest
```

Sostituiscila con l'URL completo dell'immagine nel tuo registry:

```yaml
image: tuousername/agent-setup:latest
```

### Passo 3: Configura i secrets

Opzione A -- via CLI (consigliato per iniziare):

```bash
# Crea il namespace prima
kubectl apply -f deploy/kubernetes/namespace.yml

# Crea i secrets dalla CLI
kubectl create secret generic llm-api-keys \
  --from-literal=GROQ_API_KEY=gsk_abc123... \
  --from-literal=GOOGLE_API_KEY=AIza... \
  -n agent-setup

kubectl create secret generic postgres-credentials \
  --from-literal=POSTGRES_USER=postgres \
  --from-literal=POSTGRES_PASSWORD=una_password_sicura \
  --from-literal=POSTGRES_DB=vectors \
  -n agent-setup
```

Opzione B -- modificando `secrets.yml`:

```bash
# Codifica ogni valore
echo -n "gsk_abc123..." | base64
# Incolla il risultato nel file secrets.yml al posto di <BASE64_VALUE>
```

### Passo 4: Carica il proxy config

```bash
kubectl create configmap proxy-config \
  --from-file=proxy_config.yml=./proxy_config.yml \
  -n agent-setup
```

### Passo 5: Applica tutto

Se hai usato l'opzione A (secrets via CLI), applica i manifesti singolarmente nell'ordine:

```bash
kubectl apply -f deploy/kubernetes/namespace.yml
kubectl apply -f deploy/kubernetes/configmap.yml
# (secrets gia creati al Passo 3)
kubectl apply -f deploy/kubernetes/infra.yml
kubectl apply -f deploy/kubernetes/app.yml
```

Se hai usato l'opzione B (secrets nel file YAML), puoi applicare tutto con Kustomize:

```bash
kubectl apply -k deploy/kubernetes/
```

### Passo 6: Verifica

```bash
# Controlla che tutti i pod siano Running
kubectl get pods -n agent-setup
# NAME                              READY   STATUS    RESTARTS
# agent-app-xxxxx                   1/1     Running   0
# litellm-proxy-xxxxx               1/1     Running   0
# qdrant-0                          1/1     Running   0
# postgres-vector-0                 1/1     Running   0

# Log dell'app
kubectl logs -f deployment/agent-app -n agent-setup

# Log del proxy
kubectl logs -f deployment/litellm-proxy -n agent-setup

# Test diretto tramite port-forward (apre un tunnel temporaneo)
kubectl port-forward svc/agent-app 8000:8000 -n agent-setup
# In un altro terminale:
curl http://localhost:8000/health
curl -X POST http://localhost:8000/invoke \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "ciao"}]}'
```

### Esporre l'app su internet (Ingress)

Per rendere l'API accessibile dall'esterno del cluster, decommenta la sezione `Ingress` in `app.yml` e configura:

1. **Installa un Ingress Controller** (se non ne hai uno):

```bash
# nginx-ingress (il piu comune)
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.2/deploy/static/provider/cloud/deploy.yaml
```

2. **Modifica l'Ingress in `app.yml`**:

```yaml
spec:
  rules:
    - host: agent-api.il-tuo-dominio.com    # <-- Il tuo dominio
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: agent-app
                port:
                  number: 8000
```

3. **Configura il DNS** del tuo dominio per puntare all'IP dell'Ingress Controller.

### Scalare l'app

Per avere piu repliche dell'app (gestire piu traffico):

```bash
kubectl scale deployment/agent-app --replicas=3 -n agent-setup
```

Oppure modifica `replicas` in `app.yml`:

```yaml
spec:
  replicas: 3
```

I servizi di infrastruttura (Qdrant, PostgreSQL) non vanno scalati semplicemente aumentando le repliche -- richiedono configurazioni cluster-specific.

---

## 4. LangGraph Cloud

Se usi LangGraph Cloud (piattaforma gestita da LangChain), non hai bisogno di Docker, Kubernetes, o server propri. La piattaforma legge `langgraph.json` e fa tutto da sola.

### File coinvolti

| File | Ruolo |
|------|-------|
| `langgraph.json` | Dichiara il grafo da deployare |
| `.env` | Le API key (caricate sulla piattaforma) |

### Come funziona

```json
{
  "dependencies": [".", "langchain_openai"],
  "graphs": {
    "agent1": "./src/agents/agent1/agent.py:graph"
  },
  "env": "./.env"
}
```

- `dependencies`: pacchetti da installare (`.` = il progetto stesso)
- `graphs`: mappa nome -> entry point del grafo
- `env`: file con le variabili d'ambiente

### Passo 1: Configura le variabili d'ambiente sulla piattaforma

Nella dashboard di LangGraph Cloud, configura le stesse variabili del file `.env`:
- Tutte le API key dei provider LLM
- `LITELLM_BASE_URL` (potrebbe non servire se usi LangGraph Cloud con LLM integrati)

### Passo 2: Deploya

Segui la documentazione ufficiale di LangGraph Cloud per collegare il tuo repository e lanciare il deploy.

### Limitazione

LangGraph Cloud gestisce solo l'app Python, non LiteLLM proxy, Qdrant o PostgreSQL. Se il tuo agente usa la pipeline RAG (vector search), dovrai:
- Usare Qdrant Cloud al posto del container self-hosted
- Configurare `QDRANT_URL` per puntare al cloud
- Oppure usare un'alternativa cloud per il vector store

---

## Troubleshooting

### L'app non parte (Docker Compose)

```bash
# Controlla i log
docker compose -f docker-compose.prod.yml logs app

# Errori comuni:
# "ModuleNotFoundError" -> il Dockerfile non ha copiato/installato tutto
# "Connection refused" su porta 4000 -> il proxy non e' ancora pronto
#                                        (depends_on con healthcheck dovrebbe gestirlo)
```

### Il proxy non trova le API key

```bash
# Verifica che .env.docker sia riferito correttamente
docker compose -f docker-compose.prod.yml exec litellm-proxy env | grep API_KEY
```

Se le variabili sono vuote, controlla che `.env.docker` esista e contenga i valori.

### Pod in CrashLoopBackOff (Kubernetes)

```bash
# Vedi i log del pod
kubectl logs pod/agent-app-xxxxx -n agent-setup

# Vedi gli eventi
kubectl describe pod/agent-app-xxxxx -n agent-setup

# Motivi comuni:
# - Immagine non trovata (ImagePullBackOff) -> controlla il nome dell'immagine e i permessi del registry
# - OOMKilled -> aumenta i limiti di memoria in app.yml
# - Secret non trovato -> crea i secrets prima di applicare app.yml
```

### Come verificare che i servizi si vedano (Docker)

```bash
# Entra nel container dell'app
docker compose -f docker-compose.prod.yml exec app bash

# Dall'interno del container, testa la connettivita
curl http://litellm-proxy:4000/health
curl http://qdrant:6333/healthz
```

### Come verificare che i servizi si vedano (Kubernetes)

```bash
# Avvia un pod temporaneo per il debug
kubectl run debug --rm -it --image=curlimages/curl -n agent-setup -- sh

# Dall'interno del pod
curl http://litellm-proxy:4000/health
curl http://qdrant:6333/healthz
```
