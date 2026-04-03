# Configurazione
PROXY_URL=http://localhost:4000/v1/chat/completions
CONFIG_FILE=proxy_config.yml

# Estrae tutti gli ID definiti sotto model_info.id nel config.yaml
# Rimuove i duplicati (se presenti) per evitare test ripetuti
MODELS := $(shell grep "id:" $(CONFIG_FILE) | sed 's/.*id:[[:space:]]*//' | tr -d '"' | tr -d "'")

# ==========================================
# Infrastruttura Modulare (docker-parts/)
# ==========================================
# Ogni modulo e un docker-compose autocontenuto.
# Per l'ecosistema completo: make build / make down
# Per singoli moduli: make <modulo>-up / make <modulo>-down
# Per la guida completa: make help-modules

PARTS_DIR      = docker-parts
COMPOSE_MOD    = docker compose --project-directory . -p agent-setup

# Flag compose per ogni modulo
MOD_LLM           = -f $(PARTS_DIR)/llm.yml
MOD_VECTORDB      = -f $(PARTS_DIR)/vectordb.yml
MOD_DATABASE      = -f $(PARTS_DIR)/database.yml
MOD_OBSERVABILITY = -f $(PARTS_DIR)/observability.yml
MOD_GRAPHDB       = -f $(PARTS_DIR)/graphdb.yml
MOD_RDF           = -f $(PARTS_DIR)/rdf.yml
MOD_ALL           = $(MOD_LLM) $(MOD_VECTORDB) $(MOD_DATABASE) $(MOD_OBSERVABILITY) $(MOD_GRAPHDB) $(MOD_RDF)

# Dipendenze (auto-incluse dal Makefile)
DEPS_OBSERVABILITY = $(MOD_DATABASE)


# ==========================================
# Ecosistema Completo (root docker-compose)
# ==========================================

# Avvia tutta l'infrastruttura dev (tutti i servizi)
build:
	docker compose up -d --build

# Ferma tutta l'infrastruttura dev
down:
	docker compose down

# Log in tempo reale del proxy LLM (root compose)
llm-proxy-logs:
	docker compose logs -f litellm-proxy

# Controlla lo stato di salute del proxy
llm-proxy-health:
	@curl -sf http://localhost:4000/health | python3 -m json.tool || echo "Proxy non raggiungibile"

# Riavvia il proxy (utile dopo modifica config)
llm-proxy-restart:
	docker compose restart litellm-proxy

# ==========================================
# Singoli Moduli (docker-parts/)
# ==========================================
# LLM e il gateway obbligatorio per tutti i workflow agentici.
# I target individuali avviano SOLO il servizio richiesto.
# Per aggregare piu moduli: make modules-up m="llm vectordb rdf"

# --- LLM Proxy (litellm-proxy) ---
llm-up:
	$(COMPOSE_MOD) $(MOD_LLM) up -d
llm-down:
	$(COMPOSE_MOD) $(MOD_LLM) down
llm-logs:
	$(COMPOSE_MOD) $(MOD_LLM) logs -f

# --- Vector Database (Qdrant) ---
vectordb-up:
	$(COMPOSE_MOD) $(MOD_VECTORDB) up -d
vectordb-down:
	$(COMPOSE_MOD) $(MOD_VECTORDB) down
vectordb-logs:
	$(COMPOSE_MOD) $(MOD_VECTORDB) logs -f

# --- Database (PostgreSQL + pgvector) ---
database-up:
	$(COMPOSE_MOD) $(MOD_DATABASE) up -d
database-down:
	$(COMPOSE_MOD) $(MOD_DATABASE) down
database-logs:
	$(COMPOSE_MOD) $(MOD_DATABASE) logs -f

# --- Observability (Phoenix) — auto-include database ---
observability-up:
	$(COMPOSE_MOD) $(DEPS_OBSERVABILITY) $(MOD_OBSERVABILITY) up -d
observability-down:
	$(COMPOSE_MOD) $(DEPS_OBSERVABILITY) $(MOD_OBSERVABILITY) down
