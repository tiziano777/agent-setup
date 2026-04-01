"""Built-in guidance program factories.

Provides ready-to-use structured generation programs that wrap guidance
primitives (gen, select, json, regex, grammar).  All programs route
LLM calls through the LiteLLM proxy via :func:`get_guidance_model`.

Each program uses an inner ``@guidance``-decorated function for the
constrained generation portion, enabling proper grammar composition
and automatic token fast-forwarding.

Usage::

    from src.shared.guidance_toolkit.programs import structured_json
    from pydantic import BaseModel

    class Person(BaseModel):
        name: str
        age: int

    result = structured_json(Person, "Extract person info from: John is 30 years old")
    # result == {"name": "John", "age": 30}
"""

from __future__ import annotations

import json as json_mod
import logging
from typing import Any

from src.shared.guidance_toolkit.config import _check_available
from src.shared.guidance_toolkit.llm_bridge import get_guidance_model

logger = logging.getLogger(__name__)


def structured_json(
    schema: type,
    prompt: str,
    *,
    model=None,
    temperature: float | None = None,
    system_prompt: str | None = None,
    capture_name: str = "json_output",
) -> dict[str, Any]:
    """Generate JSON output constrained to a Pydantic model schema.

    Uses guidance's ``guidance.json()`` to guarantee the output
    conforms to the provided schema.

    Args:
        schema: A Pydantic BaseModel class defining the JSON structure.
        prompt: The user prompt describing what to generate.
        model: Optional guidance model override.
        temperature: Sampling temperature override.
        system_prompt: Optional system prompt prepended to the conversation.
        capture_name: Name for the captured output in the guidance program.

    Returns:
        A dict parsed from the constrained JSON output.
    """
    _check_available()
    from guidance import assistant, json, system, user
    from guidance import guidance as _guidance

    @_guidance
    def _json_program(lm, schema, capture_name):
        lm += json(name=capture_name, schema=schema)
        return lm

    if model is None:
        model = get_guidance_model(temperature=temperature)

    lm = model

    if system_prompt:
        with system():
            lm += system_prompt

    with user():
        lm += prompt

    with assistant():
        lm += _json_program(schema=schema, capture_name=capture_name)

    raw = lm[capture_name]
    return json_mod.loads(raw) if isinstance(raw, str) else raw


def constrained_select(
    options: list[str],
    prompt: str,
    *,
    model=None,
    temperature: float | None = None,
    system_prompt: str | None = None,
    capture_name: str = "selection",
) -> str:
    """Force the LLM to select exactly one option from a provided list.

    Uses guidance's ``select()`` primitive to guarantee the output
    is one of the allowed values.

    Args:
        options: List of allowed string values.
        prompt: The user prompt describing the selection task.
        model: Optional guidance model override.
        temperature: Sampling temperature override.
        system_prompt: Optional system prompt.
        capture_name: Name for the captured output.

    Returns:
        The selected option as a string.
    """
    _check_available()
    from guidance import assistant, select, system, user
    from guidance import guidance as _guidance

    @_guidance
    def _select_program(lm, options, capture_name):
        lm += select(options, name=capture_name)
        return lm

    if model is None:
        model = get_guidance_model(temperature=temperature)

    lm = model

    if system_prompt:
        with system():
            lm += system_prompt

    with user():
        lm += prompt

    with assistant():
        lm += _select_program(options=options, capture_name=capture_name)

    return lm[capture_name]


def regex_generate(
    pattern: str,
    prompt: str,
    *,
    model=None,
    temperature: float | None = None,
    system_prompt: str | None = None,
    capture_name: str = "regex_output",
    max_tokens: int = 256,
) -> str:
    """Generate text constrained to match a regular expression.

    Uses guidance's ``gen(regex=...)`` to guarantee the output
    matches the provided pattern.

    Args:
        pattern: Regular expression the output must match.
        prompt: The user prompt.
        model: Optional guidance model override.
        temperature: Sampling temperature override.
        system_prompt: Optional system prompt.
        capture_name: Name for the captured output.
        max_tokens: Maximum tokens to generate.

    Returns:
        The generated text matching the regex pattern.
    """
    _check_available()
    from guidance import assistant, gen, system, user
    from guidance import guidance as _guidance

    @_guidance
    def _regex_program(lm, pattern, capture_name, max_tokens):
        lm += gen(name=capture_name, regex=pattern, max_tokens=max_tokens)
        return lm

    if model is None:
        model = get_guidance_model(temperature=temperature)

    lm = model

    if system_prompt:
        with system():
            lm += system_prompt

    with user():
        lm += prompt

    with assistant():
        lm += _regex_program(
            pattern=pattern, capture_name=capture_name, max_tokens=max_tokens
        )

    return lm[capture_name]


