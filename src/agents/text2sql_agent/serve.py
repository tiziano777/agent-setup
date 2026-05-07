"""text2sql_agent: Server API.

Wraps compiled LangGraph in FastAPI REST.
Endpoints:
    GET  /health       - Healthcheck
    POST /invoke       - Invokes graph with NL query
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
    title="text2sql_agent API",
    description="REST API for text2sql_agent - NL to SQL converter",
    version="0.1.0",
)


class Message(BaseModel):
    role: str
    content: str


class InvokeRequest(BaseModel):
    messages: list[Message]


class InvokeResponse(BaseModel):
    messages: list[dict]
    generated_query: str | None = None
    final_query: str | None = None
    query_result: dict | None = None


@app.get("/health")
def health():
    """Healthcheck."""
    return {"status": "ok"}


@app.post("/invoke", response_model=InvokeResponse)
async def invoke(req: InvokeRequest):
    """Invoke text2sql_agent with NL query.

    Example:
        curl -X POST http://localhost:8000/invoke \
            -H "Content-Type: application/json" \
            -d '{"messages": [{"role": "user", "content": "How many orders in Q1?"}]}'
    """
    try:
        from src.agents.text2sql_agent.agent import graph

        input_messages = [
            {"role": m.role, "content": m.content} for m in req.messages
        ]
        state = {
            "messages": input_messages,
            "status": "pending",
            "generated_query": None,
            "final_query": None,
            "query_result": None,
        }
        result = await graph.ainvoke(state)

        output_messages = [
            {"role": m.type, "content": m.content} for m in result.get("messages", [])
        ]
        return InvokeResponse(
            messages=output_messages,
            generated_query=result.get("generated_query"),
            final_query=result.get("final_query"),
            query_result=result.get("query_result"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
