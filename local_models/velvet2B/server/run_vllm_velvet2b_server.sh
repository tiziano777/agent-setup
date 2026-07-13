#!/bin/bash

# 1. CONFIGURAZIONE VARIABILI (Senza spazi prima e dopo =)
ckpt_path="/nfs/training-output/velvet-cycle2/Velvet-2B-1.5/l06_f5/001_s_09_6/ba35217"
name="Velvet-2B-1.5_ba53454_t0" 

echo "----------------------------------------------------------------"
echo "Avvio vLLM Docker Server..."
echo "Model Path: $ckpt_path"
echo "Served Name: $name"
echo "----------------------------------------------------------------"

# 2. LANCIO DOCKER
# Nota: Ho aggiunto --shm-size per evitare crash di memoria condivisa comuni in vLLM
sudo docker run \
    --runtime nvidia \
    --gpus all \
    -v "$ckpt_path":"$ckpt_path" \
    -p 8001:8001 \
    --ipc=host \
    --shm-size 16g \
    --restart unless-stopped \
    vllm/vllm-openai:v0.10.2 \
    --model "$ckpt_path" \
    --served-model-name "$name" \
    --port 8001 \
    --gpu-memory-utilization 0.85 \
    --max-model-len 4096 \
    --max-num-seqs 256 \
    --trust-remote-code  # Spesso necessario per modelli custom/nuovi