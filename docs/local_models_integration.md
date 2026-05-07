# Local Models Integration with LiteLLM

Guide: integrate vLLM local models (Velvet, Llama, etc.) into proxy routing.

## Architecture

```
Agent Code
    ↓
get_llm(model="llm") [or model="local"]
    ↓
LiteLLM Proxy (localhost:4000)
    ↓
Routing Decision:
  - model="llm" (default)    → Gemini → Groq → Cerebras → ... → Local (fallback)
  - model="local"            → Local vLLM only (offline)
  - model="remote"           → Skip local, remote providers only
  - force_remote=True        → Remote only (emergency)
```

## Setup

### 1. Add Local Model to proxy_config.yml

Already configured:

```yaml
# proxy_config.yml

model_list:
  # --- LLM LOCAL (vLLM on localhost:8001) ---
  - model_name: llm
    litellm_params:
      model: openai/velvet-2b-1.5_ba34086_t0.0
      api_key: "not-needed"
      api_base: "http://localhost:8001/v1"
      order: 4  # Lowest priority (fallback)
    model_info:
      id: local/velvet-2b-1.5
      name: velvet-2b-1.5
      provider: local-vllm

  # Explicit local alias
  - model_name: local
    litellm_params:
      model: openai/velvet-2b-1.5_ba34086_t0.0
      api_key: "not-needed"
      api_base: "http://localhost:8001/v1"
    model_info:
      id: local/velvet-2b-1.5
      name: velvet-2b-1.5-local
      provider: local-vllm
```

### 2. Start vLLM Server

Manual launch (GPU required):

```bash
bash local_models/velvet2B/run_server.sh
```

Or via docker-compose (optional, edit docker-compose.yml):

```bash
docker-compose up vllm-local
```

Verify health:

```bash
curl http://localhost:8001/v1/models
# Returns: {"object": "list", "data": [{"id": "velvet-2b-1.5_ba34086_t0.0", ...}]}
```

## Model Selection Strategies

### 1. Default (Auto-Fallback)

```python
from src.shared.llm import get_llm

llm = get_llm()  # Uses "llm" → proxy rotation
# Tries: Gemini → Groq → Cerebras → ... → Local (if all fail)
```

**Env**: None (uses `DEFAULT_MODEL="llm"`)

### 2. Offline-First (Prefer Local)

```python
llm = get_llm(model="local")  # Force local vLLM
```

**Env**:

```bash
export MODEL_STRATEGY=local
```

Then agents use local by default:

```python
from src.shared.llm import get_llm
llm = get_llm()  # Picks "local" (offline)
```

### 3. Cloud-First (Skip Local)

```python
llm = get_llm(model="llm", force_remote=True)  # Skip local fallback
```

**Env**:

```bash
export MODEL_STRATEGY=remote
```

### 4. Per-Agent Override

```bash
export LLM_CODE_RUNNER=local              # code_runner uses local
export LLM_TEXT2SQL_AGENT=groq/llama...   # text2sql uses Groq
export LLM_KNOWLEDGE_AGENT=llm            # knowledge_agent uses default
```

Then in agent code:

```python
from src.shared.llm import get_llm_for_agent

llm = get_llm_for_agent("code_runner")  # Reads LLM_CODE_RUNNER
```

## Usage Examples

### Example 1: Use Local When Available

```python
# .env
MODEL_STRATEGY=auto
DEFAULT_MODEL=llm

# Code
from src.shared.llm import get_llm

llm = get_llm()
# If vLLM fails: proxy tries remote providers
# If remote providers fail: uses local as final fallback
```

### Example 2: Offline Development (Local Only)

```bash
# Start vLLM
bash local_models/velvet2B/run_server.sh

# .env
export MODEL_STRATEGY=local
```

```python
from src.shared.llm import get_llm

llm = get_llm()  # Always local, no API keys needed
```

### Example 3: Cost Optimization (Local for Text2SQL, Cloud for Code)

```bash
export LLM_TEXT2SQL_AGENT=local
export LLM_CODE_RUNNER=groq/llama-3.3-70b-versatile
```

```python
from src.shared.llm import get_llm_for_agent

text2sql_llm = get_llm_for_agent("text2sql_agent")     # Local (cheap)
code_runner_llm = get_llm_for_agent("code_runner")    # Groq (powerful)
```

