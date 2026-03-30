"""rag_agent: Functional API definition.

Defines the agent as a @entrypoint/@task workflow with retrieve and generate steps.
"""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint, task

from src.agents.rag_agent.prompts.system import get_prompt
from src.shared.llm import get_llm
from src.shared.retrieval import get_retriever


@task
def retrieve_task(query: str) -> dict:
    """Search the in-memory hybrid retriever for relevant documents."""
    retriever = get_retriever()
    results = retriever.search(query, k=3)
    context = "\n\n".join(doc["content"] for doc in results)
    sources = [doc["id"] for doc in results]
    return {"context": context, "sources": sources}


@task
def generate_task(question: str, context: str) -> str:
    """Generate a grounded answer from the retrieved context."""
    llm = get_llm(temperature=0.2)
    system_prompt = get_prompt(context=context)
    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ])
    return response.content


checkpointer = InMemorySaver()


@entrypoint(checkpointer=checkpointer)
def workflow(inputs: dict) -> dict:
    """Functional API workflow for rag_agent.

    Args:
        inputs: dict with key "messages" (list of message dicts).

    Returns:
        dict with "response" and "sources" keys.
    """
    messages = inputs.get("messages", [])
    query = messages[-1]["content"] if messages else ""

    retrieval = retrieve_task(query).result()
    response = generate_task(query, retrieval["context"]).result()

    return {"response": response, "sources": retrieval["sources"]}
