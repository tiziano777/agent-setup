
# 1. Solo torch dall'index PyTorch
pip install torch==2.4.0 torchvision==0.19.0 torchaudio==2.4.0 \
  --index-url https://download.pytorch.org/whl/cu121

# 2. FlashInfer dal suo index
pip install flashinfer \
  -i https://flashinfer.ai/whl/cu121/torch2.4/

# 3. SGLang da PyPI (NESSUN --index-url)
pip install "sglang[all]==0.3.1.post2"

# 4. Resto da PyPI
pip install "aiohttp>=3.9" pyyaml pandas pyarrow duckdb tqdm "pydantic>=2.0" pytest pytest-asyncio
