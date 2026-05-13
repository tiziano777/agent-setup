#!/usr/bin/env bash
set -euo pipefail

# start.sh - avvia vLLM (docker) se necessario, prepara `.inference_venv` e
# esegue il client async_client.py

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "[start.sh] Working directory: $ROOT"

# 1) Avvia server se non c'è nulla in ascolto su 8001
if ! ss -ltn | grep -q ':8001'; then
	echo "[start.sh] vLLM non in ascolto su :8001 — lancio server tramite server/run_vllm_server.sh"
	nohup bash server/run_vllm_server.sh > server/run_vllm_server.log 2>&1 &
	disown
else
	echo "[start.sh] vLLM sembra già in ascolto su :8001"
fi

# 2) Aspetta ~30s per dare tempo al container di avviarsi, poi loop di health-check
echo "[start.sh] Attendo 30s per dare tempo al server di iniziare..."
sleep 30
echo "[start.sh] Avvio loop di health-check su http://127.0.0.1:8001/v1/chat/completions"
while true; do
  if curl -sS -o /dev/null -m 3 http://127.0.0.1:8001/v1/chat/completions; then
    echo "[start.sh] Server pronto."
    break
  fi
  echo "[start.sh] Server non ancora pronto, riprovo tra 1s..."
  sleep 1
done

# 3) Crea o aggiorna la virtualenv `.inference_venv` nel percorso corrente
VENV="$ROOT/.inference_venv"
if [ ! -d "$VENV" ]; then
	echo "[start.sh] Creazione virtualenv $VENV"
	python3 -m venv "$VENV"
	. "$VENV/bin/activate"
	pip install --upgrade pip
	# Preferisci requisiti locali se presenti
	if [ -f "$ROOT/client/requirements.txt" ]; then
		pip install -r "$ROOT/client/requirements.txt"
	elif [ -f "$ROOT/requirements.txt" ]; then
		pip install -r "$ROOT/requirements.txt"
	else
		pip install aiohttp tqdm pyyaml duckdb
	fi
	deactivate
else
	echo "[start.sh] Virtualenv $VENV già presente"
fi

# 4) Attiva la venv e avvia il client
echo "[start.sh] Attivazione virtualenv e lancio client"
. "$VENV/bin/activate"
python "$ROOT/client/async_client.py"
RET=$?
deactivate
exit $RET