def grammar_generate(
    grammar_fn,
    prompt: str,
    *,
    model=None,
    temperature: float | None = None,
    system_prompt: str | None = None,
    capture_name: str = "grammar_output",
    **grammar_kwargs,
) -> str:
    """Generate text using a custom @guidance grammar function.

    The grammar_fn should be a function decorated with ``@guidance``
    (or ``@guidance(stateless=True)``) that accepts ``lm`` as first arg
    and returns the modified model with captures.

    Example::

        from guidance import guidance, gen, select

        @guidance(stateless=True)
        def fruit_pair(lm):
            options = ["apple", "banana", "cherry"]
            lm += select(options, name="first")
            lm += " and "
            lm += select(options, name="second")
            return lm

        result = grammar_generate(fruit_pair, "Pick two fruits")

    Args:
        grammar_fn: A @guidance-decorated function returning a grammar.
        prompt: The user prompt.
        model: Optional guidance model override.
        temperature: Sampling temperature override.
        system_prompt: Optional system prompt.
        capture_name: Name for the captured output.
        **grammar_kwargs: Keyword arguments passed to the grammar function.

    Returns:
        The generated text from the grammar (captured under *capture_name*
        if the grammar uses that name, otherwise the full assistant output).
    """
    _check_available()
    from guidance import assistant, system, user
    from guidance import guidance as _guidance

    @_guidance
    def _grammar_wrapper(lm, grammar_fn, grammar_kwargs):
        lm += grammar_fn(**grammar_kwargs)
        return lm

    if model is None:
        model = get_guidance_model(temperature=temperature)

    lm = model

    if system_prompt:
        with system():
            lm += system_prompt

    with user():
        lm += prompt

    with assistant():
        lm += _grammar_wrapper(grammar_fn=grammar_fn, grammar_kwargs=grammar_kwargs)

    # Try to retrieve the named capture; fall back to the full output
    try:
        return lm[capture_name]
    except KeyError:
        return str(lm)


# ── CFG support ─────────────────────────────────────────────────────


def cfg_generate(
    grammar_fn,
    prompt: str,
    *,
    model=None,
    temperature: float | None = None,
    system_prompt: str | None = None,
    capture_names: list[str] | None = None,
    **grammar_kwargs,
) -> dict[str, str]:
    """Execute a ``@guidance(stateless=True)`` CFG grammar and return all captures.

    Unlike :func:`grammar_generate` (which returns a single string), this
    function returns a dict of all named captures produced by the grammar.
    Token fast-forwarding is automatic when grammar constraints make the
    next token deterministic.

    Args:
        grammar_fn: A ``@guidance(stateless=True)`` decorated function
            defining the CFG grammar.  Should use primitives like
            ``gen()``, ``select()``, ``one_or_more()``, etc.
        prompt: The user prompt.
        model: Optional guidance model override.
        temperature: Sampling temperature override.
        system_prompt: Optional system prompt.
        capture_names: List of capture names to extract from the result.
            If *None*, attempts to extract all string-valued captures.
        **grammar_kwargs: Keyword arguments passed to the grammar function.

    Returns:
        A dict mapping capture names to their string values.

    Example::

        from guidance import guidance, gen, select

        @guidance(stateless=True)
        def product_entry(lm):
            lm += "Category: "
            lm += select(["Electronics", "Books", "Food"], name="category")
            lm += " | Item: "
            lm += gen(name="item", max_tokens=20, regex=r"[A-Za-z0-9 ]+")
            return lm

        result = cfg_generate(product_entry, "Create a product entry")
        # {"category": "Electronics", "item": "Laptop Pro 15"}
    """
    _check_available()
    from guidance import assistant, system, user

    if model is None:
        model = get_guidance_model(temperature=temperature)

    lm = model

    if system_prompt:
        with system():
            lm += system_prompt

    with user():
        lm += prompt

    with assistant():
        lm += grammar_fn(**grammar_kwargs)

    # Extract captures
    if capture_names is not None:
        return {name: lm[name] for name in capture_names}

    # Auto-extract all string-valued captures
    result: dict[str, str] = {}
    try:
        for key in lm.variables():
            val = lm[key]
            if isinstance(val, str):
                result[key] = val
    except (AttributeError, TypeError):
        result["output"] = str(lm)

    return result


