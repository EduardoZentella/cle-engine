#!/bin/sh
set -eu

usage() {
  echo "Usage: $0 <service-name> <kv-v2-data-path> -- <command> [args...]" >&2
  echo "Example: $0 backend secret/data/cle-engine/backend -- uvicorn app.api.main:app" >&2
}

if [ "$#" -lt 4 ]; then
  usage
  exit 1
fi

SERVICE_NAME="$1"
SECRET_PATH="$2"
shift 2

if [ "$1" != "--" ]; then
  usage
  exit 1
fi
shift

VAULT_ADDR="${VAULT_ADDR:-http://vault:8200}"
ROLE_ID_FILE="${VAULT_ROLE_ID_FILE:-/vault/bootstrap/${SERVICE_NAME}/role_id}"
SECRET_ID_FILE="${VAULT_SECRET_ID_FILE:-/vault/bootstrap/${SERVICE_NAME}/secret_id}"
WAIT_RETRIES="${VAULT_WAIT_RETRIES:-60}"
WAIT_DELAY_SECONDS="${VAULT_WAIT_DELAY_SECONDS:-2}"

wait_for_inputs() {
  attempt=1
  while [ "$attempt" -le "$WAIT_RETRIES" ]; do
    if [ -s "$ROLE_ID_FILE" ] && [ -s "$SECRET_ID_FILE" ] && curl -sS "${VAULT_ADDR}/v1/sys/health" >/dev/null 2>&1; then
      return 0
    fi

    echo "Waiting for Vault credentials for ${SERVICE_NAME}... ($attempt/$WAIT_RETRIES)"
    sleep "$WAIT_DELAY_SECONDS"
    attempt=$((attempt + 1))
  done

  echo "Vault credentials or endpoint unavailable for service ${SERVICE_NAME}." >&2
  return 1
}

wait_for_inputs

ROLE_ID="$(cat "$ROLE_ID_FILE")"
SECRET_ID="$(cat "$SECRET_ID_FILE")"

LOGIN_PAYLOAD="$(jq -cn --arg role_id "$ROLE_ID" --arg secret_id "$SECRET_ID" '{role_id: $role_id, secret_id: $secret_id}')"

LOGIN_RESPONSE="$(curl -sS --request POST --data "$LOGIN_PAYLOAD" "${VAULT_ADDR}/v1/auth/approle/login")"
CLIENT_TOKEN="$(printf '%s' "$LOGIN_RESPONSE" | jq -r '.auth.client_token // empty')"

if [ -z "$CLIENT_TOKEN" ]; then
  echo "Failed to authenticate with Vault using AppRole for ${SERVICE_NAME}." >&2
  exit 1
fi

SECRET_RESPONSE="$(curl -sS --header "X-Vault-Token: ${CLIENT_TOKEN}" "${VAULT_ADDR}/v1/${SECRET_PATH}")"
ERROR_COUNT="$(printf '%s' "$SECRET_RESPONSE" | jq '.errors | length // 0')"

if [ "$ERROR_COUNT" -gt 0 ]; then
  echo "Failed to read secret path ${SECRET_PATH} for ${SERVICE_NAME}." >&2
  printf '%s\n' "$SECRET_RESPONSE" | jq -r '.errors[]'
  exit 1
fi

for encoded_entry in $(printf '%s' "$SECRET_RESPONSE" | jq -r '.data.data | to_entries[] | @base64'); do
  entry_json="$(printf '%s' "$encoded_entry" | base64 -d)"
  entry_key="$(printf '%s' "$entry_json" | jq -r '.key')"
  entry_value="$(printf '%s' "$entry_json" | jq -r '.value | tostring')"
  export "${entry_key}=${entry_value}"
done

unset ROLE_ID
unset SECRET_ID
unset CLIENT_TOKEN

exec "$@"
