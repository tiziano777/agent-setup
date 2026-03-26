"""Tests for __AGENT_NAME__."""

from src.agents.__AGENT_NAME__.states.state import AgentState


class TestAgentGraph:
    """Test the Graph API agent."""

    def test_graph_compiles(self):
        from src.agents.__AGENT_NAME__.agent import graph

        assert graph is not None

    def test_graph_is_callable(self):
        from src.agents.__AGENT_NAME__.agent import graph

        assert hasattr(graph, "invoke")


class TestTools:
    """Test that sandbox tools are importable."""

    def test_execute_cmd_importable(self):
        """Verify execute_cmd can be imported.

        Note: Actually invoking the tool requires Docker to be running.
        """
        from src.agents.__AGENT_NAME__.tools import execute_cmd

        assert execute_cmd is not None
        assert execute_cmd.name == "execute_cmd"


class TestAgentState:
    """Test state definition."""

    def test_state_has_messages(self):
        assert "messages" in AgentState.__annotations__
