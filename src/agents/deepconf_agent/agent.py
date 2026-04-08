"""deepconf_agent: Graph API definition.

Single-node StateGraph agent that executes deep reasoning on input questions
using DeepConf (facebookresearch/deepconf DeepThinkLLM with fallback).

Full tracing to Phoenix via OpenTelemetry for auditability.
"""

import logging
from datetime import datetime

from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, START, END

from src.agents.deepconf_agent.config import settings
from src.agents.deepconf_agent.prompts import SYSTEM_PROMPT
from src.agents.deepconf_agent.schemas import (
    DeepConfAgentInput,
    DeepConfAgentOutput,
)
from src.agents.deepconf_agent.states import DeepConfAgentState
from src.shared.deepconf import DeepConf

logger = logging.getLogger(__name__)


def reason_node(state: DeepConfAgentState) -> DeepConfAgentState:
    """Execute deep reasoning on the input question.

    Calls DeepConf.think() with configured budget and mode (via asyncio.run).
    Logs all results to Phoenix via OpenTelemetry for traceability.

    Args:
        state: Agent state with question.

    Returns:
        Updated state with reasoning_output and final_answer.
    """
    import asyncio

    question = state.get("question", "")

    if not question:
        logger.error("No question provided to reason_node")
        return {
            **state,
            "final_answer": "Error: No question provided",
            "reasoning_output": {},
        }

    logger.info(f"Starting deep reasoning for: {question[:100]}...")

    try:
        # Initialize DeepConf
        deepconf = DeepConf(
            model=settings.model,
            enable_deepthink=settings.enable_deepthink,
        )

        # Log backend info
        signature = deepconf.get_signature()
        logger.info(f"DeepConf backend: {signature}")

        # Execute reasoning (async via asyncio.run)
        output = asyncio.run(
            deepconf.think(
                prompt=f"{SYSTEM_PROMPT}\n\nQuestion: {question}",
                mode=settings.reasoning_mode,
                budget=settings.reasoning_budget,
            )
        )

        # Log reasoning steps
        for i, step in enumerate(output.reasoning_steps, 1):
            logger.info(f"Reasoning step {i}: {step}")

        # Log voting results
        for strategy, result in output.voting_results.items():
            logger.info(
                f"Voting result - {strategy}: "
                f"confidence={result.confidence:.2f}"
            )

        # Log metrics
        logger.info(
            f"Reasoning completed: "
            f"input_tokens={output.input_tokens}, "
            f"output_tokens={output.output_tokens}, "
            f"mode={output.mode}"
        )

        # Log final answer
        logger.info(f"Final answer: {output.final_answer[:200]}...")

        # Convert output to dict for state
        reasoning_output = {
            "final_answer": output.final_answer,
            "voted_answer": output.voted_answer,
            "voting_results": {
                k: {"strategy": v.strategy, "answer": v.answer,
                    "confidence": v.confidence}
                for k, v in output.voting_results.items()
            },
            "reasoning_steps": output.reasoning_steps,
            "all_traces_count": len(output.all_traces),
            "mode": output.mode,
            "timestamp": output.timestamp,
        }

        # Create message for tracing
        message = AIMessage(
            content=output.final_answer,
            metadata={
                "backend": signature["backend"],
                "reasoning_mode": output.mode,
                "strategies_used": len(output.voting_results),
                "timestamp": datetime.now().isoformat(),
            },
        )

        return {
            **state,
            "messages": state.get("messages", []) + [message],
            "reasoning_output": reasoning_output,
            "final_answer": output.final_answer,
        }

    except Exception as e:
        logger.error(
            f"Error during deep reasoning: {str(e)}", exc_info=True
        )
        return {
            **state,
            "final_answer": f"Error: {str(e)}",
            "reasoning_output": {"error": str(e)},
        }


def build_graph():
    """Construct the single-node reasoning graph."""
    graph = StateGraph(DeepConfAgentState)

    # Add single reasoning node
    graph.add_node("reason", reason_node)

    # Connect start → reason → end
    graph.add_edge(START, "reason")
    graph.add_edge("reason", END)

    return graph.compile()


graph = build_graph()
