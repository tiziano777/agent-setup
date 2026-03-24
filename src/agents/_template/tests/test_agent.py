"""Tests for __AGENT_NAME__."""

from src.agents.__AGENT_NAME__.states.state import AgentState


class TestAgentGraph:
    """Test the Graph API agent."""

    def test_graph_compiles(self):
        from src.agents.__AGENT_NAME__.agent import graph

        assert graph is not None

    def test_graph_has_nodes(self):
        from src.agents.__AGENT_NAME__.agent import build_graph

        builder = build_graph()
        assert "process" in builder.nodes


class TestAgentState:
    """Test state definition."""

    def test_state_has_messages(self):
        assert "messages" in AgentState.__annotations__
