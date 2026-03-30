"""Tests for code_runner."""

from src.agents.code_runner.states.state import AgentState


class TestAgentGraph:
    """Test the Graph API agent."""

    def test_graph_compiles(self):
        from src.agents.code_runner.agent import graph

        assert graph is not None

    def test_graph_is_callable(self):
        from src.agents.code_runner.agent import graph

        assert hasattr(graph, "invoke")


class TestTools:
    """Test that sandbox tools are importable."""

    def test_execute_cmd_importable(self):
        """Verify execute_cmd can be imported.

        Note: Actually invoking the tool requires Docker to be running.
        """
        from src.agents.code_runner.tools import execute_cmd

        assert execute_cmd is not None
        assert execute_cmd.name == "execute_cmd"


class TestAgentState:
    """Test state definition."""

    def test_state_has_messages(self):
        assert "messages" in AgentState.__annotations__
