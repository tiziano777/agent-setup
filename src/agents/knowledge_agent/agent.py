"""knowledge_agent: Graph API definition.

ReAct agent with 4 tools:
- cognee_add: Store information in the knowledge graph
- cognee_search: Search the knowledge graph
- cognee_cognify: Trigger knowledge graph construction
- execute_cmd: Sandboxed shell execution

The agent autonomously decides which tools to use via create_react_agent.
Cognee handles the ECL pipeline (Extract-Cognify-Load) automatically:
when cognee_add is called, data is extracted into entities/relationships,
cognified into a knowledge graph (Neo4j), and loaded into vector indexes (Qdrant).
"""

from langgraph.prebuilt import create_react_agent

from src.agents.knowledge_agent.config import settings
from src.agents.knowledge_agent.prompts.system import SYSTEM_PROMPT
from src.agents.knowledge_agent.tools import get_knowledge_agent_tools
from src.shared.llm import get_llm


def build_graph(tools: list | None = None):
    """Construct the knowledge agent.

    Args:
        tools: Optional tool list override. If None, uses the default
               Cognee + sandbox tools. Useful for testing with mock tools.
    """
    llm = get_llm(temperature=settings.temperature)
    if tools is None:
        tools = get_knowledge_agent_tools()
    return create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)


graph = build_graph()
