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

def process_record_for_json(record):
    """
    Processa ricorsivamente un record per la serializzazione JSON.
    Versione migliorata con gestione corretta di numpy array e NaN.
    """
    try:
        # Gestione None
        if record is None:
            return None
            
        # Tipi base Python (già serializzabili)
        if isinstance(record, (str, int, float, bool)):
            return record
        
        # Dizionari
        if isinstance(record, dict):
            return {str(k): process_record_for_json(v) for k, v in record.items()}
        
        # Liste e tuple
        if isinstance(record, (list, tuple)):
            # IMPORTANTE: non usare type(record) per mantenere il tipo originale
            if isinstance(record, tuple):
                return tuple(process_record_for_json(item) for item in record)
            return [process_record_for_json(item) for item in record]
        
        # Set
        if isinstance(record, set):
            return [process_record_for_json(item) for item in record]
        
        # NaN check - deve essere PRIMA dei controlli numpy per evitare problemi
        try:
            if pd.isna(record):
                return None
        except Exception:
            # Se pd.isna fallisce (es. con numpy array), continuiamo
            pass
        
        # NumPy array - questo DEVE venire prima dei controlli sui singoli numeri
        if isinstance(record, np.ndarray):
            # Se è un array, convertiamo in lista e processiamo ricorsivamente
            return [process_record_for_json(item) for item in record.tolist()]
        
        # NumPy scalars
        if isinstance(record, np.integer):
            return int(record)
        if isinstance(record, np.floating):
            try:
                if np.isnan(record):
                    return None
                return float(record)
            except TypeError:
                # Se np.isnan fallisce, proviamo una conversione diretta
                return float(record) if not np.isnan(float(record)) else None
        if isinstance(record, np.bool_):
            return bool(record)
        if isinstance(record, np.generic):
            # Altri tipi numpy generici
            try:
                return process_record_for_json(record.item())
            except:
                return str(record)
        
        # Pandas Series
        if isinstance(record, pd.Series):
            return process_record_for_json(record.to_dict())
        
        # Pandas DataFrame
        if isinstance(record, pd.DataFrame):
            return process_record_for_json(record.to_dict(orient='records'))
        
        # UUID
        if isinstance(record, UUID):
            return str(record)

        # Date e datetime
        if isinstance(record, (datetime.datetime, datetime.date)):
            return record.isoformat()
        
        # Decimal
        if isinstance(record, Decimal):
            return float(record)
        
        # Oggetti con __dict__
        if hasattr(record, '__dict__'):
            # Proviamo a serializzare il dizionario, altrimenti usiamo str
            try:
                return process_record_for_json(record.__dict__)
            except:
                return str(record)
        
        # Per qualsiasi altro tipo, proviamo str come fallback
        return str(record)
        
    except Exception as e:
        logger.error(f"[serializer.process_record_for_json] Error processing record: {record}, error: {e}")
        return fallback_convert_record(record)

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
