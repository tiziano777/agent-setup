"""Annotator agent: LLM-as-judge for DPO negative quality.

3-node looping StateGraph:
    START → load_batch → judge → write_output → (more? → load_batch | done → END)
"""

from langgraph.graph import END, START, StateGraph

from src.agents.annotator.nodes import judge, load_batch, write_output
from src.agents.annotator.states import AnnotatorState


def _should_continue(state: AnnotatorState) -> str:
    """Route back to load_batch if entries remain, else finish."""
    if state["batch_index"] < state["total_entries"]:
        return "load_batch"
    return END


def build_graph():
    """Construct the annotator StateGraph."""
    builder = StateGraph(AnnotatorState)

    builder.add_node("load_batch", load_batch)
    builder.add_node("judge", judge)
    builder.add_node("write_output", write_output)

    builder.add_edge(START, "load_batch")
    builder.add_edge("load_batch", "judge")
    builder.add_edge("judge", "write_output")
    builder.add_conditional_edges("write_output", _should_continue)

    return builder.compile()


graph = build_graph()


if __name__ == "__main__":
    import logging

    from src.agents.annotator.config import settings

    logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")
    result = graph.invoke({"messages": []})
    print(f"\nDone: {result['processed_count']}/{result['total_entries']} entries judged")
    print(f"Output: {settings.output_path}")