observability-logs:
	$(COMPOSE_MOD) $(DEPS_OBSERVABILITY) $(MOD_OBSERVABILITY) logs -f phoenix

# --- Graph Database (Neo4j) ---
graphdb-up:
	$(COMPOSE_MOD) $(MOD_GRAPHDB) up -d
graphdb-down:
	$(COMPOSE_MOD) $(MOD_GRAPHDB) down
graphdb-logs:
	$(COMPOSE_MOD) $(MOD_GRAPHDB) logs -f

# --- Multi-modulo (composizione libera) ---
# Usage: make modules-up m="llm vectordb database"
modules-up:
ifndef m
	$(error Usage: make modules-up m="llm vectordb database observability graphdb rdf")
endif
	$(COMPOSE_MOD) $(foreach mod,$(m),-f $(PARTS_DIR)/$(mod).yml) up -d

modules-down:
ifndef m
	$(error Usage: make modules-down m="llm vectordb database observability graphdb rdf")
endif
	$(COMPOSE_MOD) $(foreach mod,$(m),-f $(PARTS_DIR)/$(mod).yml) down

modules-ps:
ifndef m
	$(error Usage: make modules-ps m="llm vectordb database observability graphdb rdf")
endif
	$(COMPOSE_MOD) $(foreach mod,$(m),-f $(PARTS_DIR)/$(mod).yml) ps

# --- Tutti i moduli ---
up-all:
	$(COMPOSE_MOD) $(MOD_ALL) up -d

down-all:
	$(COMPOSE_MOD) $(MOD_ALL) down

ps-all:
	$(COMPOSE_MOD) $(MOD_ALL) ps

# --- Guida moduli ---
help-modules:
	@echo "=== Infrastruttura Modulare (docker-parts/) ==="
	@echo ""
	@echo "Moduli disponibili:"
	@echo "  llm            LiteLLM proxy - gateway LLM (prerequisito per tutti i workflow)"
	@echo "  vectordb       Qdrant vector database"
	@echo "  database       PostgreSQL + pgvector"
	@echo "  observability  Arize Phoenix tracing (richiede: database)"
	@echo "  graphdb        Neo4j graph database"
	@echo ""
	@echo "Comandi per singolo modulo:"
	@echo "  make <modulo>-up      Avvia un modulo"
	@echo "  make <modulo>-down    Ferma un modulo"
	@echo "  make <modulo>-logs    Log in tempo reale"
	@echo ""
	@echo "Comandi multi-modulo:"
	@echo "  make modules-up m=\"llm vectordb database\"   Avvia i moduli elencati"
	@echo "  make modules-down m=\"llm vectordb\"           Ferma i moduli elencati"
	@echo "  make modules-ps m=\"llm vectordb\"             Stato dei moduli"
	@echo "  make up-all / down-all / ps-all              Tutti i moduli"
	@echo ""
	@echo "Matrice dipendenze:"
	@echo "  observability -> database  (auto-incluso per observability-up)"
	@echo "  llm           -> prerequisito per tutti i workflow agentici"
	@echo ""
	@echo "Ecosistema completo (root docker-compose, include tutto):"
	@echo "  make build / make down"




define test_provider
	@echo "\n🚀 Testing: $(1)"
	@curl -s -w "\nHTTP Status: %{http_code}\n" -D - $(PROXY_URL) \
		-H "Content-Type: application/json" \
		-d '{"model": "$(1)", "messages": [{"role": "user", "content": "ok"}]}' \
		| grep -iE "x-litellm-model-id|HTTP Status|message|\"content\":" || echo "❌ Errore fatale su $(1)"
	@echo "------------------------------------------"
endef

test-all:
	@echo "--- INIZIO TEST DINAMICO POOL LLM ---"
	@echo "Modelli rilevati: $(MODELS)"
	@for mod in $(MODELS); do \
		$(MAKE) --no-print-directory call-one-provider TARGET_MOD=$$mod; \
	done
	@echo "\n✅ Test completato su tutti i modelli."

