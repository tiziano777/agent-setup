#!/bin/bash

# 1. CONFIGURAZIONE VARIABILI
# Assicurati che il mount NFS sia mappato correttamente su questa cartella locale
ckpt_path="/nfs/training-output/qwen3_32B"
name="qwen3-32b"

echo "----------------------------------------------------------------"
echo "Avvio vLLM Docker Server per Qwen3-32B (Precisione Massima)"
echo "Local Path: $ckpt_path"
echo "Served Name: $name"
echo "----------------------------------------------------------------"

# 2. LANCIO DOCKER
# Usiamo l'ultima versione di vLLM che ha il supporto ottimizzato per Qwen3
sudo docker run \
    --runtime nvidia \
    --gpus all \
    -v "$ckpt_path":"$ckpt_path" \
    -p 8001:8001 \
    --ipc=host \
    --shm-size 32g \
    --restart unless-stopped \
    vllm/vllm-openai:latest \
    --model "$ckpt_path" \
    --served-model-name "$name" \
    --port 8001 \
    --dtype bfloat16 \
    --trust-remote-code \
    --gpu-memory-utilization 0.95 \
    --max-model-len 6144 \
    --reasoning-parser qwen3