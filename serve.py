"""Server API minimale per esporre i grafi LangGraph.

Questo file e' infrastruttura di deployment, NON codice applicativo.
Wrappa i grafi compilati in un'API REST via FastAPI.

Endpoints:
    GET  /health              - Healthcheck (usato da Docker/K8s)
    POST /invoke              - Invoca il grafo con una lista di messaggi
    POST /rdf-extract         - Invoca la pipeline RDF extraction
    POST /rdf-extract/seed    - Seed Oxigraph CWO + Qdrant few-shots
"""

import logging
import os
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# from src.agents.code_runner.agent import graph
from src.shared.env_validation import print_validation_report, validate_env
from src.shared.tracing import setup_tracing

logger = logging.getLogger(__name__)

_env_result = validate_env()
print_validation_report(_env_result)
if _env_result["errors"]:
    import sys

    sys.exit(1)

setup_tracing()

app = FastAPI(
    title="Agent Setup API",
    description="REST API per grafi LangGraph (code_runner + rdf_extractor)",
    version="0.2.0",
)


# ---------- Schemas ----------


class Message(BaseModel):
    role: str  # "user", "assistant", "system"
    content: str


class InvokeRequest(BaseModel):
    messages: list[Message]


class InvokeResponse(BaseModel):
    messages: list[dict]


class RDFExtractRequest(BaseModel):
    text: str = Field(..., description="Natural language text to extract RDF from")
    load_context: bool = Field(
        False, description="If true, enrich ontology context from Oxigraph CWO graph"
    )
    thread_id: str | None = Field(None, description="Thread ID for persistence")


class RDFExtractResponse(BaseModel):
    triples_count: int
    triples: list[str]
    committed_chunks: list[int]
    failed_chunks: list[int]
    audit_trail: dict


# ---------- Endpoints ----------


@app.get("/health")
def health():
    """Healthcheck. Ritorna 200 se il server e' attivo."""
    return {"status": "ok"}


@app.post("/invoke", response_model=InvokeResponse)
async def invoke(req: InvokeRequest):
    """Invoca il grafo agent1 con i messaggi forniti.

    Esempio:
        curl -X POST http://localhost:8000/invoke \
            -H "Content-Type: application/json" \
            -d '{"messages": [{"role": "user", "content": "ciao"}]}'
    """
    try:
        input_messages = [{"role": m.role, "content": m.content} for m in req.messages]
        result = await graph.ainvoke({"messages": input_messages})  # noqa: F821
        output = [{"role": m.type, "content": m.content} for m in result["messages"]]
        return InvokeResponse(messages=output)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rdf-extract", response_model=RDFExtractResponse)
async def rdf_extract(req: RDFExtractRequest):
    """Esegui la pipeline RDF extraction su testo libero.

    Esempio semplice (singolo chunk, niente worker multipli):
        curl -X POST http://localhost:8000/rdf-extract \\
            -H "Content-Type: application/json" \\
            -d '{"text": "Marco Rossi è il CEO di Acme S.r.l.", "load_context": true}'
    """
    try:
        from src.agents.rdf_extractor.config_loader import load_config
        from src.agents.rdf_extractor.graph import build_graph

        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "src", "agents", "rdf_extractor", "config.yaml",
        )
        config = load_config(config_path)

        shacl_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "src", "agents", "rdf_extractor", "shacl", "shapes.ttl",
        )
        if not os.path.isfile(shacl_path):
            shacl_path = ""

        thread_id = req.thread_id or str(uuid.uuid4())

        initial_state = {
            "config": config,
            "input_text": req.text,
            "shacl_shapes_path": shacl_path,
            "ontology_context": "",
            "system_prompt": "",
            "chunk_manifest": [],
            "audit_trail": {},
            "final_triples_buffer": [],
            "committed_chunk_ids": [],
            "load_context": req.load_context,
        }

        graph_rdf = build_graph()
        result = await graph_rdf.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": thread_id}},
        )

        triples = result.get("final_triples_buffer", [])
        committed = result.get("committed_chunk_ids", [])
        manifest = result.get("chunk_manifest", [])
        failed = [t["chunk_id"] for t in manifest if t.get("status") == "failed"]
        audit = result.get("audit_trail", {})

        return RDFExtractResponse(
            triples_count=len(triples),
            triples=triples,
            committed_chunks=committed,
            failed_chunks=failed,
            audit_trail=audit,
        )

    except Exception as e:
        logger.exception("RDF extraction failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rdf-extract/seed")
async def rdf_seed():
    """Seed Oxigraph CWO context + Qdrant few-shot examples.

    Chiamare una volta prima di usare /rdf-extract con load_context=true.

    Esempio:
        curl -X POST http://localhost:8000/rdf-extract/seed
    """
    try:
        from src.agents.rdf_extractor.seed import seed_oxigraph_cwo, seed_qdrant_few_shots

        results = {}

        try:
            seed_oxigraph_cwo()
            results["oxigraph_cwo"] = "ok"
        except Exception as e:
            results["oxigraph_cwo"] = f"error: {e}"

        try:
            seed_qdrant_few_shots()
            results["qdrant_few_shots"] = "ok"
        except Exception as e:
            results["qdrant_few_shots"] = f"error: {e}"

        return {"status": "done", "results": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
