"""Evaluation scorers for code_runner.

Scoring functions to evaluate agent output quality.
Can be used standalone or with the Phoenix evaluation toolkit.

Phoenix toolkit usage (requires ``pip install -e '.[phoenix]'``)::

    from src.shared.phoenix_eval import (
        correctness_evaluator,
        faithfulness_evaluator,
        evaluate_batch,
        create_llm_judge,
    )

    # Built-in evaluators
    results = evaluate_batch(
        data=[{"input": "...", "output": "...", "context": "..."}],
        evaluators=[correctness_evaluator(), faithfulness_evaluator()],
    )

    # Custom LLM-as-Judge
    tone_judge = create_llm_judge(
        name="tone",
        prompt_template=(
            "Is the response professional?\\n"
            "Input: {input}\\nOutput: {output}\\n"
            "Answer PROFESSIONAL or CASUAL."
        ),
        choices={"PROFESSIONAL": 1.0, "CASUAL": 0.0},
    )
"""


def relevance_score(query: str, response: str) -> float:
    """Compute a relevance score between query and response.

    Returns a float in [0.0, 1.0]. Higher = more relevant.
    Replace with actual evaluation logic (LLM-as-judge, semantic similarity, etc.).
    """
    return 1.0 if query.lower() in response.lower() else 0.5
