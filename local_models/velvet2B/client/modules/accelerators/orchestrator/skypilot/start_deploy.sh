#!/bin/bash
# ============================================================
# start_deploy.sh
# Setup completo SkyPilot + K3s + GPU Operator + SSH Node Pool
# Versione migliorata basata su troubleshooting reale
# ============================================================

set -e  # Interrompi in caso di errore

echo "======================================"
echo " SkyPilot Deploy Setup - azure-gpu-cluster"
echo "======================================"

# --------------------------------------------------------------
# 0. PREREQUISITI
# --------------------------------------------------------------
echo "[0/8] Verifica prerequisiti..."

if ! command -v autossh &>/dev/null; then
    echo "Installazione autossh..."
    sudo apt-get install -y autossh
else
    echo "autossh già installato."
fi

# --------------------------------------------------------------
# CRITICO (fix da troubleshooting):
# Sostituisci il symlink kubectl -> k3s con il binario reale.
# Il symlink K3s ignora ~/.kube/config e legge sempre
# /etc/rancher/k3s/k3s.yaml (root-only), causando:
#   "Failed to get kubeconfig text for context ssh-azure-gpu-cluster"
# --------------------------------------------------------------
echo "[0/8] Verifica binario kubectl (fix symlink K3s)..."

if [ -L /usr/local/bin/kubectl ] && \
   [ "$(readlink /usr/local/bin/kubectl)" = "k3s" ]; then
    echo "WARN: kubectl è un symlink a k3s. Installazione binario standalone..."
    sudo rm /usr/local/bin/kubectl

    # Recupera la versione K3s installata per compatibilità
    K3S_VERSION=$(k3s --version | grep -oP 'v\d+\.\d+\.\d+' | head -1)
    echo "Versione K3s rilevata: $K3S_VERSION"

    curl -LO "https://dl.k8s.io/release/${K3S_VERSION}/bin/linux/amd64/kubectl"
    sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
    rm kubectl
    echo "kubectl standalone installato: $(kubectl version --client --short 2>/dev/null || kubectl version --client)"
else
    echo "kubectl standalone già presente."
fi

# --------------------------------------------------------------
# 1. KUBECONFIG - Rendi accessibile il kubeconfig K3s all'utente
# --------------------------------------------------------------
echo "[1/8] Configurazione kubeconfig K3s..."

mkdir -p ~/.kube
sudo k3s kubectl config view --raw | tee ~/.kube/config > /dev/null
chmod 600 ~/.kube/config

export KUBECONFIG=~/.kube/config

# Aggiungi a .bashrc se non già presente
if ! grep -q 'export KUBECONFIG=~/.kube/config' ~/.bashrc; then
    echo 'export KUBECONFIG=~/.kube/config' >> ~/.bashrc
fi

# Rendi leggibile anche il file originale K3s (fix permessi)
# NOTA: K3s può resettare i permessi al riavvio; la soluzione
# permanente è il binario kubectl standalone (step 0)
sudo chmod 644 /etc/rancher/k3s/k3s.yaml

# Verifica kubectl (senza sudo)
echo "Verifica kubectl..."
kubectl get nodes || { echo "ERRORE: kubectl non funziona. Controlla K3s."; exit 1; }

# --------------------------------------------------------------
# 2. VERIFICA GPU OPERATOR
# --------------------------------------------------------------
echo "[2/8] Verifica GPU Operator..."

GPU_PODS=$(kubectl get pods -n gpu-operator --no-headers 2>/dev/null | wc -l)
if [ "$GPU_PODS" -eq 0 ]; then
    echo "GPU Operator non trovato. Installazione per K3s..."

    helm repo add nvidia https://helm.ngc.nvidia.com/nvidia || true
    helm repo update

    # Installazione con parametri specifici K3s
    # Ref: https://docs.skypilot.co/en/latest/reference/kubernetes/kubernetes-deployment.html
    helm install gpu-operator -n gpu-operator --create-namespace \
      nvidia/gpu-operator \
        --set 'toolkit.env[0].name=CONTAINERD_CONFIG' \
        --set 'toolkit.env[0].value=/var/lib/rancher/k3s/agent/etc/containerd/config.toml' \
        --set 'toolkit.env[1].name=CONTAINERD_SOCKET' \
        --set 'toolkit.env[1].value=/run/k3s/containerd/containerd.sock' \
        --set 'toolkit.env[2].name=CONTAINERD_RUNTIME_CLASS' \
        --set 'toolkit.env[2].value=nvidia'

    echo "Attendo completamento GPU Operator (può richiedere 10+ minuti)..."
    kubectl wait --for=condition=ready pod \
        -l app=gpu-operator \
        -n gpu-operator \
        --timeout=600s
    echo "GPU Operator installato. Attendo propagazione label (60s)..."
    sleep 60
else
    echo "GPU Operator già installato ($GPU_PODS pod trovati)."
fi

