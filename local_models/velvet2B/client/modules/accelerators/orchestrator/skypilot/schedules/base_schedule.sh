#!/usr/bin/env bash
# =============================================================================
# base_schedule.sh — SkyPilot Experiment Orchestrator (Sequenziale/Coda)
# =============================================================================
set -euo pipefail

sudo apt install socat

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(dirname "$SCRIPT_DIR")"
# Risale fino alla root del tuo repository
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"

# Defaults definiti dalla documentazione
BASE_CONFIG="${REPO_ROOT}/config.yml"
LINEAGE_FILE="${REPO_ROOT}/.lineage/experiment.yml"
TEMPLATE_FILE="${MODULE_DIR}/tasks/task_template.yaml"
GENERATED_DIR="${MODULE_DIR}/generated"
CLUSTER_NAME="azure-gpu-cluster-2"
INFRA="ssh/azure-gpu-cluster-2"  # Configurazione infrastruttura SSH Node Pool
DRY_RUN=false
PARALLEL=false 
CLUSTER_PREFIX=""
VARIANT_FILES=()

echo "variabili inizializzate:"
echo "BASE_CONFIG=$BASE_CONFIG"
echo "LINEAGE_FILE=$LINEAGE_FILE"
echo "TEMPLATE_FILE=$TEMPLATE_FILE"
echo "GENERATED_DIR=$GENERATED_DIR"
echo "CLUSTER_NAME=$CLUSTER_NAME"
echo "INFRA=$INFRA"
echo "DRY_RUN=$DRY_RUN"
echo "PARALLEL=$PARALLEL"
echo "CLUSTER_PREFIX=$CLUSTER_PREFIX"
echo "VARIANT_FILES=${VARIANT_FILES[@]}"

echo "INFO: pulizia preventiva dell'ambiente SkyPilot per il cluster '$CLUSTER_NAME'..."
sky down $CLUSTER_NAME 
echo "🚀 Esecuzione automatica di 'sky ssh up'..."
echo " INFO: se il comando fallisce, potresti non aver settato chiavi SSH o configurato correttamente SkyPilot. " >&2
sky ssh up || echo "⚠️ 'sky ssh up' ha restituito un avviso, procedo comunque con il lancio."

HOME_SKY_DIR="${HOME}/.sky"
REPO_SKY_SRC="${MODULE_DIR}/.sky/ssh_node_pools.yaml"


if [ "$DRY_RUN" = false ]; then
  if [ ! -f "${HOME_SKY_DIR}/ssh_node_pools.yaml" ]; then
    echo "⚠️ Configurazione SkyPilot non trovata in ${HOME_SKY_DIR}"
    
    if [ -f "$REPO_SKY_SRC" ]; then
      echo "📦 Inizializzazione automatica dell'infrastruttura dal repository..."
      mkdir -p "$HOME_SKY_DIR"
      ln -sf "$REPO_SKY_SRC" "${HOME_SKY_DIR}/ssh_node_pools.yaml"
      echo "✅ Collegamento simbolico creato con successo: ${HOME_SKY_DIR}/ssh_node_pools.yaml -> $REPO_SKY_SRC"
    else
      echo "❌ ERROR: File di configurazione sorgente non trovato in $REPO_SKY_SRC" >&2
      exit 1
    fi
  fi
fi

# Parsing degli argomenti
while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) BASE_CONFIG="$2"; shift 2 ;;
    --lineage) LINEAGE_FILE="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --parallel) PARALLEL=true; shift ;; 
    --cluster-prefix) CLUSTER_PREFIX="$2"; shift 2 ;;
    --cluster-name) CLUSTER_NAME="$2"; shift 2 ;;
    --infra) INFRA="$2"; shift 2 ;; # Permette di sovrascrivere l'infra da CLI
    -h|--help) 
      echo "SkyPilot Experiment Orchestrator"
      echo "Usage: $0 [--config PATH] [--lineage PATH] [--dry-run] [--cluster-prefix PREFIX] [--infra INFRA] [variants/..]"
      exit 0 ;;
    *) VARIANT_FILES+=("$1"); shift ;;
  esac
done

if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 è richiesto per l'unione dei file di configurazione." >&2
  exit 1
fi

mkdir -p "$GENERATED_DIR"

