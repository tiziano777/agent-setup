from __future__ import annotations 

"""Chat template function for chat_type: context_train_dpo.

Extends the instruct DPO template by appending context documents to the
user content. Each element in the sample's context list is appended as:

    \nDocuments:\n<doc_1>\n\nDocuments:\n<doc_2>\n...

This injects retrieval context directly into the user turn so the model
learns to ground its answers on provided documents.

Expected input schema: input_schema.json (same as train_dpo)
  - messages[].context may be:
    - A string (single doc or JSON-serialized list like "[\"str1\",\"str2\"]")
    - A list of strings
    - None (no context)
"""
 
import logging

logger = logging.getLogger(__name__)

import re

def _build_context_suffix(context) -> str:
    """Format context documents as a suffix string for user content.

    Args:
        context: Single document string (including JSON-serialized lists),
                 a list of document strings, or None.

    Returns:
        Formatted suffix string, empty if no context provided.
    """
    if not context:
        return ""

    # Caso 1: L'input è una lista
    if isinstance(context, list):
        res = "Documents:\n"
        for i, doc in enumerate(context):
            res += str(doc)
            # Aggiungiamo il newline solo se non è l'ultimo elemento
            if i < len(context) - 1:
                res += "\n"
        return res

    # Caso 2: L'input è una stringa
    if isinstance(context, str):
        context = context.strip()
        
        # Verifica se la stringa è una lista serializzata (inizia con [ e finisce con ])
        if context.startswith("[") and context.endswith("]"):
            # Rimuoviamo le parentesi quadre esterne
            content = context[1:-1]
            
            # Sostituiamo la prima parte con il template richiesto
            # Usiamo regex per trovare la virgola tra doppi apici: "," 
            # Il pattern cerca: " seguito da , seguito da "
            formatted_content = re.sub(r'","', '\n', content)
            
            # Rimuoviamo eventuali doppi apici rimasti all'inizio e alla fine del contenuto
            if formatted_content.startswith('"') and formatted_content.endswith('"'):
                formatted_content = formatted_content[1:-1]
            
            return f"Documents:\n{formatted_content}"
        
        # Se è una stringa semplice ma non una lista serializzata
        return f"Documents:\n{context}"

    return ""


def apply_chat_template(
    sample: dict,
    system_prompt: str | None
    ) -> list[dict]:
    """Extract messages from a DPO sample, appending context to user content.

    Args:
        sample:        Raw sample dict following input_schema.json.
        system_prompt: System prompt content from the recipe. Injected as
                       the first system message if provided.

    Returns:
        List of {"role": ..., "content": ...} dicts ready for the chat
        completions API. User content includes appended context documents.

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
            # Append context documents to user content
            context = msg.get("context")
            content += _build_context_suffix(context)
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

