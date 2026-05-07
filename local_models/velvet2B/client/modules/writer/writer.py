import json
import os
import glob

class RollingJsonlWriter:
    """Gestisce la scrittura di file JSONL rotativi basati sulla dimensione."""
    def __init__(self, directory, base_name, max_mb):
        self.directory = directory
        self.base_name = base_name
        self.max_bytes = max_mb * 1024 * 1024
        self.current_part = 0
        self.current_file = None
        
        if not os.path.exists(directory):
            os.makedirs(directory)
        self._open_next_part()

    def _open_next_part(self):
        # Cerca l'ultima parte esistente per gestire il riavvio (checkpoint)
        existing_parts = glob.glob(f"{self.directory}/{self.base_name}_part*.jsonl")
        if existing_parts and self.current_part == 0:
            self.current_part = max([int(p.split('_part')[-1].split('.')[0]) for p in existing_parts])
        else:
            self.current_part += 1
            
        if self.current_file:
            self.current_file.close()
            
        path = f"{self.directory}/{self.base_name}_part{self.current_part}.jsonl"
        self.current_file = open(path, "a")
        self.current_path = path

    def write(self, data):
        line = json.dumps(data) + "\n"
        # Se il file supera la soglia, passiamo al prossimo
        if os.path.exists(self.current_path) and os.path.getsize(self.current_path) > self.max_bytes:
            self._open_next_part()
        
        self.current_file.write(line)
        self.current_file.flush()

    def close(self):
        if self.current_file:
            self.current_file.close()