if [[ ${#VARIANT_FILES[@]} -eq 0 ]]; then
  VARIANT_FILES=("__base__")
fi

# -----------------------------------------------------------------------------
# Motore Python per estrazione sicura e Deep Merge
# -----------------------------------------------------------------------------
py_extract_field() {
  python3 -c "
import yaml
with open('$1') as f:
    d = yaml.safe_load(f) or {}
for k in '$2'.split('.'):
    d = d.get(k, '') if isinstance(d, dict) else ''
print(str(d).replace('+', ''))
" 2>/dev/null || echo "$3"
}

py_deep_merge_and_lineage() {
  local out="$1" l_file="$2" b_file="$3" v_file="$4"
  python3 -c "
import yaml
import sys

def deep_merge(dict1, dict2):
    \"\"\"Merge ricorsivo che sovrascrive dict1 con dict2\"\"\"
    for key, value in dict2.items():
        if isinstance(value, dict) and key in dict1 and isinstance(dict1[key], dict):
            deep_merge(dict1[key], value)
        else:
            dict1[key] = value

# 1. Carica tutti i file
with open('$b_file') as f:
    base_config = yaml.safe_load(f) or {}

with open('$l_file') as f:
    lineage_data = yaml.safe_load(f) or {}

variant_config = {}
variant_file_path = '$v_file'
if variant_file_path and variant_file_path != '':
    try:
        with open(variant_file_path) as f:
            variant_config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        pass

# 2. Costruisci la configurazione finale
final_dict = {}

# 3. Prima applica la base
deep_merge(final_dict, base_config)

# 4. Poi applica il lineage (sovrascrive la base)
if 'experiment' in lineage_data:
    deep_merge(final_dict, lineage_data)

# 5. Ora applica la variante MA gestisci experiment in modo speciale
for key, value in variant_config.items():
    if key == 'experiment':
        # Per experiment: merge ricorsivo ma preserva tutti i campi
        if 'experiment' not in final_dict:
            final_dict['experiment'] = {}
        # Merge dei campi experiment
        for exp_key, exp_value in value.items():
            final_dict['experiment'][exp_key] = exp_value
    else:
        # Per tutti gli altri campi: merge normale
        if isinstance(value, dict) and key in final_dict and isinstance(final_dict[key], dict):
            deep_merge(final_dict[key], value)
        else:
            final_dict[key] = value

# 6. Assicura che i campi obbligatori ci siano
if 'experiment' not in final_dict:
    final_dict['experiment'] = {}

# Se l'ID non è stato impostato dalla variante, usa quello del lineage
if 'id' not in final_dict['experiment'] and 'experiment' in lineage_data and 'id' in lineage_data['experiment']:
    final_dict['experiment']['id'] = lineage_data['experiment']['id']

# 7. Salva
with open('$out', 'w') as f:
    yaml.dump(final_dict, f, default_flow_style=False, allow_unicode=True)

print(f'Configurazione salvata in $out')
"
}

# Estrazione Risorse Hardware per SkyPilot
SKY_ACCELERATORS=$(py_extract_field "$BASE_CONFIG" "hardware.skypilot.resources.accelerators" "A100-80GB:1")
SKY_CPUS=$(py_extract_field "$BASE_CONFIG" "hardware.skypilot.resources.cpus" "24")
SKY_MEMORY=$(py_extract_field "$BASE_CONFIG" "hardware.skypilot.resources.memory" "216")

# -----------------------------------------------------------------------------
# Ciclo di generazione ed esecuzione delle Varianti
# -----------------------------------------------------------------------------
for i in "${!VARIANT_FILES[@]}"; do
  variant_file="${VARIANT_FILES[$i]}"
  
  # 1. Determiniamo PRIMA il nome della variante (Evita bug di precedenza)
  variant_name="base"
  if [[ "$variant_file" != "__base__" ]]; then
    variant_name=$(basename "$variant_file" .yml)
  fi

  # 2. Generiamo l'ID e la cartella usando il nome appena estratto
  run_id="${variant_name}_$(date +%Y%m%d_%H%M%S)_${i}"
  run_sandbox_dir="${GENERATED_DIR}/run_${run_id}"
  mkdir -p "$run_sandbox_dir"
  
  # 3. Log e normalizzazione del path per lo script python successivo
  if [[ "$variant_file" == "__base__" ]]; then
    variant_file=""
    echo "=== Preparazione Variante: BASE ==="
  else
    echo "=== Preparazione Variante: ${variant_name} ==="
  fi

  merged_config_path="${run_sandbox_dir}/config_${variant_name}.yml"
  
  # Esegui il Deep Merge e l'iniezione del Lineage Tracker
  py_deep_merge_and_lineage "$merged_config_path" "$LINEAGE_FILE" "$BASE_CONFIG" "$variant_file"

  experiment_name=$(py_extract_field "$merged_config_path" "experiment.name" "dpo_exp")
  job_display_name="${experiment_name}"
  if [[ -n "$CLUSTER_PREFIX" ]]; then
    job_display_name="${CLUSTER_PREFIX}_${variant_name}"
  fi

  task_yaml="${run_sandbox_dir}/task_${variant_name}.yaml"
  
  # Calcola il path relativo corretto partendo dalla REPO_ROOT specchiata da SkyPilot
  config_path="$(realpath --relative-to="$REPO_ROOT" "$merged_config_path")"

  # Genera il task YAML sostituendo i placeholder
  python3 -c "
with open('$TEMPLATE_FILE') as f:
    content = f.read()

content = content.replace('__TASK_NAME__', '${job_display_name}')
content = content.replace('__SKY_ACCELERATORS__', '${SKY_ACCELERATORS}')
content = content.replace('__SKY_CPUS__', '${SKY_CPUS}')
content = content.replace('__SKY_MEMORY__', '${SKY_MEMORY}')
content = content.replace('__REPO_ROOT__', '${REPO_ROOT}')
content = content.replace('__CONFIG_PATH__', '${config_path}')

with open('$task_yaml', 'w') as f:
    f.write(content)
"

  # Sottomissione alla coda o Dry Run
  if [[ "$DRY_RUN" == true ]]; then
    echo "   [DRY-RUN] sky launch --infra $INFRA -c ${CLUSTER_NAME} ${task_yaml} --detach-run"
    echo "   [DRY-RUN] Configurazione fusa generata in: $merged_config_path"
    echo "   [DRY-RUN] config_path: ${config_path}"
    echo "   [DRY-RUN] merged_config_path exists: $(test -f "$merged_config_path" && echo YES || echo NO)"
    echo ""
  else
    echo "   Sottomissione in coda su infrastruttura '$INFRA' con nome cluster '$CLUSTER_NAME'..."
    sky launch --infra "$INFRA" -c "$CLUSTER_NAME" "$task_yaml" -y --detach-run 
    echo "   Job sottomesso con successo."
  fi
done

echo "=== Elaborazione completata. Directory di Staging: $(realpath "$GENERATED_DIR") ==="
if [[ "$DRY_RUN" == false ]]; then
  echo "Controlla lo stato della coda hardware con il comando: sky queue $CLUSTER_NAME"
fi