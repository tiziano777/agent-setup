"""knowledge_agent: Server API.

Wraps compiled LangGraph in FastAPI REST.
Endpoints:
    GET  /health       - Healthcheck
    POST /invoke       - Invokes graph with messages
"""

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

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
    title="knowledge_agent API",
    description="REST API for knowledge_agent - Cognee knowledge graph",
    version="0.1.0",
)


class Message(BaseModel):
    role: str
    content: str


class InvokeRequest(BaseModel):
    messages: list[Message]


class InvokeResponse(BaseModel):
    messages: list[dict]


@app.get("/health")
def health():
    """Healthcheck."""
    return {"status": "ok"}


@app.post("/invoke", response_model=InvokeResponse)
async def invoke(req: InvokeRequest):
    """Invoke knowledge_agent with messages.

    Example:
        curl -X POST http://localhost:8000/invoke \
            -H "Content-Type: application/json" \
            -d '{"messages": [{"role": "user", "content": "add this info to knowledge graph..."}]}'
    """
    try:
        from src.agents.knowledge_agent.agent import graph

        input_messages = [
            {"role": m.role, "content": m.content} for m in req.messages
        ]
        result = await graph.ainvoke({"messages": input_messages})
        output = [{"role": m.type, "content": m.content} for m in result["messages"]]
        return InvokeResponse(messages=output)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
