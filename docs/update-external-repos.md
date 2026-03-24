# Aggiornamento External Repos

## Setup iniziale (una volta sola)

```bash
make external-setup
```

Clona entrambi i repos in `external/`:
- `external/docs/` — documentazione LangChain/LangGraph/Deep Agents (sparse checkout)
- `external/langchain-skills/` — 11 SKILL.md con pattern e codice

## Aggiornamento

```bash
# Aggiorna entrambi
make external-update

# Oppure singolarmente
make external-docs-update
make external-skills-update
```

## Stato

```bash
make external-status
```

## Reset completo

```bash
make external-clean     # rimuove i cloni
make external-setup     # ri-clona da zero
```
