"""Chat template function for chat_type: context_train_dpo.

Variante di apply_chat_template che inietta i documenti recuperati e la query
dell'utente all'interno di un template di system_prompt (placeholder
{retrieved_docs} e {query}), applicato a OGNI turno USER della conversazione
(non solo all'ultimo), per supportare correttamente il caso multi-turn.

Il contesto documentale si trova in messages[0]["context"] ed è condiviso
per tutti i turni USER del sample.

Il resto della logica (selezione chosen/rejected per temperatura, hard
negative filtering) rimane invariato rispetto alla funzione originale.
"""

from __future__ import annotations

from modules.filters.hard_negative_filtering import HardNegativeFilter


def _select_by_temperature(items: list[dict], temperature: float) -> dict:
    """Pick the inference_item whose inference_params.temperature matches."""
    for item in items:
        params = item.get("inference_params") or {}
        if params.get("temperature") == temperature:
            return item
    # Fallback: first item
    return items[0] if items else {}


def _extract_content(item: dict) -> str:
    """Get displayable content from an inference_item."""
    return item.get("content") or ""


def apply_chat_template(
    sample: dict,
    system_prompt: str | None,
    temperature: float = 0.3,
    hn_filter: HardNegativeFilter | None = None
) -> dict | None:
    """Convert a raw RAG-DPO sample into DPOTrainer-compatible format.

    A differenza della versione base, il system_prompt viene trattato come
    template contenente i placeholder {retrieved_docs} e {query}. Il testo
    risultante dal `.format()` sostituisce il contenuto di OGNI turno USER
    della conversazione (retrieved_docs è condiviso, query è il contenuto
    originale di quel singolo turno). Non viene aggiunto alcun messaggio
    "system" separato.

    Args:
        sample:        Raw sample dict following input_schema.json.
                        messages[0] deve contenere il campo "context" con i
                        documenti recuperati (retrieved_docs).
        system_prompt: Template con placeholder {retrieved_docs} e {query}.
        temperature:   Select positive/negative by this temperature value.
        hn_filter:     Optional HardNegativeFilter for NLP-based rejected selection.

    Returns:
        {"prompt": [...], "chosen": [...], "rejected": [...]}
        Each is a list of {"role": str, "content": str} message dicts.
        Returns None if the sample should be dropped (hard negative filter decision).

    Raises:
        ValueError: on missing/malformed data.
    """
    id_hash: str = sample.get("_id_hash", "<unknown>")
    raw_messages = sample.get("messages", [])
    metadata: dict = {k: sample[k] for k in sample if k.startswith("_")}

    # Be explicit about emptiness checks: samples may contain numpy arrays or
    # pandas Series where truthiness raises ValueError. Use len() when available.
    if raw_messages is None:
        raise ValueError(f"Sample {id_hash}: 'messages' is missing or empty.")
    if hasattr(raw_messages, "__len__"):
        if len(raw_messages) == 0:
            raise ValueError(f"Sample {id_hash}: 'messages' is missing or empty.")
    else:
        # Non-iterable / unexpected type
        raise ValueError(f"Sample {id_hash}: 'messages' is not an iterable of messages.")

    # retrieved_docs vive in messages[0].context
    retrieved_docs = raw_messages[0].get("context") if hasattr(raw_messages[0], "get") else None
    if not retrieved_docs:
        raise ValueError(f"Sample {id_hash}: 'messages[0].context' is missing or empty.")

    if not system_prompt or "{retrieved_docs}" not in system_prompt or "{query}" not in system_prompt:
        raise ValueError(
            f"Sample {id_hash}: system_prompt must be a template containing "
            "'{retrieved_docs}' and '{query}' placeholders."
        )

    prompt_messages: list[dict] = []

    chosen_content: str | None = None
    rejected_content: str | None = None
    chosen_item: dict = {}
    rejected_item: dict = {}

    for msg in raw_messages:
        role: str = (msg.get("role") or "").upper()

        if role == "USER":
            content = msg.get("content", "")
            if not content:
                raise ValueError(f"Sample {id_hash}: USER message has empty 'content'.")
            templated_content = system_prompt.format(retrieved_docs=retrieved_docs, query=content)
            prompt_messages.append({"role": "user", "content": templated_content})

        elif role == "ASSISTANT":
            # Generation target turn — extract chosen/rejected
            positives = msg.get("positives", [])
            negatives = msg.get("negatives", [])

            if not positives:
                raise ValueError(f"Sample {id_hash}: generation turn has no positives.")
            if not negatives:
                raise ValueError(f"Sample {id_hash}: generation turn has no negatives.")

            chosen_item = _select_by_temperature(positives, temperature)
            chosen_content = _extract_content(chosen_item)

            # Hard negative selection: NLP-based or temperature fallback
            if hn_filter:
                rejected_item = hn_filter.select(
                    negatives,
                    gold_content=chosen_content,
                    temperature=temperature,
                    sample_metadata=metadata
                )
                if rejected_item is None:
                    return None  # signal drop to caller
            else:
                rejected_item = _select_by_temperature(negatives, temperature)

            rejected_content = _extract_content(rejected_item)
        else:
            raise ValueError(f"Sample {id_hash}: unexpected role '{role}'.")

    if chosen_content is None or rejected_content is None:
        raise ValueError(f"Sample {id_hash}: no generation turn with positives/negatives found.")

    # L'ultimo messaggio del prompt deve essere un turno user
    if not prompt_messages or prompt_messages[-1]["role"] != "user":
        raise ValueError(f"Sample {id_hash}: last prompt message must be a user turn.")

    return {
        "prompt": prompt_messages,
        "chosen": [{"role": "assistant", "content": chosen_content}],
        "rejected": [{"role": "assistant", "content": rejected_content}],
        "_eval": {
            "gold": chosen_content,
            "chosen_inference_params": chosen_item.get("inference_params") if chosen_item else None,
            "rejected_inference_params": rejected_item.get("inference_params") if rejected_item else None,
        },
    }