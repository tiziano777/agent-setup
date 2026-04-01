"""State definition for rdf_reader.

Extends the base messages state with domain-specific fields for the
two-node extract → query pipeline. RDF data lives in Fuseki (session
graph), not in agent state.
"""

from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """Core state shared across all nodes in this agent's graph."""

    messages: Annotated[list[AnyMessage], add_messages]
    context: str  # Long input text to extract triples from
    instruction: str  # User's question to answer
    triple_count: int  # Number of triples extracted (verification)
    sparql_result: str  # Raw SPARQL result for the query node
