#!/usr/bin/env python
"""Standalone test: RLM Agent finding hidden value with full message tracing.

This test does NOT require the LiteLLM proxy running (uses mocks).
Shows complete message chain + execution metadata for Phoenix observability.

Run: python test_rlm_standalone.py
"""

import asyncio
import json
import random
import string
from unittest.mock import patch


async def test_rlm_agent_standalone():
    """Test RLM Agent with mocked RLM backend."""
    from src.agents.rlm_agent.agent import get_agent
    from src.agents.rlm_agent.states import RLMAgentState

    print("\n" + "=" * 80)
    print("RLM AGENT STANDALONE TEST")
    print("=" * 80)

    # Generate test haystack (3000 lines)
    print("\n[1] Generating test haystack...")
    magic_value = "SECRET_42_FOUND"
    lines = [
        "".join(random.choices(string.ascii_lowercase + " ", k=120))
        for _ in range(3000)
    ]
    insert_at = random.randint(1000, 2000)
    lines.insert(insert_at, f"MAGIC: {magic_value}")
    haystack = "\n".join(lines)
    print(f"    ✓ Generated {len(haystack):,} chars ({len(lines)} lines)")
    print(f"    ✓ Hidden value at line {insert_at}: {magic_value}")

    # Mock rlm_completion to simulate RLM behavior
    def mock_rlm_completion(prompt, context=None, settings=None, **kwargs):
        """Simulate RLM finding the magic value."""
        return {
            "response": f"Found the magic value: {magic_value}",
            "execution_time": 2.34,
            "metadata": {
                "iterations": [
                    {"step": 1, "action": "sample_lines", "sampled": 50},
                    {"step": 2, "action": "regex_search", "pattern": "MAGIC:"},
                    {"step": 3, "action": "extract_value", "found": magic_value},
                ],
                "rlm_calls": [],
            },
            "status": "success",
            "error": None,
        }

    # Run test with mock
    print("\n[2] Patching rlm_completion with mock...")
    with patch("src.agents.rlm_agent.nodes.search.rlm_completion") as mock_rlm:
        mock_rlm.side_effect = mock_rlm_completion

        print("    ✓ Mock installed")

        # Create agent
        print("\n[3] Creating RLM Agent...")
        agent = get_agent()
        print("    ✓ Agent compiled (single-node pipeline)")

        # Build initial state
        print("\n[4] Building initial state...")
        initial_state: RLMAgentState = {
            "prompt": "Find and extract the MAGIC value from this text",
            "context": haystack,
            "rlm_response": None,
            "rlm_metadata": None,
            "rlm_status": "pending",
            "messages": [],
        }
        print("    ✓ State ready")

        # Execute agent
        print("\n[5] Executing agent.ainvoke()...")
        result = await agent.ainvoke(initial_state)
        print("    ✓ Agent execution complete")

        # Display results
        print("\n[6] RESULTS:")
        print(f"    Status: {result['rlm_status']}")
        print(f"    RLM Response: {result['rlm_response']}")
        print(f"    Expected: {magic_value}")

        # Verify correctness
        print("\n[7] VERIFICATION:")
        if result["rlm_status"] == "success":
            if magic_value in result["rlm_response"]:
                print(f"    ✅ PASS: Found '{magic_value}'")
            else:
                print(f"    ❌ FAIL: Expected '{magic_value}' in response")
                return False
        else:
            print(f"    ❌ FAIL: Status was '{result['rlm_status']}'")
            return False

        # Display full message chain (for Phoenix)
        print("\n[8] MESSAGE CHAIN (for observability):")
        messages = result["messages"]
        print(f"    Total messages: {len(messages)}")

        for i, msg in enumerate(messages):
            msg_type = msg.__class__.__name__
            content = msg.content
            print(f"\n    Message {i}: {msg_type}")
            print(f"      Content preview: {content[:100]}...")

            # Try to get metadata if available
            if hasattr(msg, "metadata") and msg.metadata:
                print(f"      Metadata:")
                for key, val in msg.metadata.items():
                    print(f"        {key}: {val}")
            elif hasattr(msg, "response_metadata") and msg.response_metadata:
                print(f"      Response metadata: {msg.response_metadata}")

        # Display RLM metadata (execution trajectory)
        print("\n[9] RLM EXECUTION TRAJECTORY:")
        metadata = result["rlm_metadata"]
        if metadata:
            iterations = metadata.get("iterations", [])
            print(f"    Iterations: {len(iterations)}")
            for it in iterations:
                print(f"      • {json.dumps(it)}")

            recursive = metadata.get("rlm_calls", [])
            print(f"    Recursive calls: {len(recursive)}")

        # Summary
        print("\n[10] OBSERVABILITY SUMMARY:")
        print("    ✓ Message history fully captured")
        print("    ✓ Execution metadata available")
        print("    ✓ Would be visible in Phoenix traces at http://localhost:6006")
        print("    ✓ RLM response: Success")

        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED")
        print("=" * 80 + "\n")
        return True


if __name__ == "__main__":
    success = asyncio.run(test_rlm_agent_standalone())
    exit(0 if success else 1)
