"""Turtle syntax validation using rdflib."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

TURTLE_PREFIXES = (
    "@prefix schema: <https://schema.org/> .\n"
    "@prefix ex: <http://example.org/> .\n"
    "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
    "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
    "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n"
)


def check_syntax(triples: list[str]) -> tuple[list[str], list[dict]]:
    """Validate Turtle syntax for each triple individually.

    Args:
        triples: List of Turtle triple strings.

    Returns:
        Tuple of (valid_triples, syntax_errors).
        Each error is {"triple": str, "error": str}.
    """
    from rdflib import Graph

    valid: list[str] = []
    errors: list[dict] = []

    for triple in triples:
        triple_stripped = triple.strip()
        if not triple_stripped:
            continue
        try:
            g = Graph()
            g.parse(data=TURTLE_PREFIXES + triple_stripped, format="turtle")
            if len(g) > 0:
                valid.append(triple_stripped)
            else:
                errors.append(
                    {
                        "triple": triple_stripped,
                        "error": "No triples parsed from input",
                    }
                )
        except Exception as e:
            errors.append(
                {
                    "triple": triple_stripped,
                    "error": str(e),
                }
            )
            logger.debug("Syntax error in triple: %s -> %s", triple_stripped[:80], e)

    return valid, errors
