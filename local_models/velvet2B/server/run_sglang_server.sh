#!/bin/bash

# ==============================================================================
# SCRIPT DI AVVIO SERVER SGLANG - MODELLO VELVET-2B
# ==============================================================================

# 1. CONFIGURAZIONE PERCORSI E PORTA
# Modifica MODEL_PATH con il percorso reale dove hai scaricato Velvet-2B
MODEL_PATH="/nfs/training-output/velvet-cycle2/Velvet-2B-1.5/ckpt_2B_v2/huggingface/ba34086"
# Derive a model id from the model path basename so clients can reference it
MODEL_NAME=$(basename "$MODEL_PATH")
MODEL_ID="$MODEL_NAME"
PORT=30000

# 2. PARAMETRI DI OTTIMIZZAZIONE GPU
# Allochiamo il 95% della VRAM (circa 76GB su 80GB)
MEM_FRACTION=0.95

# Lunghezza massima della sequenza (Prompt 2000 + Generazione 2000)
CONTEXT_LEN=4096

echo "----------------------------------------------------------------"
echo "Avvio Server SGLang..."
echo "Modello: $MODEL_PATH"
echo "Porta: $PORT"
echo "GPU Memory Fraction: $MEM_FRACTION"
echo "Suggested MODEL_ID for clients: $MODEL_ID (sync this with inference_config.yml MODEL_ID)"
echo "----------------------------------------------------------------"

# 3. LANCIO DEL SERVER
# Spiegazione flag:
# --kv-cache-dtype fp8: Fondamentale per raddoppiare la densità della cache.
# --enable-prefix-caching: Abilita il Radix Tree per saltare il prefill su prompt duplicati.
# --mem-fraction-static: Forza SGLang a prendersi quasi tutta la memoria subito.

python -m sglang.launch_server \
    --model-path "$MODEL_PATH" \
    --host 0.0.0.0 \
    --port $PORT \
    --mem-fraction-static $MEM_FRACTION \
    --context-length $CONTEXT_LEN \
    --kv-cache-dtype fp8 \
    --enable-prefix-caching \
    --log-level-http info

# NOTA: Se riscontri errori di memoria CUDA Graphs all'avvio, 
# aggiungi il flag --enforce-eager alla fine del comando sopra.