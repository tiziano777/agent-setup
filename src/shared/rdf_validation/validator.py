"""Combined RDF validation (syntax + SHACL)."""

from __future__ import annotations

from src.shared.rdf_validation.shacl import check_shacl
from src.shared.rdf_validation.syntax import check_syntax


def validate_rdf(
    triples: list[str],
    shacl_shapes_path: str,
) -> dict:
    """Validate RDF triples in two sequential phases.

    Phase 1: Turtle syntax check (rdflib).
    Phase 2: SHACL validation (pyshacl) on syntax-valid triples.

    Returns:
        {
            "valid": List[str],           # triples that passed all checks
            "syntax_errors": List[dict],  # {"triple": ..., "error": ...}
            "shacl_violations": List[dict] # {"triple": ..., "report": ...}
        }
    """
    syntax_valid, syntax_errors = check_syntax(triples)
    shacl_valid, shacl_violations = check_shacl(syntax_valid, shacl_shapes_path)

    return {
        "valid": shacl_valid,
        "syntax_errors": syntax_errors,
        "shacl_violations": shacl_violations,
    }
