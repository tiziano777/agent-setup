import json
from pathlib import Path
import logging
logger = logging.getLogger(__name__)


def filter_by_token(ds, tokenizer, FILTERED_DATA_PATH, MAX_PAIR_TOKENS=4096, SYSTEM_TOKENS=1024):
    """Filtra il dataset usando la lunghezza in token; scrive gli scartati su FILE."""
    out_path = Path(FILTERED_DATA_PATH)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with out_path.open("a", encoding="utf-8") as f:
            scartati = 0

            def check_and_log(x):
                nonlocal scartati
                p = x.get("prompt") or ""
                c = x.get("chosen") or ""
                r = x.get("rejected") or ""

                len_chosen_pair = len(tokenizer(p)["input_ids"]) + len(tokenizer(c)["input_ids"]) + SYSTEM_TOKENS
                len_rejected_pair = len(tokenizer(p)["input_ids"]) + len(tokenizer(r)["input_ids"]) + SYSTEM_TOKENS

                if (len_chosen_pair < MAX_PAIR_TOKENS) and (len_rejected_pair < MAX_PAIR_TOKENS):
                    return True

                f.write(json.dumps(x, ensure_ascii=False) + "\n")
                logger.warning(
                    "Scartato -> _id_hash=%s | Tokens(P+C): %d, Tokens(P+R): %d",
                    x.get("_id_hash", ""), len_chosen_pair, len_rejected_pair,
                )
                scartati += 1
                return False

            kept_ds = ds.filter(check_and_log, batched=False)

        logger.info(f"Filtro token completato. Scartati {scartati} campioni su {len(kept_ds) + scartati} totali.")
        return kept_ds

    except Exception:
        logger.exception("Impossibile applicare il filtro di lunghezza in token; proseguo senza filtraggio.")
        return ds
