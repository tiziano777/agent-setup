"""Tests for annotator agent."""

from src.agents.annotator.states import AnnotatorState


class TestAnnotatorGraph:
    def test_graph_compiles(self):
        from src.agents.annotator.agent import graph

        assert graph is not None

    def test_graph_is_callable(self):
        from src.agents.annotator.agent import graph

        assert hasattr(graph, "invoke")


class TestAnnotatorState:
    def test_state_has_required_keys(self):
        annotations = AnnotatorState.__annotations__
        for key in ("messages", "all_entries", "current_batch", "batch_index", "status"):
            assert key in annotations