## Router Priority Order

LiteLLM tries in this order (when model="llm"):

| Order | Provider | Notes |
|-------|----------|-------|
| 1 | Gemini (Google AI) | Highest free tier quota |
| 2 | Groq, Cerebras, Mistral, etc. | Tier-2 remote |
| 3 | (Reserved) | Future tier-3 providers |
| 4 | Local vLLM | Fallback (localhost:8001) |

Routing stops on first success. Failure → next tier.

## Troubleshooting

### vLLM Service Unavailable

**Symptom**: `ConnectionError: http://localhost:8001`

**Solution**:

```bash
# Check if running
ps aux | grep vllm

# Restart
bash local_models/velvet2B/run_server.sh

# Verify health
curl http://localhost:8001/v1/models
```

### Model Not Found in Proxy

**Symptom**: `LiteLLMException: Model velvet-2b-1.5 not found`

**Solution**:

1. Check proxy_config.yml has `model_name: llm` entry
2. Verify vLLM reports correct model name:
   ```bash
   curl http://localhost:8001/v1/models | jq
   ```
3. Restart LiteLLM proxy:
   ```bash
   docker-compose restart litellm-proxy
   ```

### Proxy Prefers Remote Over Local

**Symptom**: vLLM is available but proxy uses cloud provider

**Reason**: `order: 4` is lowest priority. Proxy succeeds at `order: 1-3` first.

**To test local fallback**:

```bash
# Block remote provider (e.g., unset GOOGLE_API_KEY)
unset GOOGLE_API_KEY
export MODEL_STRATEGY=local  # Or use model="local" explicitly
```

### LLM Cache Collision (Calling get_llm Multiple Times)

**Issue**: `@lru_cache(maxsize=8)` caches by args. Different agents with same build params get cached instance.

**Solution**: Clear cache if model changes:

```python
from src.shared.llm import get_llm
get_llm.cache_clear()  # Clear cache
llm = get_llm(model="local")  # Fresh instance
```

## Configuration Reference

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `LITELLM_BASE_URL` | `http://localhost:4000/v1` | Proxy endpoint |
| `DEFAULT_MODEL` | `llm` | Default model name for routing pool |
| `MODEL_STRATEGY` | `auto` | Selection strategy: auto\|local\|remote |
| `LLM_{AGENT_NAME}` | (None) | Per-agent override (e.g., `LLM_CODE_RUNNER=local`) |
| `OPENAI_API_KEY` | `sk-not-needed` | Dummy key for proxy (required by ChatOpenAI) |

### proxy_config.yml

Local model entry:

```yaml
- model_name: llm              # For router pool
  litellm_params:
    model: openai/velvet-...   # vLLM model name
    api_key: "not-needed"
    api_base: "http://localhost:8001/v1"
    order: 4                   # Lowest priority
```

## Best Practices

### 1. Layered Fallback Strategy

```bash
# Prod: cloud first, local fallback
export MODEL_STRATEGY=auto
export DEFAULT_MODEL=llm

# Dev: local + lightweight, skip cloud
export MODEL_STRATEGY=local
```

### 2. Per-Agent Tuning

```bash
# Cheap tasks → local (2B model)
export LLM_KNOWLEDGE_AGENT=local
export LLM_RLM_AGENT=local

# Complex tasks → powerful cloud
export LLM_TEXT2SQL_AGENT=groq/llama-3.3-70b-versatile
export LLM_CODE_RUNNER=gemini/gemini-2.0-flash
```

### 3. Cost Monitoring

Track token usage in Phoenix:

```bash
http://localhost:6006  # Phoenix UI
# See provider costs per agent + model
```

## Next Steps

1. **Profile local model performance**:
   ```bash
   # Benchmark Velvet-2B latency + accuracy
   pytest src/agents/text2sql_agent/tests/test_text2sql.py -k local --benchmark
   ```

2. **Add more local models**:
   - Update `local_models/` directory
   - Register in `proxy_config.yml` with unique `served-model-name`
   - Update router priority (`order`)

3. **Production deployment**:
   - Use Kubernetes LLM node pool (GPUs)
   - Run vLLM via StatefulSet
   - Add model auto-scaling based on queue depth
