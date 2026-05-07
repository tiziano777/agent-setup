"""deepconf_agent: Server API.

Wraps compiled LangGraph in FastAPI REST.
Endpoints:
    GET  /health       - Healthcheck
    POST /invoke       - Invokes graph with question
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
    title="deepconf_agent API",
    description="REST API for deepconf_agent - Deep reasoning via DeepThinkLLM",
    version="0.1.0",
)


class Message(BaseModel):
    role: str
    content: str


class InvokeRequest(BaseModel):
    messages: list[Message]


class InvokeResponse(BaseModel):
    messages: list[dict]
    final_answer: str | None = None
    reasoning_output: dict | None = None


@app.get("/health")
def health():
    """Healthcheck."""
    return {"status": "ok"}


@app.post("/invoke", response_model=InvokeResponse)
async def invoke(req: InvokeRequest):
    """Invoke deepconf_agent with question.

    Example:
        curl -X POST http://localhost:8000/invoke \
            -H "Content-Type: application/json" \
            -d '{"messages": [{"role": "user", "content": "What is quantum computing?"}]}'
    """
    try:
        from src.agents.deepconf_agent.agent import graph

        # Extract question from last user message
        question = ""
        for msg in reversed(req.messages):
            if msg.role == "user":
                question = msg.content
                break

        state = {
            "question": question,
            "final_answer": None,
            "reasoning_output": {},
            "messages": [],
        }
        result = await graph.ainvoke(state)

        output_messages = [
            {"role": m.type, "content": m.content} for m in result.get("messages", [])
        ]
        return InvokeResponse(
            messages=output_messages,
            final_answer=result.get("final_answer"),
            reasoning_output=result.get("reasoning_output"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
