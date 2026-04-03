"""SHACL validation using pyshacl."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def check_shacl(triples: list[str], shapes_path: str) -> tuple[list[str], list[dict]]:
    """Validate triples against SHACL shapes.

    Args:
        triples: List of valid Turtle triple strings.
        shapes_path: Path to the SHACL shapes file (.ttl).

    Returns:
        Tuple of (valid_triples, shacl_violations).
        Each violation is {"triple": str, "report": str}.
    """
    from pyshacl import validate
    from rdflib import Graph

    from src.shared.rdf_validation.syntax import TURTLE_PREFIXES

    if not triples:
        return [], []

    all_turtle = TURTLE_PREFIXES + "\n".join(triples)
    data_graph = Graph()
    try:
        data_graph.parse(data=all_turtle, format="turtle")
    except Exception as e:
        logger.error("Failed to parse combined triples for SHACL: %s", e)
        return [], [{"triple": "(batch)", "report": str(e)}]

    shapes_graph = Graph()
    shapes_graph.parse(shapes_path, format="turtle")

    conforms, results_graph, results_text = validate(
        data_graph,
        shacl_graph=shapes_graph,
        inference="none",
        abort_on_first=False,
    )

    if conforms:
        return list(triples), []

    violating_subjects = set()
    for result in results_graph.subjects(predicate=None, object=None):
        violating_subjects.add(str(result))

    violations_text = results_text or "SHACL validation failed"

    valid: list[str] = []
    violations: list[dict] = []
    for triple in triples:
        is_violating = False
        for subject in violating_subjects:
            if subject in triple:
                is_violating = True
                break
        if is_violating:
            violations.append(
                {
                    "triple": triple,
                    "report": violations_text,
                }
            )
        else:
            valid.append(triple)

    if not violations and not conforms:
        return list(triples), [{"triple": "(batch)", "report": violations_text}]

    return valid, violations
