# Vault Runtime Secret Flow

This folder contains scripts that bootstrap Vault and inject runtime environment variables into services.

## Files

- `vault-init.sh`: One-shot bootstrap for Vault.
- `run-with-vault-env.sh`: Runtime launcher that authenticates via AppRole and exports env vars from Vault before starting a process.

## Secret Paths

The bootstrap script writes these kv-v2 paths:

- `secret/cle-engine/backend`
  - `DATABASE_URL`
  - `EMBEDDING_BACKEND`
  - `LLM_API_KEY`
  - `LLM_EMBEDDING_MODEL`
  - `LLM_EMBEDDING_URL`
  - `PYTHONUNBUFFERED`
- `secret/cle-engine/frontend`
  - `VITE_API_URL`
- `secret/cle-engine/admin`
  - `DATABASE_URL`
  - `API_URL`
  - `PYTHONUNBUFFERED`

## Authentication Model

- Vault init creates a dedicated policy and AppRole for each service (`backend`, `frontend`, `admin`).
- Role ID and Secret ID are written to `/vault/bootstrap/<service>/`.
- Runtime script reads those files, logs in to Vault, fetches env keys, exports them, then `exec`s the target command.

## Security Notes

- Application containers do not receive Vault root token.
- Application containers only have read permission for their own path.
- Role credentials are mounted read-only into app containers.
- Secrets are not hardcoded in service `environment` sections in compose.

This setup is suitable for local development stacks and keeps secret distribution centralized in Vault.
