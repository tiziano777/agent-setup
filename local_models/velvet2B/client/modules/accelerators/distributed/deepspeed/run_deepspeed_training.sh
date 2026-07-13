#!/bin/bash

# 1. Spostati nella cartella radice del progetto
cd "$HOME/dpo-setup" || exit

# 2. Carica configurazione DeepSpeed (o usa defaults)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env.deepspeed"

if [[ -f "$ENV_FILE" ]]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

# --- FIX NCCL ---
# Riscriviamo la variabile ignorando br01 se non esiste, 
# oppure forziamo il fallback sicuro in ogni caso.
export NCCL_SOCKET_IFNAME="lo,eth0,en,ens,bond"
export NCCL_DEBUG="INFO" # Cambiato temporaneamente a INFO per fare debug se fallisce ancora

# --- FIX CUDA ALLOCATOR ---
# Visto che i tuoi log dicevano che expandable_segments non è supportato sulla tua piattaforma,
# lo commentiamo o rimuoviamo per evitare warning fastidiosi.
# export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"

export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export TOKENIZERS_PARALLELISM="${TOKENIZERS_PARALLELISM:-false}"

# 4. Carica parametri accelerate (con defaults)
NUM_PROCESSES="${NUM_PROCESSES:-1}"
NUM_MACHINES="${NUM_MACHINES:-1}"
DYNAMO_BACKEND="${DYNAMO_BACKEND:-no}"
MIXED_PRECISION="${MIXED_PRECISION:-bf16}"
USE_DEEPSPEED="${USE_DEEPSPEED:-true}"
TRAIN_CONFIG="${TRAIN_CONFIG:-config.yml}"

# 5. Lancio tramite HF Accelerate
accelerate launch \
    --num_processes="$NUM_PROCESSES" \
    --num_machines="$NUM_MACHINES" \
    --dynamo_backend="$DYNAMO_BACKEND" \
    --mixed_precision="$MIXED_PRECISION" \
    $([ "$USE_DEEPSPEED" = "true" ] && echo "--use_deepspeed") \
    "train.py" --config "$TRAIN_CONFIG"

echo "Training completato!"