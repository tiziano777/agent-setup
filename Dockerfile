# ============================================
# Dockerfile per agent-setup
# ============================================
# Builda un'immagine con l'app Python + tutte le dipendenze.
# Espone il grafo LangGraph come API REST via FastAPI.
#
# Build:  docker build -t agent-setup .
# Run:    docker run -p 8000:8000 --env-file .env.docker agent-setup
# ============================================

FROM python:3.11-slim AS base

# Impedisce a Python di bufferizzare stdout/stderr (utile per i log Docker)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dipendenze di sistema: curl per healthcheck, build-essential per compilare
# eventuali pacchetti C (psycopg, sentence-transformers, ecc.)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# ---------- Dipendenze Python ----------
# Copiamo prima solo pyproject.toml per sfruttare la cache dei layer Docker.
# Se il codice sorgente cambia ma le dipendenze no, questo layer non viene ricostruito.
COPY pyproject.toml .

# Installa il progetto con TUTTE le optional dependencies
# + fastapi/uvicorn per il server API (non sono in pyproject.toml)
RUN pip install --no-cache-dir -e ".[retrieval-all,postgres,dev]" && \
    pip install --no-cache-dir fastapi uvicorn

# ---------- Codice sorgente ----------
COPY src/ src/
COPY serve.py .
COPY langgraph.json .
COPY proxy_config.yml .

# ---------- Porta e healthcheck ----------
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ---------- Entry point ----------
# uvicorn serve:app  =  importa 'app' dal file serve.py
CMD ["uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8000"]
