"""Guidance structured generation toolkit.

Provides constrained text generation for LangGraph agents using the
guidance-ai library.  Forces LLM outputs to match JSON schemas, regex
patterns, or fixed option sets.  All LLM calls route through the
project's LiteLLM proxy.

Quick start::

    from src.shared.guidance_toolkit import structured_json, get_guidance_tools

    # As a Python function
    from pydantic import BaseModel

    class Person(BaseModel):
        name: str
        age: int

    result = structured_json(Person, "Extract: John is 30 years old")

    # As LangGraph tools
    tools = get_guidance_tools()
    agent = create_react_agent(get_llm(), tools)

    # As a LangGraph node
    builder.add_node("extract", create_guidance_structured_node(Person))

Dependencies:
    Requires ``pip install -e '.[guidance]'``.  All imports are lazy --
    ``ImportError`` is raised only when a function is actually called.
"""

from src.shared.guidance_toolkit.config import GuidanceSettings, setup_guidance

__all__ = [
    # Config
    "GuidanceSettings",
    "setup_guidance",
    "get_settings",
    # LLM bridge
    "get_guidance_model",
    "create_guidance_model",
    # Programs
    "structured_json",
    "constrained_select",
    "regex_generate",
    "grammar_generate",
    "cfg_generate",
    "build_cfg_grammar",
    # Tools
    "get_guidance_tools",
    # Nodes
    "create_guidance_structured_node",
    "create_guidance_select_node",
]


# ── Factory: Config ──────────────────────────────────────────────────


def get_settings():
    """Return the active ``GuidanceSettings``."""
    from src.shared.guidance_toolkit.config import get_settings as _fn

    return _fn()


# ── Lazy re-exports: LLM bridge ─────────────────────────────────────


def get_guidance_model(model=None, temperature=None):
    """Return a guidance ``OpenAI`` model pointed at the LiteLLM proxy."""
    from src.shared.guidance_toolkit.llm_bridge import get_guidance_model as _fn

    return _fn(model=model, temperature=temperature)


def create_guidance_model(model=None, temperature=None, **kwargs):
    """Create a guidance ``OpenAI`` model with custom kwargs (uncached)."""
    from src.shared.guidance_toolkit.llm_bridge import create_guidance_model as _fn

    return _fn(model=model, temperature=temperature, **kwargs)


# ── Lazy re-exports: Programs ────────────────────────────────────────


def structured_json(schema, prompt, **kwargs):
    """Generate JSON constrained to a Pydantic schema."""
    from src.shared.guidance_toolkit.programs import structured_json as _fn

    return _fn(schema, prompt, **kwargs)


def constrained_select(options, prompt, **kwargs):
    """Force LLM to select one option from a list."""
    from src.shared.guidance_toolkit.programs import constrained_select as _fn

    return _fn(options, prompt, **kwargs)


def regex_generate(pattern, prompt, **kwargs):
    """Generate text matching a regex pattern."""
    from src.shared.guidance_toolkit.programs import regex_generate as _fn

    return _fn(pattern, prompt, **kwargs)


def grammar_generate(grammar_fn, prompt, **kwargs):
    """Generate text using a custom @guidance grammar."""
    from src.shared.guidance_toolkit.programs import grammar_generate as _fn

    return _fn(grammar_fn, prompt, **kwargs)


def cfg_generate(grammar_fn, prompt, **kwargs):
    """Execute a @guidance(stateless=True) CFG grammar and return all captures."""
    from src.shared.guidance_toolkit.programs import cfg_generate as _fn

    return _fn(grammar_fn, prompt, **kwargs)


def build_cfg_grammar(steps):
    """Build a @guidance(stateless=True) grammar from a list of primitive steps."""
    from src.shared.guidance_toolkit.programs import build_cfg_grammar as _fn

    return _fn(steps)


# ── Lazy re-exports: Tools ───────────────────────────────────────────


def get_guidance_tools(settings=None):
    """Return ``[guidance_json_generate, guidance_select, guidance_regex_generate]`` tools."""
    from src.shared.guidance_toolkit.tools import get_guidance_tools as _fn

    return _fn(settings=settings)


# ── Lazy re-exports: Nodes ───────────────────────────────────────────


def create_guidance_structured_node(schema, **kwargs):
    """Create a node that generates structured JSON."""
    from src.shared.guidance_toolkit.nodes import create_guidance_structured_node as _fn

    return _fn(schema, **kwargs)


def create_guidance_select_node(options, **kwargs):
    """Create a node that selects from fixed options."""
    from src.shared.guidance_toolkit.nodes import create_guidance_select_node as _fn

    return _fn(options, **kwargs)
