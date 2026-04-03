"""RDF validation toolkit (syntax + SHACL).

Provides reusable RDF validation functions for any agent that works with
RDF triples. Uses rdflib for syntax checks and pyshacl for SHACL validation.

Quick start::

    from src.shared.rdf_validation import check_syntax, check_shacl

    valid, errors = check_syntax(["<http://ex.org/s> <http://ex.org/p> <http://ex.org/o> ."])
    valid, violations = check_shacl(valid, "path/to/shapes.ttl")
"""

__all__ = [
    "check_syntax",
    "check_shacl",
    "validate_rdf",
]


def check_syntax(triples: list[str]) -> tuple[list[str], list[dict]]:
    """Check Turtle syntax for each triple. Returns (valid, errors)."""
    from src.shared.rdf_validation.syntax import check_syntax as _fn

    return _fn(triples)


def check_shacl(triples: list[str], shapes_path: str) -> tuple[list[str], list[dict]]:
    """Validate triples against SHACL shapes. Returns (valid, violations)."""
    from src.shared.rdf_validation.shacl import check_shacl as _fn

    return _fn(triples, shapes_path)


def validate_rdf(triples: list[str], shacl_shapes_path: str) -> dict:
    """Full validation: syntax check then SHACL. Returns categorized results."""
    from src.shared.rdf_validation.validator import validate_rdf as _fn

    return _fn(triples, shacl_shapes_path)