# Target interno per la chiamata singola
call-one-provider:
	@echo "\n🚀 Testing: $(TARGET_MOD)"
	@curl -s -w "\nHTTP Status: %{http_code}\n" -D - $(PROXY_URL) \
		-H "Content-Type: application/json" \
		-d "{\"model\": \"$(TARGET_MOD)\", \"messages\": [{\"role\": \"user\", \"content\": \"ok\"}]}" \
		| grep -iE "x-litellm-model-id|HTTP Status|x-litellm-provider|message|\"content\":" || echo "❌ Errore fatale su $(TARGET_MOD)"
	@echo "------------------------------------------"


# test generico del rotator (scelta casuale)
llm-proxy-test:
	@echo "--- Testing Random Provider (Rotator) ---"
	@curl -s -D - $(PROXY_URL) \
		-H "Content-Type: application/json" \
		-d '{"model": "llm", "messages": [{"role": "user", "content": "Rispondi solo: ok"}]}' \
		| grep -iE "x-litellm-model-id|x-litellm-provider|\"content\":"


# ==========================================
# Agent Management
# ==========================================

AGENTS_DIR=src/agents
TEMPLATE_DIR=$(AGENTS_DIR)/_template

# Crea un nuovo agente dal template
# Usage: make new-agent name=my_agent
new-agent:
ifndef name
	$(error Usage: make new-agent name=agent_name)
endif
	@if [ -d "$(AGENTS_DIR)/$(name)" ]; then \
		echo "Error: Agent '$(name)' already exists"; \
		exit 1; \
	fi
	@echo "Creating agent: $(name)"
	@cp -r $(TEMPLATE_DIR) $(AGENTS_DIR)/$(name)
	@find $(AGENTS_DIR)/$(name) -type f -name '*.py' -exec sed -i '' 's/__AGENT_NAME__/$(name)/g' {} +
	@echo "Agent '$(name)' created at $(AGENTS_DIR)/$(name)"
	@echo "Remember to add it to langgraph.json if needed."

