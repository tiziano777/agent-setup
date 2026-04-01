"""LangGraph-compatible tools for guidance structured generation.

Factory function returns ``@tool``-decorated functions ready to attach
to any LangGraph agent's tool list.

Usage::

    from src.shared.guidance_toolkit import get_guidance_tools

    tools = get_guidance_tools()
    agent = create_react_agent(get_llm(), tools)
"""

from __future__ import annotations

from langchain_core.tools import tool

from src.shared.guidance_toolkit.config import GuidanceSettings


def get_guidance_tools(
    settings: GuidanceSettings | None = None,
) -> list:
    """Return a list of LangGraph-compatible guidance tools.

    Returns ``[guidance_json_generate, guidance_select, guidance_regex_generate]``.
    Each tool captures *settings* in its closure.

    Args:
        settings: Configuration dataclass.  Uses defaults when *None*.
    """

    @tool
    def guidance_json_generate(json_schema_description: str, prompt: str) -> str:
        """Generate structured JSON output constrained to a schema.

        The output is guaranteed to be valid JSON matching the described
        structure.  Use this when you need the LLM to produce data in a
        specific format (API payloads, structured data, etc.).

        Args:
            json_schema_description: Plain-language description of the JSON structure.
                Example: "An object with fields: name (string), age (integer),
                hobbies (list of strings)"
            prompt: What to generate.  The LLM will produce JSON based on this prompt.
        """
        from guidance import assistant, gen, system, user

        from src.shared.guidance_toolkit.llm_bridge import get_guidance_model

        model = get_guidance_model()
        lm = model

        with system():
            lm += f"You produce valid JSON only. Schema: {json_schema_description}"

        with user():
            lm += prompt

        with assistant():
            lm += gen(
                name="json_output",
                regex=r"\{[^}]*\}",
                max_tokens=1024,
            )

        return lm["json_output"]

    @tool
    def guidance_select(options: str, prompt: str) -> str:
        """Select exactly one option from a comma-separated list.

        The output is guaranteed to be one of the provided options.
        Use this when you need a deterministic choice from a fixed set
        (classification, routing, yes/no decisions, etc.).

        Args:
            options: Comma-separated list of allowed values.
                Example: "positive,negative,neutral"
            prompt: The question or context for the selection.
        """
        from src.shared.guidance_toolkit.programs import constrained_select

        option_list = [opt.strip() for opt in options.split(",") if opt.strip()]
        return constrained_select(option_list, prompt)

    @tool
    def guidance_regex_generate(pattern: str, prompt: str) -> str:
        """Generate text that matches a regular expression pattern.

        The output is guaranteed to match the provided regex.
        Use this for generating formatted strings (emails, phone numbers,
        dates, codes, identifiers, etc.).

        Args:
            pattern: Regular expression the output must match.
                Example: "[A-Z]{3}-\\d{4}" for codes like "ABC-1234"
            prompt: The context or instructions for generation.
        """
        from src.shared.guidance_toolkit.programs import regex_generate

        return regex_generate(pattern, prompt)

    return [guidance_json_generate, guidance_select, guidance_regex_generate]
