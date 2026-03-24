"""Server API minimale per esporre il grafo LangGraph.

Questo file e' infrastruttura di deployment, NON codice applicativo.
Wrappa il grafo compilato in un'API REST via FastAPI.

Endpoints:
    GET  /health  - Healthcheck (usato da Docker/K8s)
    POST /invoke  - Invoca il grafo con una lista di messaggi
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.agents.agent1.agent import graph
from src.shared.env_validation import print_validation_report, validate_env
from src.shared.tracing import setup_tracing

_env_result = validate_env()
print_validation_report(_env_result)
if _env_result["errors"]:
    import sys

    sys.exit(1)

setup_tracing()

app = FastAPI(
    title="Agent Setup API",
    description="REST API per il grafo LangGraph agent1",
    version="0.1.0",
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
        result = await graph.ainvoke({"messages": input_messages})
        output = [{"role": m.type, "content": m.content} for m in result["messages"]]
        return InvokeResponse(messages=output)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
