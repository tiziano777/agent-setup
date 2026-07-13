#!/bin/bash

# 1. CONFIGURAZIONE VARIABILI
HOST_CKPT_PATH="/nfs/training-output/velvet-cycle2/Velvet-2B-1.5/l06_f5/001_s_09_6/ba35217"
CONTAINER_CKPT_PATH="/model/velvet-2b"
name="Velvet-2B-1.5_ba53454_t0" 
PORT=8002  
MEM_FRACTION=0.85
CONTEXT_LEN=8096

# Image
#DOCKER_IMAGE="lmsysorg/sglang:latest" 
DOCKER_IMAGE="lmsysorg/sglang:latest-cu129"

echo "----------------------------------------------------------------"
echo "Avvio Server SGLang in CONTAINER DOCKER..."
echo "Host Path Modello: $HOST_CKPT_PATH"
echo "Container Path Modello: $CONTAINER_CKPT_PATH"
echo "Porta Esposta: $PORT"
echo "Suggested MODEL_ID for clients: $name"
echo "----------------------------------------------------------------"

# 2. LANCIO DEL CONTAINER DOCKER
# --gpus all: passa le GPU al container
# --shm-size=16gb: fondamentale per PyTorch/vLLM/SGLang per la memoria condivisa ed evitare crash di Triton
# -v ... : monta la cartella NFS dell'host dentro il container in sola lettura (:ro)
# --ipc=host: ulteriore protezione per la gestione della memoria inter-processo

# Rimuove eventuali container omonimi rimasti appesi
sudo docker rm -f sglang-velvet-2b 2>/dev/null

# 2. LANCIO DEL CONTAINER DOCKER 
sudo docker run -d \
    --name sglang-velvet-2b \
    --gpus all \
    --shm-size=16gb \
    --ipc=host \
    --net=host \
    --ulimit memlock=-1 \
    --ulimit stack=67108864 \
    -v "$HOST_CKPT_PATH":"$CONTAINER_CKPT_PATH":ro \
    $DOCKER_IMAGE \
    python3 -m sglang.launch_server \
        --model-path "$CONTAINER_CKPT_PATH" \
        --served-model-name "$name" \
        --host 0.0.0.0 \
        --port $PORT \
        --mem-fraction-static $MEM_FRACTION \
        --context-length $CONTEXT_LEN \
        --kv-cache-dtype fp8_e4m3 \
        --log-level info \
        --trust-remote-code \
        --schedule-policy lpm \
        --chunked-prefill-size 512

# ==============================================================================
# NOTE DI OTTIMIZZAZIONE PER IL SERVING MASSIVO:
# ==============================================================================
# 1. `--schedule-policy lpm`: Forza l'algoritmo di cache a cercare il prefisso comune più lungo.
#    Se i K prompt hanno istruzioni o contesti identici all'inizio, le prestazioni esplodono.
# 2. `--chunked-prefill-size 512`: Divide il calcolo dei token iniziali in blocchi da 512.
#    Evita l'effetto "collo di bottiglia" quando arrivano contemporaneamente prompt molto lunghi e molto corti.
# 3. `--net=host`: Utilizzato nel comando docker per eliminare l'overhead di rete del bridge di Docker,
#    garantendo la massima velocità di risposta sulle chiamate HTTP/gRPC.
#
# IN CASO DI ERRORI CON I CUDA GRAPHS:
# Se il modello da 2B dovesse fallire l'inizializzazione dei CUDA Graphs a causa delle ottimizzazioni interne,
# aggiungi in coda al comando: --disable-cuda-graph