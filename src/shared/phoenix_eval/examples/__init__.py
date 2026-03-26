"""Phoenix evaluation toolkit — practical examples.

Standalone, runnable examples demonstrating every evaluator category in
``src.shared.evals``.  Each file is self-contained, heavily commented,
and designed for copy-paste reuse inside agent workflows.

Examples:

    ex_response_quality.py
        Correctness, conciseness, and refusal evaluators on Q&A data.

    ex_rag_evaluation.py
        Faithfulness, document relevance, and hallucination evaluators
        on retrieval-augmented generation data.

    ex_tool_use.py
        Tool selection, invocation, and response-handling evaluators
        on agent tool-call data.

    ex_custom_evaluators.py
        Custom LLM-as-Judge (safety, tone) and deterministic code
        evaluators (JSON validity, word-count).

    ex_full_pipeline.py
        End-to-end pipeline: build evaluator suite, run batch
        evaluation, convert to Phoenix annotations, print summary.

Prerequisites:
    - Infrastructure running (``make build``)
    - Phoenix extras installed (``pip install -e '.[phoenix]'``)

Run any example directly::

    python -m src.shared.evals.examples.ex_response_quality
"""
