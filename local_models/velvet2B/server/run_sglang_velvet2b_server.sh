#!/bin/bash

# ==============================================================================
# SCRIPT DI AVVIO SERVER SGLANG - MODELLO VELVET-2B
# ==============================================================================

# 1. CONFIGURAZIONE VARIABILI (Senza spazi prima e dopo =)
recipe="001_s_09_5"
ckpt="ba53454"
ckpt_path="/nfs/training-output/velvet-cycle2/Velvet-2B-1.5/l06_f5/$recipe/$ckpt"
name="Velvet-2B-1.5_ba53454_t0" 
PORT=8002  # Cambia porta se vuoi far girare vLLM e SGLang contemporaneamente

MEM_FRACTION=0.85

# Lunghezza massima della sequenza (Prompt 2000 + Generazione 2000)
CONTEXT_LEN=4096

echo "----------------------------------------------------------------"
echo "Avvio Server SGLang..."
echo "CKP Modello: $ckpt_path"
echo "Porta: $PORT"
echo "GPU Memory Fraction: $MEM_FRACTION"
echo "Suggested MODEL_ID for clients: $name (sync this with inference_config.yml MODEL_ID)"
echo "----------------------------------------------------------------"

# 3. LANCIO DEL SERVER
# Spiegazione flag:
# --kv-cache-dtype fp8: Fondamentale per raddoppiare la densità della cache.
# --enable-prefix-caching: Abilita il Radix Tree per saltare il prefill su prompt duplicati.
# --mem-fraction-static: Forza SGLang a prendersi quasi tutta la memoria subito.

#sglang serve alternativa come comando diretto (senza python):
# python3 -m sglang.launch_server \
sudo docker run \
    --runtime nvidia \
    --gpus all \
    -v "$ckpt_path":"$ckpt_path" \
    -p $PORT:$PORT \
    --ipc=host \
    --shm-size 16g \
    lmsysorg/sglang:latest \
    sglang serve \
        --model-path "$ckpt_path" \
        --served-model-name "$name" \
        --host 0.0.0.0 \
        --port $PORT \
        --mem-fraction-static $MEM_FRACTION \
        --context-length $CONTEXT_LEN \
        --kv-cache-dtype fp8_e4m3 \
        --log-level info \
        --trust-remote-code


# NOTA: Se riscontri errori di memoria CUDA Graphs all'avvio, 
# aggiungi il flag --enforce-eager alla fine del comando sopra.