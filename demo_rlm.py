"""RLM Agent Demo - Full Text Search Example with Phoenix Tracing.

This demo shows:
1. RLM integration with LiteLLM proxy
2. Single-node LangGraph pipeline for text search
3. Full Phoenix OTEL observability
4. Message chain tracking and execution metrics
"""

import asyncio
import random
import string
from datetime import datetime

from src.agents.rlm_agent import get_agent
from src.agents.rlm_agent.states import RLMAgentState
from src.shared.tracing import setup_tracing


def generate_test_context(num_lines: int = 5000) -> tuple[str, str, int]:
    """Generate long text with hidden value.

    Returns:
        (context, secret_value, insertion_line)
    """
    secret = f"MAGIC_{random.randint(100, 999)}_FOUND"

    # Create filler lines
    lines = [
        "".join(random.choices(string.ascii_lowercase + " ", k=100))
        for _ in range(num_lines)
    ]

    # Insert secret at random position in middle third
    insert_pos = random.randint(len(lines) // 3, 2 * len(lines) // 3)
    lines.insert(insert_pos, f">>> HIDDEN VALUE: {secret} <<<")

    return "\n".join(lines), secret, insert_pos


async def demo_rlm_agent():
    """Run RLM Agent demo with full Phoenix tracing."""

    print("\n" + "=" * 80)
    print("🚀 RLM (Recursive Language Models) Agent Demo")
    print("=" * 80)

    # Enable Phoenix OTEL tracing
    print("\n[1] Initializing Phoenix OTEL Tracing...")
    setup_tracing()
    print("✓ Phoenix tracing enabled")

    # Generate test data
    print("\n[2] Generating Test Context...")
    context, secret, insert_line = generate_test_context(5000)
    print(f"✓ Generated context: {len(context):,} chars, {len(context.splitlines())} lines")
    print(f"  - Hidden secret: {secret}")
    print(f"  - Located at line: {insert_line}")

    # Create agent
    print("\n[3] Creating RLM Agent Graph...")
    agent = get_agent()
    print("✓ Agent graph compiled")

    # Prepare state
    print("\n[4] Preparing Agent State...")
    initial_state: RLMAgentState = {
        "prompt": "Find and return the HIDDEN VALUE in the text.",
        "context": context,
        "rlm_response": None,
        "rlm_metadata": None,
        "rlm_status": "pending",
        "messages": [],
    }

    # Execute agent
    print("\n[5] Executing RLM Agent...")
    start_time = datetime.now()
    result = await agent.ainvoke(initial_state)
    elapsed = (datetime.now() - start_time).total_seconds()

    print(f"✓ Execution completed in {elapsed:.2f}s")

    # Display results
    print("\n[6] Results:")
    print(f"  Status: {result['rlm_status']}")
    print(f"  Response: {result['rlm_response']}")

    # Show message chain
    print("\n[7] Message Chain:")
    messages = result.get("messages", [])
    print(f"  Total messages: {len(messages)}")
    for i, msg in enumerate(messages, 1):
        print(f"    [{i}] {msg.__class__.__name__}")

    print("\n" + "=" * 80)
    print(f"✅ Demo completed successfully!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(demo_rlm_agent())
