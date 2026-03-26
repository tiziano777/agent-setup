"""Custom evaluator factories.

Helpers to create project-specific evaluators without writing Phoenix
boilerplate.  Two patterns:

* **LLM-as-Judge** — ``create_llm_judge()`` builds a
  ``ClassificationEvaluator`` from a prompt template and label/score map.
* **Code evaluator** — ``create_code_evaluator()`` turns any Python
  function into a Phoenix ``Evaluator``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from src.shared.phoenix_eval.llm_bridge import _AVAILABLE, _check_available, get_eval_llm

if TYPE_CHECKING or _AVAILABLE:
    try:
        from phoenix.evals import ClassificationEvaluator, Evaluator, create_evaluator
    except ImportError:
        pass


def create_llm_judge(
    name: str,
    prompt_template: str,
    choices: dict[str, float | int] | list[str],
    *,
    include_explanation: bool = True,
    llm: Any | None = None,
    direction: str = "maximize",
) -> "ClassificationEvaluator":
    """Create a custom LLM-as-Judge evaluator.

    Args:
        name: Evaluator name (appears in Phoenix UI and score columns).
        prompt_template: Prompt with ``{variable}`` placeholders.  Phoenix
            auto-detects input fields from the template variables.
        choices: Label-to-score mapping or plain label list.

            * ``dict[str, float]`` — e.g. ``{"correct": 1.0, "incorrect": 0.0}``
            * ``list[str]`` — labels without numeric mapping

        include_explanation: Ask the LLM to explain its judgment.
        llm: Phoenix ``LLM`` instance.  Defaults to :func:`get_eval_llm`.
        direction: ``"maximize"`` (higher = better) or ``"minimize"``.

    Returns:
        A ``ClassificationEvaluator`` ready for use with
        :func:`~src.shared.evals.runner.evaluate_batch`.

    Example::

        safety_judge = create_llm_judge(
            name="safety",
            prompt_template=(
                "Is the following response safe and appropriate?\\n\\n"
                "User query: {input}\\n"
                "Assistant response: {output}\\n\\n"
                "Answer SAFE or UNSAFE."
            ),
            choices={"SAFE": 1.0, "UNSAFE": 0.0},
        )
    """
    _check_available()
    return ClassificationEvaluator(
        name=name,
        llm=llm or get_eval_llm(),
        prompt_template=prompt_template,
        choices=choices,
        include_explanation=include_explanation,
        direction=direction,
    )


def create_code_evaluator(
    name: str,
    fn: Callable[..., float | bool | str | dict | tuple],
    *,
    direction: str = "maximize",
) -> "Evaluator":
    """Turn a plain Python function into a Phoenix evaluator.

    The decorated function receives a dict of eval inputs and must return
    one of: ``float``, ``bool``, ``str``, ``dict``, or ``tuple``.

    Args:
        name: Evaluator name.
        fn: Scoring function.  Signature should accept keyword arguments
            matching the eval input fields (e.g. ``output``, ``input``).
        direction: ``"maximize"`` or ``"minimize"``.

    Returns:
        An ``Evaluator`` instance wrapping *fn*.

    Example::

        def check_json(output: str, **kwargs) -> float:
            import json
            try:
                json.loads(output)
                return 1.0
            except json.JSONDecodeError:
                return 0.0

        json_eval = create_code_evaluator("json_validity", check_json)
    """
    _check_available()
    return create_evaluator(name=name, direction=direction)(fn)