# Lista tutti gli agenti (escluso _template)
list-agents:
	@echo "Available agents:"
	@ls -d $(AGENTS_DIR)/*/ 2>/dev/null | grep -v _template | grep -v __pycache__ | xargs -I{} basename {} | sed 's/^/  - /'

# ==========================================
# Development
# ==========================================

# Installa il progetto in modalita development
install:
	pip install -e ".[dev]"

# Esegui tutti i test
test:
	python -m pytest src/ -v

# Test per un singolo agente
# Usage: make test-agent name=agent1
test-agent:
ifndef name
	$(error Usage: make test-agent name=agent_name)
endif
	python -m pytest src/agents/$(name)/tests/ -v

# Lint con ruff
lint:
	ruff check src/
	ruff format --check src/

# Auto-format
fmt:
	ruff format src/
	ruff check --fix src/

# Validazione variabili d'ambiente
env-check:
	python -m src.shared.env_validation

# ==========================================
# Rebuild (solo infrastruttura locale)
# ==========================================

# Ricostruisce le immagini senza avviare i container
rebuild:
	docker compose build

# Ricostruisce e riavvia tutto (infrastruttura locale)
rebuild-up:
	docker compose up -d --build

# ==========================================
# Produzione - Docker Compose (On-Prem)
# ==========================================

PROD_COMPOSE=docker compose -f docker-compose.prod.yml

# Builda e avvia lo stack completo in produzione (app + infra)
prod-build:
	$(PROD_COMPOSE) up --build -d

# Avvia lo stack produzione (senza rebuild)
prod-up:
	$(PROD_COMPOSE) up -d

# Ferma lo stack produzione
prod-down:
	$(PROD_COMPOSE) down

# Ferma e cancella i volumi persistenti (ATTENZIONE: cancella dati Qdrant e PostgreSQL)
prod-down-volumes:
	$(PROD_COMPOSE) down -v

# Ricostruisce solo le immagini di produzione (senza avviare)
prod-rebuild:
	$(PROD_COMPOSE) build

# Ricostruisce e riavvia solo l'app (dopo modifiche al codice)
prod-rebuild-app:
	$(PROD_COMPOSE) up --build -d app

# Riavvia un singolo servizio di produzione
# Usage: make prod-restart service=app
prod-restart:
ifndef service
	$(error Usage: make prod-restart service=<app|litellm-proxy|qdrant|postgres-vector>)
endif
	$(PROD_COMPOSE) restart $(service)

# Log di tutti i servizi produzione
prod-logs:
	$(PROD_COMPOSE) logs -f

# Log solo dell'app
prod-logs-app:
	$(PROD_COMPOSE) logs -f app

# Log solo del proxy LLM in produzione
prod-logs-proxy:
	$(PROD_COMPOSE) logs -f litellm-proxy

# Stato dei container in produzione
prod-ps:
	$(PROD_COMPOSE) ps

# ==========================================
# Test moduli - Produzione (On-Prem)
# ==========================================

# Healthcheck dell'app (serve.py / FastAPI)
test-app-health:
	@echo "--- Test App Health ---"
	@curl -sf http://localhost:8000/health | python3 -m json.tool || echo "App non raggiungibile su :8000"

# Test invocazione dell'app (chiamata completa al grafo)
test-app-invoke:
	@echo "--- Test App Invoke ---"
	@curl -sf -X POST http://localhost:8000/invoke \
		-H "Content-Type: application/json" \
		-d '{"messages": [{"role": "user", "content": "rispondi solo: ok"}]}' \
		| python3 -m json.tool || echo "Errore invocazione app su :8000"

# Test completo dell'app (health + invoke)
test-app: test-app-health test-app-invoke

# Test connettivita Qdrant
test-db-qdrant:
	@echo "--- Test Qdrant ---"
	@curl -sf http://localhost:6333/healthz && echo " Qdrant OK" || echo "Qdrant non raggiungibile su :6333"

# Test connettivita PostgreSQL (pgvector)
test-db-postgres:
	@echo "--- Test PostgreSQL ---"
	@pg_isready -h localhost -p 5433 -U postgres 2>/dev/null && echo " PostgreSQL OK" \
		|| docker compose exec postgres-vector pg_isready -U postgres 2>/dev/null && echo " PostgreSQL OK (via docker)" \
		|| echo "PostgreSQL non raggiungibile su :5433"

# Test di tutti i database
test-db: test-db-qdrant test-db-postgres

# Test singolo agente
# Usage: make test-agent name=agent1
# (gia definito sopra nella sezione Development)

# Test di tutti gli agenti (esclude _template)
test-agents:
	@echo "--- Test tutti gli agenti ---"
	@for agent in $$(ls -d $(AGENTS_DIR)/*/ 2>/dev/null | grep -v _template | grep -v __pycache__); do \
		echo "\nTesting: $$(basename $$agent)"; \
		python -m pytest $$agent/tests/ -v || true; \
	done

# Test completo di tutti i moduli (db + llm + agents + app + phoenix + rdf)
test-modules: test-db llm-proxy-health test-all test-agents test-app test-phoenix
	@echo "\n--- Test di tutti i moduli completato ---"

# ==========================================
# External Documentation & Skills
# ==========================================

EXTERNAL_DIR=external
DOCS_REPO=https://github.com/langchain-ai/docs.git
SKILLS_REPO=https://github.com/langchain-ai/langchain-skills.git

# Clone external docs (sparse: solo src/oss/ e snippets)
external-docs:
	@if [ -d "$(EXTERNAL_DIR)/docs" ]; then \
		echo "external/docs gia presente. Usa 'make external-docs-update' per aggiornare."; \
	else \
		echo "Cloning langchain-ai/docs (sparse checkout, depth 1)..."; \
		mkdir -p $(EXTERNAL_DIR); \
		git clone --depth 1 --filter=blob:none --sparse $(DOCS_REPO) $(EXTERNAL_DIR)/docs; \
		cd $(EXTERNAL_DIR)/docs && git sparse-checkout set src/oss src/snippets/oss; \
		echo "Done. Docs disponibili in $(EXTERNAL_DIR)/docs/"; \
	fi

