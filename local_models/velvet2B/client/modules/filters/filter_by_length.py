import json
from pathlib import Path
import logging
logger = logging.getLogger(__name__)

def filter_by_length(ds, FILTERED_DATA_PATH, MAX_PAIR_CHARS=20000):
    """Filtra il dataset escludendo i campioni dove QUALSIASI coppia supera MAX_PAIR_CHARS."""
    out_path = Path(FILTERED_DATA_PATH)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Apriamo in modalità append
        with out_path.open("a", encoding="utf-8") as f:
            scartati = 0
            
            def check_and_log(x):
                nonlocal scartati
                p = x.get("prompt") or ""
                c = x.get("chosen") or ""
                r = x.get("rejected") or ""
                
                len_chosen_pair = len(p) + len(c)
                len_rejected_pair = len(p) + len(r)
                
                # CORREZIONE LOGICA: Entrambe le coppie DEVONO essere sotto il limite
                if (len_chosen_pair < MAX_PAIR_CHARS) and (len_rejected_pair < MAX_PAIR_CHARS):
                    return True
                
                # Se una delle due (o entrambe) supera il limite, viene scartata ed entra qui
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
                logger.warning(
                    "Scartato -> _id_hash=%s | Chars(P+C): %d, Chars(P+R): %d", 
                    x.get("_id_hash", ""), len_chosen_pair, len_rejected_pair
                )
                scartati += 1
                return False

            # Applica il filtro sul dataset di Hugging Face
            kept_ds = ds.filter(check_and_log, batched=False)
            
        logger.info(f"Filtro completato. Scartati {scartati} campioni su {len(kept_ds) + scartati} totali.")
        return kept_ds

    except Exception:
        logger.exception("Impossibile applicare il filtro di lunghezza al dataset; proseguo senza filtraggio.")
        return ds   
