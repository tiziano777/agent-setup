CLAUDE CODE  + HEADROOM
CLuade code is token expensive, use Headroom as proxy for context optimization!

1) DOCKER:

```shell

docker rm -f headroom-proxy

docker run -d \
  --name headroom-proxy \
  -p 8787:8080 \
  -e HEADROOM_TELEMETRY=on \
  python:3.13-slim \
  bash -c "pip install uv && uv tool run --from headroom-ai --with 'headroom-ai[code,proxy]' headroom proxy --port 8080 --host 127.0.0.1"

export ANTHROPIC_BASE_URL="http://localhost:8787"
claude
```

2) LOCAL
```shell
# 1. Installazione pulita con tutte le dipendenze e supporto code
uv tool install --python 3.13 "headroom-ai[all]"
uv tool install --python 3.13 "headroom-ai[code,proxy]"
uv tool update-shell

export HEADROOM_TELEMETRY=on

# 3. Controllo versione
headroom --version
headroom wrap claude
```