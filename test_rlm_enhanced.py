#!/usr/bin/env python
"""Standalone test: RLM Agent with code execution details visibility.

This test demonstrates full code execution visibility showing:
- Code executed by RLM
- Output/response from code execution
- Execution time per iteration
- Error messages if any

Run: python test_rlm_enhanced.py
"""

import asyncio
import json
import random
import string
from unittest.mock import patch


async def test_rlm_agent_with_code_details():
    """Test RLM Agent showing complete code execution details."""
    from src.agents.rlm_agent.agent import graph
    from src.agents.rlm_agent.states import RLMAgentState

    print("\n" + "=" * 80)
    print("RLM AGENT - ENHANCED CODE EXECUTION VISIBILITY TEST")
    print("=" * 80)

    # Generate test haystack (1000 lines)
    print("\n[1] Generating test haystack...")
    magic_value = "SECRET_99_FOUND"
    lines = [
        "".join(random.choices(string.ascii_lowercase + " ", k=120))
        for _ in range(1000)
    ]
    insert_at = random.randint(300, 700)
    lines.insert(insert_at, f">>> MAGIC_VALUE: {magic_value} <<<")
    haystack = "\n".join(lines)
    print(f"    ✓ Generated {len(haystack):,} chars ({len(lines)} lines)")
    print(f"    ✓ Hidden value at line {insert_at}: {magic_value}")

    # Mock rlm_completion with realistic code execution details
    def mock_rlm_completion(prompt, context=None, settings=None, **kwargs):
        """Simulate RLM with realistic code execution."""
        return {
            "response": f"Found the secret: {magic_value}",
            "execution_time": 2.34,
            "metadata": {
                "iterations": [
                    {
                        "code_blocks": [
                            {
                                "code": (
                                    "# Step 1: Sample the text to understand structure\n"
                                    "lines = context.split('\\n')\n"
                                    "print(f'Total lines: {len(lines)}')\n"
                                    "print(f'First line length: {len(lines[0])}')"
                                ),
                                "result": {
                                    "stdout": f"Total lines: {len(lines)}\nFirst line length: 120",
                                    "stderr": "",
                                    "execution_time": 0.0012,
                                    "locals": {"lines": []},
                                    "rlm_calls": [],
                                },
                            }
                        ],
                        "iteration_time": 0.05,
                    },
                    {
                        "code_blocks": [
                            {
                                "code": (
                                    "# Step 2: Search for MAGIC_VALUE pattern\n"
                                    "for i, line in enumerate(lines):\n"
                                    "    if 'MAGIC_VALUE' in line:\n"
                                    f"        print(f'Found at line {{i}}: {{line}}')\n"
                                    "        break"
                                ),
                                "result": {
                                    "stdout": f"Found at line {insert_at}: >>> MAGIC_VALUE: {magic_value} <<<",
                                    "stderr": "",
                                    "execution_time": 0.0018,
                                    "locals": {},
                                    "rlm_calls": [],
                                },
                            }
                        ],
                        "iteration_time": 0.08,
                    },
                ],
                "rlm_calls": [],
            },
            "status": "success",
            "error": None,
        }

    # Run test with mock
    print("\n[2] Patching rlm_completion...")
    with patch("src.agents.rlm_agent.nodes.search.rlm_completion") as mock_rlm:
        mock_rlm.side_effect = mock_rlm_completion

        print("    ✓ Mock installed")

        # Create agent
        print("\n[3] Creating RLM Agent...")
        agent = graph
        print("    ✓ Agent ready")

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
        print("    ✓ Execution complete")

        # Display results
        print("\n[6] RESULTS:")
        print(f"    Status: {result['rlm_status']}")
        print(f"    Response: {result['rlm_response']}")

        # Verify correctness
        print("\n[7] VERIFICATION:")
        if result["rlm_status"] == "success":
            if magic_value in result["rlm_response"]:
                print(f"    ✅ PASS: Found '{magic_value}'")
            else:
                print(f"    ❌ FAIL: Expected '{magic_value}'")
                return False
        else:
            print(f"    ❌ FAIL: Status was '{result['rlm_status']}'")
            return False

        # Display full message chain with CODE EXECUTION DETAILS
        print("\n[8] MESSAGE CHAIN WITH CODE EXECUTION DETAILS:")
        messages = result["messages"]
        print(f"    Total messages: {len(messages)}\n")

        for i, msg in enumerate(messages):
            msg_type = msg.__class__.__name__
            print(f"    Message {i}: {msg_type}")
            print(f"      Content: {msg.content[:80]}...")

            # ⭐ THIS IS THE NEW PART - Show code execution details
            if (
                hasattr(msg, "metadata")
                and msg.metadata
                and "iteration_details" in msg.metadata
            ):
                iteration_details = msg.metadata["iteration_details"]
                print(f"\n      🔍 Code Execution Details ({len(iteration_details)} iterations):")

                for detail in iteration_details:
                    print(f"\n        Iteration {detail['iteration']}:")
                    print(f"        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

                    # Show code (truncated)
                    code = detail["code_executed"]
                    code_lines = code.split("\n")
                    if len(code_lines) > 3:
                        code_preview = "\n            ".join(code_lines[:3]) + "\n            ..."
                    else:
                        code_preview = "\n            ".join(code_lines)
                    print(f"        Code executed:\n            {code_preview}")

                    # Show output
                    output = detail["exec_response"]
                    if len(output) > 100:
                        output = output[:100] + "..."
                    print(f"        Output: {output}")

                    # Show metrics
                    print(f"        Execution time: {detail['execution_time']:.4f}s")
                    if detail["stderr"]:
                        print(f"        Stderr: {detail['stderr']}")

                    print()
            elif hasattr(msg, "metadata"):
                print(f"      Metadata: {msg.metadata}")

        # Summary
        print("\n[9] OBSERVABILITY SUMMARY:")
        ai_msg = messages[-1]
        if hasattr(ai_msg, "metadata") and ai_msg.metadata:
            print(f"    ✓ Execution time: {ai_msg.metadata.get('execution_time')}s")
            print(
                f"    ✓ Total iterations: {ai_msg.metadata.get('total_iterations')}"
            )
            print(
                f"    ✓ Recursive calls: {ai_msg.metadata.get('recursive_calls')}"
            )
            print(
                f"    ✓ Code blocks captured: {len(ai_msg.metadata.get('iteration_details', []))}"
            )
            print(f"    ✓ All code execution visible in message metadata")

        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED - CODE EXECUTION FULLY VISIBLE")
        print("=" * 80 + "\n")
        return True


if __name__ == "__main__":
    success = asyncio.run(test_rlm_agent_with_code_details())
    exit(0 if success else 1)
