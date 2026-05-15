from decimal import Decimal
from uuid import UUID
import datetime
import numpy as np
import pandas as pd
import logging
logger = logging.getLogger(__name__)


def json_ts_serial(obj):
    if isinstance(obj, (pd.Timestamp, pd.DatetimeIndex)):
        return obj.isoformat()
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def convert_to_serializable(obj):
    """
    Converte oggetti non serializzabili in formato JSON-serializzabile.
    Versione specifica per il tuo schema JSON.
    """
    # Gestione None
    if obj is None:
        return None
    
    # Gestione tipi base Python
    if isinstance(obj, (str, int, float, bool)):
        return obj
    
    # Gestione tipi NumPy
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.generic):
        if isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            val = obj.item()
            return None if np.isnan(val) else val
        return obj.item()
    
    # Gestione NaN
    if isinstance(obj, float) and np.isnan(obj):
        return None
    
    # Gestione Decimal
    if isinstance(obj, Decimal):
        return float(obj)
    
    # Gestione UUID
    if isinstance(obj, UUID):
        return str(obj)

    # Gestione date
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    
    # Gestione liste (CRITICO: gestire le liste di dizionari per messages)
    if isinstance(obj, list):
        try:
            # Per liste di dizionari (come messages), processa ricorsivamente
            return [convert_to_serializable(item) for item in obj]
        except:
            # Se fallisce, prova a convertire in stringa
            return str(obj)
    
    # Gestione dizionari
    if isinstance(obj, dict):
        try:
            # Processa ricorsivamente i dizionari
            return {str(k): convert_to_serializable(v) for k, v in obj.items()}
        except:
            return str(obj)
    
    # Gestione pandas Series
    if isinstance(obj, pd.Series):
        try:
            return obj.to_dict()
        except:
            return str(obj)
    
    # Gestione pandas DataFrame
    if isinstance(obj, pd.DataFrame):
        try:
            return obj.to_dict(orient='records')
        except:
            return str(obj)
    
    # Ultima risorsa
    try:
        return str(obj)
    except:
        return None

def process_record_for_json(record, depth=0, max_depth=5): # Max depth 5 è più che sufficiente
    if depth > max_depth:
        return str(record)[:1000] # Tronchiamo stringhe enormi in profondità

    try:
        if record is None: return None
        if isinstance(record, (str, int, float, bool)):
            if isinstance(record, float) and (np.isnan(record) or np.isinf(record)):
                return None
            return record
        
        if isinstance(record, dict):
            # Usiamo un dizionario nuovo per evitare modifiche in place
            return {str(k): process_record_for_json(v, depth + 1) for k, v in record.items()}
        
        if isinstance(record, (list, tuple, set, np.ndarray)):
            items = record.tolist() if hasattr(record, 'tolist') else record
            return [process_record_for_json(i, depth + 1) for i in items]

        # Per Pandas, gestiamo solo se siamo in superficie
        if 'pandas' in str(type(record)) and depth == 0:
            if hasattr(record, 'to_dict'):
                return process_record_for_json(record.to_dict(), depth + 1)

        if isinstance(record, (datetime.datetime, datetime.date)):
            return record.isoformat()
        
        return str(record)
    except:
        return str(record) # Fallback atomico: nessuna ricorsione qui.

def fallback_convert_record(record):
    """
    Conversione di fallback migliorata per record problematici.
    """
    try:
        if record is None:
            return None
            
        if isinstance(record, dict):
            result = {}
            for k, v in record.items():
                try:
                    # Prova la conversione normale
                    result[str(k)] = process_record_for_json(v)
                except Exception as e:
                    # Se fallisce, prova con str
                    try:
                        result[str(k)] = str(v)
                    except:
                        result[str(k)] = f"<unserializable: {type(v).__name__}>"
            return result
            
        elif isinstance(record, (list, tuple)):
            result = []
            for item in record:
                try:
                    result.append(process_record_for_json(item))
                except:
                    try:
                        result.append(str(item))
                    except:
                        result.append(f"<unserializable: {type(item).__name__}>")
            return result if not isinstance(record, tuple) else tuple(result)
            
        elif isinstance(record, np.ndarray):
            # Fallback specifico per array numpy
            try:
                return [fallback_convert_record(item) for item in record.tolist()]
            except:
                return str(record)
                
        else:
            # Per qualsiasi altro tipo, prova str
            try:
                return str(record)
            except:
                return f"<unserializable: {type(record).__name__}>"
                
    except Exception as e:
        # Se tutto fallisce, restituisci un messaggio di errore
        logger.error(f"[fallback_convert_record] Critical error: {e}")
        return f"<critical error in serialization: {type(record).__name__}>"
    
def fallback_convert_record(record):
    """
    Conversione di fallback per record problematici.
    """
    if isinstance(record, dict):
        result = {}
        for k, v in record.items():
            try:
                # Prova la conversione normale
                result[str(k)] = process_record_for_json(v)
            except:
                # Se fallisce, converto a stringa
                try:
                    result[str(k)] = str(v)
                except:
                    result[str(k)] = None
        return result
    else:
        # Se non è un dict, prova a convertirlo
        try:
            return str(record)
        except:
            return None