# Clone external skills
external-skills:
	@if [ -d "$(EXTERNAL_DIR)/langchain-skills" ]; then \
		echo "external/langchain-skills gia presente. Usa 'make external-skills-update' per aggiornare."; \
	else \
		echo "Cloning langchain-ai/langchain-skills (depth 1)..."; \
		mkdir -p $(EXTERNAL_DIR); \
		git clone --depth 1 $(SKILLS_REPO) $(EXTERNAL_DIR)/langchain-skills; \
		echo "Done. Skills disponibili in $(EXTERNAL_DIR)/langchain-skills/"; \
	fi

# Clone entrambi i repos esterni
external-setup: external-docs external-skills
	@echo "Repos esterni pronti."

# Aggiorna external docs
external-docs-update:
	@if [ -d "$(EXTERNAL_DIR)/docs" ]; then \
		echo "Aggiornamento external/docs..."; \
		cd $(EXTERNAL_DIR)/docs && git fetch --depth 1 origin main && git reset --hard origin/main; \
		echo "Done."; \
	else \
		echo "external/docs non trovato. Esegui prima 'make external-docs'."; \
	fi

# Aggiorna external skills
external-skills-update:
	@if [ -d "$(EXTERNAL_DIR)/langchain-skills" ]; then \
		echo "Aggiornamento external/langchain-skills..."; \
		cd $(EXTERNAL_DIR)/langchain-skills && git fetch --depth 1 origin main && git reset --hard origin/main; \
		echo "Done."; \
	else \
		echo "external/langchain-skills non trovato. Esegui prima 'make external-skills'."; \
	fi

# Aggiorna tutti i repos esterni
external-update: external-docs-update external-skills-update
	@echo "Tutti i repos esterni aggiornati."

# Rimuovi repos esterni (re-clone con external-setup)
external-clean:
	@echo "Rimozione repos esterni..."
	rm -rf $(EXTERNAL_DIR)/docs $(EXTERNAL_DIR)/langchain-skills
	@echo "Done. Ri-clona con 'make external-setup'."

# Stato dei repos esterni
external-status:
	@echo "=== Stato Repos Esterni ==="
	@if [ -d "$(EXTERNAL_DIR)/docs/.git" ]; then \
		echo "docs:   $$(cd $(EXTERNAL_DIR)/docs && git log -1 --format='%h %s (%cr)')"; \
	else \
		echo "docs:   NON CLONATO (esegui 'make external-docs')"; \
	fi
	@if [ -d "$(EXTERNAL_DIR)/langchain-skills/.git" ]; then \
		echo "skills: $$(cd $(EXTERNAL_DIR)/langchain-skills && git log -1 --format='%h %s (%cr)')"; \
	else \
		echo "skills: NON CLONATO (esegui 'make external-skills')"; \
	fi

# ==========================================
# Phoenix - LLM Observability
# ==========================================

# Log di Phoenix
phoenix-logs:
	docker compose logs -f phoenix

# Healthcheck Phoenix
test-phoenix:
	@echo "--- Test Phoenix ---"
	@curl -sf http://localhost:6006/healthz && echo " Phoenix OK" || echo "Phoenix non raggiungibile su :6006"

# ==========================================
# Kubernetes
# ==========================================

K8S_DIR=deploy/kubernetes
K8S_NS=agent-setup

# Crea il namespace
k8s-namespace:
	kubectl apply -f $(K8S_DIR)/namespace.yml

# Applica il configmap
k8s-configmap: k8s-namespace
	kubectl apply -f $(K8S_DIR)/configmap.yml

# Carica proxy_config.yml come ConfigMap
k8s-proxy-config: k8s-namespace
	kubectl create configmap proxy-config \
		--from-file=proxy_config.yml=./proxy_config.yml \
		-n $(K8S_NS) --dry-run=client -o yaml | kubectl apply -f -

# Applica i secrets (da file YAML)
k8s-secrets: k8s-namespace
	kubectl apply -f $(K8S_DIR)/secrets.yml

# Applica l'infrastruttura (LiteLLM + Qdrant + PostgreSQL + Phoenix)
k8s-infra: k8s-namespace k8s-configmap k8s-proxy-config
	kubectl apply -f $(K8S_DIR)/infra.yml

