"""Configuration for rdf_reader.

Low temperature for maximum SPARQL generation precision.
High max_tokens for large INSERT DATA blocks with many triples.
"""

from dataclasses import dataclass, field


@dataclass
class AgentSettings:
    """Settings specific to this agent."""

    name: str = "rdf_reader"
    description: str = (
        "RDF triple extraction agent: reads complex text, builds a session "
        "knowledge graph via SPARQL INSERT, then answers questions with "
        "exact SPARQL SELECT queries"
    )
    model: str = "llm"
    temperature: float = 0.1
    max_tokens: int = 4096
    tags: list[str] = field(
        default_factory=lambda: ["rdf", "sparql", "knowledge-graph", "triple-extraction"]
    )


settings = AgentSettings()