# --------------------------------------------------------------
# 3. LABEL GPU SUL NODO
# --------------------------------------------------------------
echo "[3/8] Verifica e applicazione label GPU..."

GPU_PRODUCT_LABEL=$(kubectl get nodes --show-labels 2>/dev/null \
    | grep -c "nvidia.com/gpu.product" || true)

SKYPILOT_LABEL=$(kubectl get nodes --show-labels 2>/dev/null \
    | grep -c "skypilot.co/accelerator" || true)

if [ "$GPU_PRODUCT_LABEL" -gt 0 ]; then
    echo "Label nvidia.com/gpu.product già presente (GPU Operator attivo)."
else
    echo "WARN: Label nvidia.com/gpu.product non trovata."
fi

if [ "$SKYPILOT_LABEL" -eq 0 ]; then
    echo "Applicazione label skypilot.co/accelerator=a100-80gb-pcie..."
    kubectl label nodes --all \
        skypilot.co/accelerator=a100-80gb-pcie --overwrite
    echo "Label skypilot.co/accelerator applicata."
else
    echo "Label skypilot.co/accelerator già presente."
fi

# --------------------------------------------------------------
# 4. VERIFICA NVIDIA RUNTIME CLASS (necessaria per K3s)
# --------------------------------------------------------------
echo "[4/8] Verifica RuntimeClass nvidia..."

if ! kubectl get runtimeclass nvidia &>/dev/null; then
    echo "Creazione RuntimeClass nvidia..."
    kubectl apply -f - <<EOF
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: nvidia
handler: nvidia
EOF
else
    echo "RuntimeClass nvidia già presente."
fi

# Verifica GPU test pod
echo "Verifica GPU con test pod..."
kubectl apply -f https://raw.githubusercontent.com/skypilot-org/skypilot/master/tests/kubernetes/gpu_test_pod.yaml
echo "Attendo completamento test pod GPU (max 120s)..."
kubectl wait --for=jsonpath='{.status.phase}'=Succeeded pod/skygputest \
    --timeout=120s 2>/dev/null && echo "Test GPU superato!" || \
    echo "WARN: Test GPU non completato. Controlla con: kubectl logs skygputest"
kubectl delete -f https://raw.githubusercontent.com/skypilot-org/skypilot/master/tests/kubernetes/gpu_test_pod.yaml \
    --ignore-not-found=true

# --------------------------------------------------------------
# 5. PULIZIA STATO SKYPILOT PRECEDENTE
# CRITICO: rimuovi cluster in stato INIT/stale prima di sky ssh up
# per evitare: "Cluster was previously in SSH. Restarting."
# seguito da KubernetesError sul contesto mancante
# --------------------------------------------------------------
echo "[5/8] Pulizia stato SkyPilot precedente..."

source /home/velvet/DPO-unsloth-setup/.venv/bin/activate

# Rimuovi cluster stale se esiste
if sky status 2>/dev/null | grep -q "azure-gpu-cluster"; then
    echo "Cluster azure-gpu-cluster trovato. Rimozione stato stale..."
    sky down -y azure-gpu-cluster 2>/dev/null || true
    sleep 5
fi

# Cancella richieste sky ssh up pendenti
PENDING=$(sky api status 2>/dev/null \
    | grep "ssh_node_pools.up" \
    | grep "RUNNING" \
    | awk '{print $1}')

if [ -n "$PENDING" ]; then
    echo "Cancellazione richieste pendenti: $PENDING"
    sky api cancel $PENDING
    sleep 5
else
    echo "Nessuna richiesta pendente."
fi

# --------------------------------------------------------------
# 6. RIAVVIO API SERVER
# CRITICO: il server API deve essere riavviato DOPO aver
# installato il kubectl standalone e aggiornato ~/.kube/config,
# altrimenti continua a usare il vecchio contesto/credenziali
# --------------------------------------------------------------
echo "[6/8] Riavvio SkyPilot API server..."

sky api stop 2>/dev/null || true
sleep 3
sky api start
echo "Attendo avvio API server (10s)..."
sleep 10

# --------------------------------------------------------------
# 7. SKY SSH UP
# --------------------------------------------------------------
echo "[7/8] Avvio sky ssh up (attendere completamento)..."
echo "IMPORTANTE: Non interrompere questo processo!"

sky ssh up

# --------------------------------------------------------------
# 8. VERIFICA FINALE
# --------------------------------------------------------------
echo "[8/8] Verifica finale..."

echo "--- sky check ssh ---"
sky check ssh

echo "--- sky check kubernetes ---"
sky check kubernetes || true

echo "--- GPU disponibili (k8s) ---"
sky gpus list --infra k8s || true

echo "--- GPU disponibili (ssh) ---"
sky gpus list --infra ssh/azure-gpu-cluster || true

echo ""
echo "======================================"
echo " Setup completato con successo!"
echo ""
echo " Lancia un task GPU con:"
echo "   sky launch -y --infra ssh/azure-gpu-cluster --gpus A100-80GB:1 -- 'nvidia-smi'"
echo "======================================"