# Applica il deployment dell'app
k8s-app: k8s-namespace k8s-configmap
	kubectl apply -f $(K8S_DIR)/app.yml

# Applica tutto con Kustomize (richiede secrets nel file YAML)
k8s-apply-all:
	kubectl apply -k $(K8S_DIR)/

# Applica tutto in ordine (per chi usa secrets via CLI)
k8s-deploy: k8s-infra k8s-app
	@echo "Deploy completato. Controlla con: make k8s-status"

# Stato dei pod
k8s-status:
	kubectl get pods -n $(K8S_NS)

# Stato dettagliato di tutti le risorse
k8s-status-all:
	kubectl get all -n $(K8S_NS)

# Log dell'app
k8s-logs-app:
	kubectl logs -f deployment/agent-app -n $(K8S_NS)

# Log del proxy LLM
k8s-logs-proxy:
	kubectl logs -f deployment/litellm-proxy -n $(K8S_NS)

# Log di Phoenix
k8s-logs-phoenix:
	kubectl logs -f statefulset/phoenix -n $(K8S_NS)

# Port-forward dell'app (accedi su localhost:8000)
k8s-port-forward-app:
	kubectl port-forward svc/agent-app 8000:8000 -n $(K8S_NS)

# Port-forward del proxy LLM (accedi su localhost:4000)
k8s-port-forward-proxy:
	kubectl port-forward svc/litellm-proxy 4000:4000 -n $(K8S_NS)

# Port-forward di Phoenix (accedi su localhost:6006)
k8s-port-forward-phoenix:
	kubectl port-forward svc/phoenix 6006:6006 -n $(K8S_NS)

# Shell di debug per testare connettivita nel cluster
k8s-debug:
	kubectl run debug --rm -it --image=curlimages/curl -n $(K8S_NS) -- sh

# Scala l'app
# Usage: make k8s-scale replicas=3
k8s-scale:
ifndef replicas
	$(error Usage: make k8s-scale replicas=N)
endif
	kubectl scale deployment/agent-app --replicas=$(replicas) -n $(K8S_NS)

# Elimina tutto il namespace (ATTENZIONE: cancella tutto)
k8s-destroy:
	kubectl delete namespace $(K8S_NS)

# ==========================================
# Sandbox - Docker Shell Execution
# ==========================================

# Pre-pull the sandbox image
sandbox-pull:
	docker pull python:3.11-slim

# List running sandbox containers
sandbox-ps:
	@docker ps --filter "label=managed-by=agent-setup-sandbox" --format "table {{.ID}}\t{{.Status}}\t{{.Names}}"

# Clean up orphaned sandbox containers
sandbox-clean:
	@docker ps -aq --filter "label=managed-by=agent-setup-sandbox" | xargs -r docker rm -f 2>/dev/null || true
	@echo "Sandbox containers cleaned."

# Integration tests for sandbox (requires Docker)
test-sandbox:
	python -m pytest src/shared/sandbox/tests/ -v

# ==========================================
# Docker Image (per push a registry)
# ==========================================

IMAGE_NAME=agent-setup
IMAGE_TAG=latest

# Builda l'immagine Docker
docker-build:
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .

# Tagga per un registry remoto
# Usage: make docker-tag registry=tuousername/agent-setup
docker-tag:
ifndef registry
	$(error Usage: make docker-tag registry=<registry/image>)
endif
	docker tag $(IMAGE_NAME):$(IMAGE_TAG) $(registry):$(IMAGE_TAG)

# Pusha l'immagine taggata
# Usage: make docker-push registry=tuousername/agent-setup
docker-push:
ifndef registry
	$(error Usage: make docker-push registry=<registry/image>)
endif
	docker push $(registry):$(IMAGE_TAG)

# Build + tag + push in un solo comando
# Usage: make docker-release registry=tuousername/agent-setup
docker-release: docker-build
ifndef registry
	$(error Usage: make docker-release registry=<registry/image>)
endif
	docker tag $(IMAGE_NAME):$(IMAGE_TAG) $(registry):$(IMAGE_TAG)
	docker push $(registry):$(IMAGE_TAG)
