"""Node functions for text2sql agent graph."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage
from langchain_core.runnables import RunnableConfig

from src.shared.llm import get_llm
from src.shared.sql import SQLClient, get_sql_tools
from src.shared.tracing import get_tracer
from src.agents.text2sql_agent.states import Text2SQLState
from src.agents.text2sql_agent.prompts import SYSTEM_PROMPT, TABLE_SELECTION_PROMPT

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)


def _execute_tool_call(tool_name: str, tool_input: dict | str, tools: list) -> str:
    """Execute a single tool call and return result as string.

    Args:
        tool_name: Name of the tool to execute
        tool_input: Input arguments for the tool
        tools: List of available tools

    Returns:
        JSON-formatted tool result as string
    """
    tool = next((t for t in tools if t.name == tool_name), None)
    if not tool:
        return json.dumps({"error": f"Tool '{tool_name}' not found"})

    try:
        # Tool input can be a dict or string depending on LLM response format
        if isinstance(tool_input, str):
            # Parse JSON string to dict
            try:
                tool_input = json.loads(tool_input)
            except json.JSONDecodeError:
                tool_input = {"query": tool_input}  # Fallback for simple queries

        result = tool.invoke(tool_input)
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:
        logger.error(f"Tool execution failed: {tool_name} with input {tool_input}: {e}")
        return json.dumps({"error": str(e), "error_type": type(e).__name__})


def _run_llm_with_tools(
    messages: list,
    tools: list,
    max_iterations: int = 3,
) -> tuple[str, list]:
    """Run LLM with tool binding and agentic loop.

    Continues calling LLM and executing tools until LLM stops requesting tools
    or max iterations reached.

    Args:
        messages: Message history to start with
        tools: List of available tools
        max_iterations: Max tool-calling iterations

    Returns:
        Tuple of (final_response_text, updated_messages)
    """
    llm = get_llm()
    llm_with_tools = llm.bind_tools(tools)

    iteration = 0
    while iteration < max_iterations:
        iteration += 1
        logger.debug(f"LLM iteration {iteration}/{max_iterations}")

        # Call LLM
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        # Check if response has tool calls
        if not hasattr(response, "tool_calls") or not response.tool_calls:
            # No more tool calls - LLM is done
            logger.debug(f"LLM finished after {iteration} iterations")
            return response.content, messages

        # Execute tool calls
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_input = tool_call["args"]

            logger.debug(f"Executing tool: {tool_name}")
            result = _execute_tool_call(tool_name, tool_input, tools)

            # Add tool result to messages
            tool_msg = ToolMessage(
                tool_call_id=tool_call.get("id", tool_name),
                content=result,
                name=tool_name,
            )
            messages.append(tool_msg)

    logger.warning(f"Reached max iterations ({max_iterations}) in LLM tool loop")
    return response.content if hasattr(response, "content") else "", messages


def catalog_extraction_node(
    state: Text2SQLState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """Extract database catalog (tables, schemas, relationships).

    This deterministic node queries the database for all metadata needed
    by subsequent LLM nodes.
    """
    from src.shared.sql.config import SQLSettings

    with tracer.start_as_current_span("text2sql.catalog_extraction"):
        settings = SQLSettings()
        logger.debug(f"[catalog_extraction] Using connection string: {settings.connection_string[:50]}...")
        client = SQLClient(settings=settings)

        try:
            catalog = client.get_full_catalog()
            logger.info(f"Extracted catalog with {len(catalog['tables'])} tables")

            return {
                "catalog": catalog,
                "status": "selection",
                "messages": [
                    HumanMessage(
                        content=f"Extracted database catalog: {len(catalog['tables'])} tables identified"
                    )
                ],
            }

        except Exception as e:
            logger.error(f"Catalog extraction failed: {e}")
            return {
                "status": "complete",
                "error": f"Catalog extraction failed: {str(e)}",
                "messages": [
                    HumanMessage(content=f"ERROR during catalog extraction: {str(e)}")
                ],
            }


def table_selection_node(
    state: Text2SQLState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """LLM-based table selection from user prompt with tool access.

    Uses NER-like prompting to identify minimal table set needed
    to answer the user's question. LLM can use tools to explore schema
    if needed (e.g., check column names, relationships).
    """
    with tracer.start_as_current_span("text2sql.table_selection"):
        if not state.get("catalog"):
            return {
                "selected_tables": [],
                "status": "complete",
                "error": "No catalog available",
            }

        catalog = state["catalog"]
        tables = catalog["tables"]
        relationships = catalog["relationships"]

        # Build prompt for table selection
        rels_str = "\n".join([f"{r['from']} -> {r['to']}" for r in relationships])

        prompt_text = TABLE_SELECTION_PROMPT.format(
            prompt=state["prompt"],
            tables=", ".join(tables),
            relationships=rels_str,
        )

        try:
            # Get tools for LLM access
            tools = get_sql_tools()

            # Run LLM with tool access (may call tools for schema exploration)
            response_text, updated_messages = _run_llm_with_tools(
                messages=[
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=prompt_text),
                ],
                tools=tools,
                max_iterations=3,
            )

            # Parse LLM response as JSON list
            response_text = response_text.strip()

            # Try to extract JSON list from response
            if "[" in response_text:
                json_start = response_text.index("[")
                json_end = response_text.rindex("]") + 1
                json_str = response_text[json_start:json_end]
                selected = json.loads(json_str)
            else:
                selected = response_text.split(",")
                selected = [t.strip().strip('"') for t in selected]

            logger.info(f"Selected tables: {selected}")

            return {
                "selected_tables": selected,
                "status": "expansion",
                "messages": updated_messages + [
                    HumanMessage(content=f"Selected tables for query: {selected}")
                ] if updated_messages else [
                    HumanMessage(content=f"Selected tables for query: {selected}")
                ],
            }

        except Exception as e:
            logger.error(f"Table selection failed: {e}")
            return {
                "selected_tables": [],
                "status": "complete",
                "error": f"Table selection failed: {str(e)}",
                "messages": [HumanMessage(content=f"ERROR in table selection: {str(e)}")],
            }


def graph_expansion_node(
    state: Text2SQLState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """Expand sparse table selection into connected graph.

    Uses BFS to find intermediate tables connecting selected tables.
    """
    with tracer.start_as_current_span("text2sql.graph_expansion"):
        from collections import defaultdict, deque

        selected = state.get("selected_tables", [])
        catalog = state.get("catalog")

        if not selected or not catalog:
            return {
                "expanded_tables": selected,
                "status": "context",
            }

        # Build FK graph
        tables = set(catalog["tables"])
        rels = catalog["relationships"]

        # Build adjacency list: table -> [connected_tables]
        graph: dict[str, set] = defaultdict(set)
        for rel in rels:
            from_table = rel["from"].split(".")[0]
            to_table = rel["to"].split(".")[0]
            graph[from_table].add(to_table)
            graph[to_table].add(from_table)

        # Use BFS to find all connector tables
        visited = set(selected)
        queue = deque(selected)
        expanded = set(selected)

        while queue:
            current = queue.popleft()
            for neighbor in graph.get(current, set()):
                if neighbor not in visited and neighbor in tables:
                    visited.add(neighbor)
                    queue.append(neighbor)
                    expanded.add(neighbor)

        expanded_list = sorted(list(expanded))
        logger.info(f"Expanded tables from {len(selected)} to {len(expanded_list)}: {expanded_list}")

        return {
            "expanded_tables": expanded_list,
            "status": "context",
            "messages": [
                HumanMessage(
                    content=(
                        f"Expanded table selection via graph traversal "
                        f"({len(selected)} -> {len(expanded_list)}): {expanded_list}"
                    )
                )
            ],
        }


def context_builder_node(
    state: Text2SQLState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """Build compact schema context for SQL generator.

    Fetches DDL for expanded tables and formats as compact table schema (CTS).
    """
    from src.shared.sql.config import SQLSettings

    with tracer.start_as_current_span("text2sql.context_builder"):
        settings = SQLSettings()
        client = SQLClient(settings=settings)

        expanded = state.get("expanded_tables", [])
        if not expanded:
            return {
                "context": "",
                "status": "complete",
                "error": "No expanded tables",
            }

        try:
            # Fetch schemas for all expanded tables
            schemas: dict[str, Any] = {}
            for table in expanded:
                schema = client.get_table_schema(table)
                schemas[table] = schema

            # Format as compact table schema (CTS)
            cts_lines = []
            for table, schema in schemas.items():
                cols = ", ".join([f"{c['name']}({c['type']})" for c in schema["columns"]])
                cts_lines.append(f"{table}({cols})")

            # Add relationships
            cts_lines.append("\nRelationships:")
            for table, schema in schemas.items():
                for fk in schema.get("foreign_keys", []):
                    cts_lines.append(f"  {table}.{fk['column']} -> {fk['references']}")

            context = "\n".join(cts_lines)
            logger.info(f"Built schema context for {len(expanded)} tables")

            return {
                "context": context,
                "status": "generation",
                "messages": [
                    HumanMessage(content=f"Schema context ready:\n{context}")
                ],
            }

        except Exception as e:
            logger.error(f"Context building failed: {e}")
            return {
                "context": "",
                "status": "complete",
                "error": f"Context building failed: {str(e)}",
                "messages": [HumanMessage(content=f"ERROR building context: {str(e)}")],
            }


def sql_generator_node(
    state: Text2SQLState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """Generate initial SQL query from prompt + schema context with tool access.

    Uses LLM to write SQL based on user question and schema.
    LLM can use tools to explore schema details if needed.
    """
    with tracer.start_as_current_span("text2sql.sql_generator"):
        prompt = state.get("prompt")
        context = state.get("context")

        if not prompt or not context:
            return {
                "generated_query": None,
                "status": "complete",
                "error": "Missing prompt or context",
            }

        generation_prompt = f"""Based on this schema:

{context}

Answer this question by writing a SQL query:
"{prompt}"

Return ONLY the SQL query, no explanation. Ensure:
1. Correct table joins based on foreign keys
2. Proper WHERE/GROUP BY/ORDER BY clauses
3. Column aliases for readability
4. Add LIMIT 100 for safety

You have access to tools to explore the schema further if needed:
- execute_query: Run any SQL query (can use for testing)
- get_schema: Get detailed table schema
- get_catalog: Get full catalog and relationships
- get_table_stats: Get row counts and statistics"""

        try:
            # Get tools for LLM access
            tools = get_sql_tools()

            # Run LLM with tool access
            query, updated_messages = _run_llm_with_tools(
                messages=[
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=generation_prompt),
                ],
                tools=tools,
                max_iterations=3,
            )

            query = query.strip()

            # Clean up markdown code blocks if present
            if query.startswith("```"):
                query = query.split("```")[1]
                if query.startswith("sql"):
                    query = query[3:]
                query = query.strip()

            logger.info(f"Generated initial query (length={len(query)})")

            return {
                "generated_query": query,
                "status": "iteration",
                "query_iterations": [
                    {
                        "iteration": 1,
                        "query": query,
                        "error": None,
                        "retry": 0,
                    }
                ],
                "messages": updated_messages + [
                    HumanMessage(content=f"Generated SQL:\n{query}")
                ] if updated_messages else [
                    HumanMessage(content=f"Generated SQL:\n{query}")
                ],
            }

        except Exception as e:
            logger.error(f"SQL generation failed: {e}")
            return {
                "generated_query": None,
                "status": "complete",
                "error": f"SQL generation failed: {str(e)}",
                "messages": [HumanMessage(content=f"ERROR generating SQL: {str(e)}")],
            }


def query_executor_node(
    state: Text2SQLState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """Execute the generated SQL query.

    Attempts execution and either succeeds or enters feedback loop.
    """
    from src.shared.sql.config import SQLSettings

    with tracer.start_as_current_span("text2sql.query_executor"):
        settings = SQLSettings()
        client = SQLClient(settings=settings)

        query = state.get("generated_query")
        if not query:
            return {
                "status": "complete",
                "error": "No query to execute",
            }

        try:
            result = client.execute_query(query)

            if result["success"]:
                logger.info(
                    f"Query executed successfully (rows={result.get('row_count', 0)})"
                )

                return {
                    "final_query": query,
                    "final_result": result,
                    "status": "complete",
                    "messages": [
                        HumanMessage(
                            content=f"Query executed successfully:\n{json.dumps(result, indent=2)}"
                        )
                    ],
                }
            else:
                # Query failed - enter feedback loop
                logger.warning(f"Query execution failed: {result.get('error')}")

                iterations = state.get("query_iterations", [])
                iterations.append(
                    {
                        "iteration": len(iterations) + 1,
                        "query": query,
                        "error": result.get("error"),
                        "error_type": result.get("error_type"),
                        "retry": 0,
                    }
                )

                return {
                    "final_result": result,
                    "query_iterations": iterations,
                    "status": "feedback",
                    "messages": [
                        HumanMessage(
                            content=f"Query failed with error: {result.get('error')}"
                        )
                    ],
                }

        except Exception as e:
            logger.error(f"Query execution failed: {e}")

            iterations = state.get("query_iterations", [])
            iterations.append(
                {
                    "iteration": len(iterations) + 1,
                    "query": query,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "retry": 0,
                }
            )

            return {
                "query_iterations": iterations,
                "status": "feedback",
                "error": str(e),
                "messages": [HumanMessage(content=f"ERROR executing query: {str(e)}")],
            }


def feedback_loop_node(
    state: Text2SQLState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """Retry loop for failed queries with tool access (up to 3 attempts).

    Analyzes error, regenerates improved query, executes again.
    LLM can use tools to re-check schema when fixing errors.
    """
    from src.shared.sql.config import SQLSettings

    with tracer.start_as_current_span("text2sql.feedback_loop"):
        settings = SQLSettings()
        client = SQLClient(settings=settings)

        iterations = state.get("query_iterations", [])
        last_iter = iterations[-1] if iterations else None

        if not last_iter or last_iter.get("retry", 0) >= 3:
            logger.warning("Max retries reached or no iteration")
            return {
                "status": "complete",
                "error": "Max retries exceeded or invalid state",
                "messages": [
                    HumanMessage(content="Query correction failed after max retries")
                ],
            }

        current_retry = last_iter.get("retry", 0) + 1
        error = last_iter.get("error", "Unknown error")
        context = state.get("context", "")
        prompt = state.get("prompt", "")

        # Generate corrected query
        correction_prompt = f"""The previous SQL query failed with this error:
"{error}"

Original question: "{prompt}"

Schema:
{context}

Previous query:
{last_iter['query']}

Please fix the query and return ONLY the corrected SQL (no explanation).

You have access to tools to explore the schema and test queries:
- execute_query: Run any SQL query for testing
- get_schema: Get table details
- get_catalog: Get relationships
- get_table_stats: Get statistics"""

        try:
            # Get tools for LLM access
            tools = get_sql_tools()

            # Run LLM with tool access
            corrected_query, updated_messages = _run_llm_with_tools(
                messages=[
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=correction_prompt),
                ],
                tools=tools,
                max_iterations=3,
            )

            corrected_query = corrected_query.strip()

            if corrected_query.startswith("```"):
                corrected_query = corrected_query.split("```")[1]
                if corrected_query.startswith("sql"):
                    corrected_query = corrected_query[3:]
                corrected_query = corrected_query.strip()

            # Execute corrected query
            result = client.execute_query(corrected_query)

            new_iter = {
                "iteration": len(iterations) + 1,
                "query": corrected_query,
                "error": None if result["success"] else result.get("error"),
                "error_type": None if result["success"] else result.get("error_type"),
                "retry": current_retry,
                "success": result["success"],
            }

            iterations.append(new_iter)

            if result["success"]:
                logger.info(
                    f"Query corrected and executed successfully (retry {current_retry})"
                )

                return {
                    "final_query": corrected_query,
                    "final_result": result,
                    "query_iterations": iterations,
                    "status": "complete",
                    "messages": (updated_messages if updated_messages else []) + [
                        HumanMessage(
                            content=(
                                f"Query corrected and executed (retry {current_retry}):\n"
                                f"{json.dumps(result, indent=2)}"
                            )
                        )
                    ],
                }
            else:
                # Still failing - loop again
                logger.warning(f"Corrected query still failed (retry {current_retry})")

                return {
                    "query_iterations": iterations,
                    "status": "feedback",  # Try again
                    "messages": (updated_messages if updated_messages else []) + [
                        HumanMessage(
                            content=f"Retry {current_retry} failed: {result.get('error')}"
                        )
                    ],
                }

        except Exception as e:
            logger.error(f"Feedback loop correction failed: {e}")

            new_iter = {
                "iteration": len(iterations) + 1,
                "query": last_iter["query"],
                "error": str(e),
                "error_type": type(e).__name__,
                "retry": current_retry,
            }

            iterations.append(new_iter)

            return {
                "query_iterations": iterations,
                "status": "complete",
                "error": f"Correction failed: {str(e)}",
                "messages": [
                    HumanMessage(content=f"ERROR in correction loop: {str(e)}")
                ],
            }
