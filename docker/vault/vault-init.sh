#!/bin/sh
set -eu

VAULT_ADDR="${VAULT_ADDR:-http://vault:8200}"
export VAULT_ADDR

VAULT_TOKEN="${VAULT_TOKEN:?VAULT_TOKEN is required}"
WAIT_RETRIES="${VAULT_WAIT_RETRIES:-60}"
WAIT_DELAY_SECONDS="${VAULT_WAIT_DELAY_SECONDS:-2}"

wait_for_vault() {
  attempt=1
  while [ "$attempt" -le "$WAIT_RETRIES" ]; do
    if vault status >/dev/null 2>&1; then
      return 0
    fi
    echo "Waiting for Vault to be available... ($attempt/$WAIT_RETRIES)"
    sleep "$WAIT_DELAY_SECONDS"
    attempt=$((attempt + 1))
  done

  echo "Vault is not available after waiting ${WAIT_RETRIES} attempts." >&2
  return 1
}

ensure_kv_engine() {
  if vault secrets list -format=json | grep -q '"secret/"'; then
    return 0
  fi
  vault secrets enable -path=secret kv-v2 >/dev/null
}

ensure_approle_auth() {
  if vault auth list -format=json | grep -q '"approle/"'; then
    return 0
  fi
  vault auth enable approle >/dev/null
}

write_policy() {
  policy_name="$1"
  policy_path="$2"

  cat >"/tmp/${policy_name}.hcl" <<EOF
path "${policy_path}" {
  capabilities = ["read"]
}
EOF

  vault policy write "$policy_name" "/tmp/${policy_name}.hcl" >/dev/null
}

configure_role() {
  role_name="$1"
  policy_name="$2"

  vault write "auth/approle/role/${role_name}" \
    token_policies="${policy_name}" \
    token_ttl="1h" \
    token_max_ttl="4h" \
    secret_id_ttl="24h" \
    secret_id_num_uses=0 >/dev/null
}

write_role_credentials() {
  service_name="$1"
  role_name="$2"

  service_dir="/vault/bootstrap/${service_name}"
  mkdir -p "$service_dir"

  vault read -field=role_id "auth/approle/role/${role_name}/role-id" >"${service_dir}/role_id"
  vault write -f -field=secret_id "auth/approle/role/${role_name}/secret-id" >"${service_dir}/secret_id"

  chmod 0444 "${service_dir}/role_id" "${service_dir}/secret_id"
}

wait_for_vault
vault login -no-print "$VAULT_TOKEN" >/dev/null

ensure_kv_engine
ensure_approle_auth

vault kv put secret/cle-engine/backend \
  DATABASE_URL="${BACKEND_DATABASE_URL:-postgresql://admin:local_dev@db:5432/cle_engine}" \
  EMBEDDING_BACKEND="${BACKEND_EMBEDDING_BACKEND:-llm_api}" \
  INTELLIGENCE_BACKEND="${BACKEND_INTELLIGENCE_BACKEND:-generic_http}" \
  LLM_API_KEY="${LLM_API_KEY:-}" \
  LLM_EMBEDDING_MODEL="${LLM_EMBEDDING_MODEL:-text-embedding-3-small}" \
  LLM_EMBEDDING_URL="${LLM_EMBEDDING_URL:-https://api.openai.com/v1/embeddings}" \
  LLM_COMPLETION_MODEL="${LLM_COMPLETION_MODEL:-gpt-4o-mini}" \
  LLM_COMPLETION_URL="${LLM_COMPLETION_URL:-https://api.openai.com/v1/chat/completions}" \
  FINAL_RERANKER_MODEL_DIR="${FINAL_RERANKER_MODEL_DIR:-models/final_reranker}" \
  FINAL_RERANKER_MANIFEST_FILE="${FINAL_RERANKER_MANIFEST_FILE:-manifest.json}" \
  PYTHONUNBUFFERED="${BACKEND_PYTHONUNBUFFERED:-1}" >/dev/null

vault kv put secret/cle-engine/frontend \
  VITE_API_URL="${FRONTEND_API_URL:-http://localhost:8000}" >/dev/null

vault kv put secret/cle-engine/admin \
  DATABASE_URL="${ADMIN_DATABASE_URL:-postgresql://admin:local_dev@db:5432/cle_engine}" \
  API_URL="${ADMIN_API_URL:-http://backend:8000}" \
  PYTHONUNBUFFERED="${ADMIN_PYTHONUNBUFFERED:-1}" >/dev/null

write_policy "cle-backend-policy" "secret/data/cle-engine/backend"
write_policy "cle-frontend-policy" "secret/data/cle-engine/frontend"
write_policy "cle-admin-policy" "secret/data/cle-engine/admin"

configure_role "cle-backend-role" "cle-backend-policy"
configure_role "cle-frontend-role" "cle-frontend-policy"
configure_role "cle-admin-role" "cle-admin-policy"

write_role_credentials "backend" "cle-backend-role"
write_role_credentials "frontend" "cle-frontend-role"
write_role_credentials "admin" "cle-admin-role"

echo "Vault bootstrap completed successfully."