def build_cfg_grammar(
    steps: list[dict[str, Any]],
) -> Any:
    """Build a ``@guidance(stateless=True)`` grammar from a list of primitive steps.

    This is a declarative builder -- compose complex CFG grammars without
    writing ``@guidance`` functions yourself.  Token fast-forwarding is
    automatic on literal text and deterministic constraints.

    Supported step types:

    - ``{"type": "literal", "text": "..."}`` -- insert literal text
    - ``{"type": "gen", "name": "...", "max_tokens": N, "regex": "..."}``
    - ``{"type": "select", "name": "...", "options": [...]}``
    - ``{"type": "one_or_more", "body": <step or list of steps>}``
    - ``{"type": "capture", "name": "...", "body": <step or list of steps>}``
    - ``{"type": "with_temperature", "temperature": float, "body": <step or list>}``

    Args:
        steps: List of step dicts defining the grammar.

    Returns:
        A ``@guidance(stateless=True)`` decorated function ready for
        :func:`cfg_generate` or :func:`grammar_generate`.

    Example::

        grammar = build_cfg_grammar([
            {"type": "literal", "text": "Name: "},
            {"type": "gen", "name": "name", "max_tokens": 20, "regex": r"[A-Za-z ]+"},
            {"type": "literal", "text": "\\nRole: "},
            {"type": "select", "name": "role", "options": ["engineer", "designer"]},
        ])
        result = cfg_generate(grammar, "Create a team member entry")
        # {"name": "Alice Johnson", "role": "engineer"}
    """
    _check_available()
    from guidance import guidance as _guidance

    @_guidance(stateless=True)
    def _built_grammar(lm):
        lm = _apply_steps(lm, steps)
        return lm

    return _built_grammar


def _apply_steps(lm, steps: list[dict[str, Any]]):
    """Recursively apply a list of grammar steps to the model.

    Internal helper -- not part of the public API.
    """
    from guidance import gen, select
    from guidance import guidance as _guidance

    for step in steps:
        step_type = step["type"]

        if step_type == "literal":
            lm += step["text"]

        elif step_type == "gen":
            kwargs: dict[str, Any] = {}
            if "name" in step:
                kwargs["name"] = step["name"]
            if "max_tokens" in step:
                kwargs["max_tokens"] = step["max_tokens"]
            if "regex" in step:
                kwargs["regex"] = step["regex"]
            lm += gen(**kwargs)

        elif step_type == "select":
            lm += select(step["options"], name=step.get("name"))

        elif step_type == "one_or_more":
            from guidance.library import one_or_more

            body = step["body"]
            body_list = body if isinstance(body, list) else [body]

            @_guidance(stateless=True)
            def _one_or_more_body(lm, _steps=body_list):
                lm = _apply_steps(lm, _steps)
                return lm

            lm += one_or_more(_one_or_more_body())

        elif step_type == "capture":
            from guidance.library import capture

            body = step["body"]
            body_list = body if isinstance(body, list) else [body]

            @_guidance(stateless=True)
            def _capture_body(lm, _steps=body_list):
                lm = _apply_steps(lm, _steps)
                return lm

            lm += capture(_capture_body(), name=step["name"])

        elif step_type == "with_temperature":
            from guidance.library import with_temperature

            body = step["body"]
            body_list = body if isinstance(body, list) else [body]

            @_guidance(stateless=True)
            def _temp_body(lm, _steps=body_list):
                lm = _apply_steps(lm, _steps)
                return lm

            lm += with_temperature(_temp_body(), temperature=step["temperature"])

        else:
            raise ValueError(f"Unknown grammar step type: {step_type!r}")

    return lm
