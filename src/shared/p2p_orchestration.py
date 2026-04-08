"""Multi-agent orchestration utilities.

Provides factory functions for the three main multi-agent patterns:
1. Supervisor -- a central LLM routes to worker agents
2. Network (swarm/p2p) -- agents hand off to each other freely
3. Independent -- agents run in parallel, results merged

These utilities consume agents from the registry and return
compiled LangGraph graphs ready to invoke.
"""

from typing import Any

from langchain_core.tools import tool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command

from src.shared.llm import get_llm
from src.shared.registry import AgentRegistry


def create_handoff_tool(agent_name: str, description: str | None = None):
    """Create a tool that hands off control to another agent."""
    tool_name = f"transfer_to_{agent_name}"
    tool_desc = description or f"Transfer to {agent_name}"

    @tool(tool_name, description=tool_desc)
    def handoff_tool(
        tool_call_id: str = "",
    ) -> Command:
        tool_message = {
            "role": "tool",
            "content": f"Successfully transferred to {agent_name}",
            "name": tool_name,
            "tool_call_id": tool_call_id,
        }
        return Command(
            goto=agent_name,
            update={"messages": [tool_message]},
            graph=Command.PARENT,
        )

    return handoff_tool


def build_supervisor(
    agent_names: list[str],
    registry: AgentRegistry,
    supervisor_model: str = "llm",
    supervisor_prompt: str = "You are a supervisor. Route tasks to the best agent.",
) -> Any:
    """Build a supervisor multi-agent graph.

    The supervisor is a ReAct agent whose tools are handoff tools
    for each worker agent. Workers are added as subgraph nodes.
    """
    handoff_tools = [create_handoff_tool(name) for name in agent_names]
    llm = get_llm(model=supervisor_model)

    builder = StateGraph(MessagesState)

    supervisor_agent = create_react_agent(
        llm,
        handoff_tools,
        prompt=supervisor_prompt,
    )
    builder.add_node("supervisor", supervisor_agent)

    for name in agent_names:
        builder.add_node(name, registry.get_graph(name))
        builder.add_edge(name, "supervisor")

    builder.add_edge(START, "supervisor")

    return builder.compile()


def build_network(
    agent_configs: dict[str, dict],
    registry: AgentRegistry,
) -> Any:
    """Build a peer-to-peer multi-agent network graph.

    Every agent can hand off to every other agent via transfer tools.

    Args:
        agent_configs: Dict mapping agent name -> config dict with keys:
            "tools": list of additional tools
            "prompt": system prompt
        registry: The agent registry instance.
    """
    agent_names = list(agent_configs.keys())
    builder = StateGraph(MessagesState)
    llm = get_llm()

    for name in agent_names:
        other_agents = [n for n in agent_names if n != name]
        transfer_tools = [create_handoff_tool(a) for a in other_agents]
        cfg = agent_configs[name]
        all_tools = cfg.get("tools", []) + transfer_tools

        agent = create_react_agent(
            llm,
            all_tools,
            prompt=cfg.get("prompt", f"You are {name}."),
        )
        builder.add_node(name, agent)

    builder.add_edge(START, agent_names[0])

    return builder.compile()


def build_independent(
    agent_names: list[str],
    registry: AgentRegistry,
) -> Any:
    """Build a graph that runs multiple agents independently in parallel.

    All agents receive the same input and their outputs are merged.
    """
    builder = StateGraph(MessagesState)

    for name in agent_names:
        builder.add_node(name, registry.get_graph(name))
        builder.add_edge(START, name)
        builder.add_edge(name, END)

    return builder.compile()
