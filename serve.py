"""Server API minimale per esporre i grafi LangGraph.

Questo file e' infrastruttura di deployment, NON codice applicativo.
Wrappa i grafi compilati in un'API REST via FastAPI.

Endpoints:
    GET  /health              - Healthcheck (usato da Docker/K8s)
    POST /invoke              - Invoca il grafo con una lista di messaggi
"""

import logging
import os
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

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
    description="REST API per grafi LangGraph (code_runner)",
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


# ---------- Endpoints ----------


@app.get("/health")
def health():
    """Healthcheck. Ritorna 200 se il server e' attivo."""
    return {"status": "ok"}


@app.post("/code_runner", response_model=InvokeResponse)
async def invoke(req: InvokeRequest):
    """Invoca il grafo code_runner con i messaggi forniti.

    Esempio:
        curl -X POST http://localhost:8000/code_runner \
            -H "Content-Type: application/json" \
            -d '{"messages": [{"role": "user", "content": "code hello world in python"}]}'
    """
    try:
        from src.agents.code_runner.agent import graph
        input_messages = [{"role": m.role, "content": m.content} for m in req.messages]
        result = await graph.ainvoke({"messages": input_messages})  # noqa: F821
        output = [{"role": m.type, "content": m.content} for m in result["messages"]]
        return InvokeResponse(messages=output)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# add other endpoints when are ready to be exposed
# include also a call example in the docstring for each endpoint, to make it easier to test with curl 

