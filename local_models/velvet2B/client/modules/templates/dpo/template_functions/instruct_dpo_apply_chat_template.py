"""Chat template function for chat_type: train_dpo.

Scope: extract and normalize fields from a DPO input sample into the
standard role/content messages list consumed by the chat completions API.
The server applies its own tokenizer template — no manual formatting here.

Expected input schema: input_schema.json
  - messages: list of {role: USER|ASSISTANT, ...}
      USER turn:      {role: USER, content: str}
      ASSISTANT turn: {role: ASSISTANT, positives: [...], negatives: [...]}
                      OR {role: ASSISTANT, content: str}  ← completed turn (multi-turn)

The ASSISTANT turn being generated has no `content` and is excluded.
Previous completed ASSISTANT turns are included as context (multi-turn).

Note: _id_hash and system_prompt_id are metadata tracked by the client —
this function does not embed them in the output.
"""

from __future__ import annotations


def apply_chat_template(
    sample: dict,
    system_prompt: str | None
    ) -> list[dict]:
    """Extract messages from a DPO sample into standard role/content format.

    Args:
        sample:           Raw sample dict following input_schema.json.
        system_prompt:    System prompt content from the recipe. Injected as
                          the first system message if provided.

    Returns:
        List of {"role": ..., "content": ...} dicts ready for the chat
        completions API. Roles are lowercased ("system", "user", "assistant").

    Raises:
        ValueError: if messages are missing, malformed, or the last usable
                    turn is not a user turn.
    """
    id_hash: str = sample.get("_id_hash", "<unknown>")
    raw_messages: list[dict] = sample.get("messages", [])

    if not raw_messages:
        raise ValueError(f"Sample {id_hash}: 'messages' field is missing or empty.")

    result: list[dict] = []

    # Inject system prompt as the first message if provided
    if system_prompt:
        result.append({"role": "system", "content": system_prompt})

    for msg in raw_messages:
        role: str = (msg.get("role") or "").upper()

        if role == "USER":
            content = msg.get("content", "")
            if not content:
                raise ValueError(
                    f"Sample {id_hash}: USER message has empty 'content'."
                )
            result.append({"role": "user", "content": content})

        elif role == "ASSISTANT":
            content = msg.get("content")
            if content:
                # Completed ASSISTANT turn — include as context (multi-turn)
                result.append({"role": "assistant", "content": content})
            # No content → generation target turn, intentionally excluded

        else:
            raise ValueError(
                f"Sample {id_hash}: unexpected role '{role}'. "
                f"Expected USER or ASSISTANT."
            )

    # The last non-system message must be a user turn for generation to make sense
    non_system = [m for m in result if m["role"] != "system"]
    if not non_system:
        raise ValueError(f"Sample {id_hash}: no user/assistant turns found.")
    if non_system[-1]["role"] != "user":
        raise ValueError(
            f"Sample {id_hash}: last message must be a user turn. "
            f"Got: '{non_system[-1]['role']}'."
        )

    return result
