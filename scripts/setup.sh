#!/usr/bin/env bash
# ============================================
# n8n Research Lab Setup
# ============================================
# Run this AFTER starting the Docker environment:
#   docker compose up -d
#   ./scripts/setup.sh
# ============================================

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load .env
set -a
source "$PROJECT_DIR/.env"
set +a

echo "========================================"
echo " n8n Lab Setup: Credentials & Workflows"
echo "========================================"

# ====== Wait for n8n ====================================================================================
echo ""
echo "1. Waiting for n8n..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:5678/healthz > /dev/null 2>&1; then
    echo "   n8n is ready."
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "   ERROR: n8n did not become ready. Check: docker compose logs n8n"
    exit 1
  fi
  sleep 2
done

# ====== Check owner user ========================================================================
echo ""
echo "2. Checking owner user..."
USER_ID=$(docker exec n8n-postgres psql -U n8n -d n8n -t -A -c "SELECT id FROM public.user LIMIT 1;" 2>/dev/null | tr -d '[:space:]')
if [ -z "$USER_ID" ]; then
  echo "   No user found. Open http://localhost:5678 in your browser,"
  echo "   complete the setup wizard to create your account, then re-run this script."
  exit 1
fi
echo "   Owner user: $USER_ID"

# ====== Generate credential UUIDs ===================================
echo ""
echo "3. Generating credential UUIDs..."
PG_CRED_ID=$(docker exec n8n-app node -e "console.log(require('crypto').randomUUID())" 2>/dev/null | tr -d '[:space:]')
echo "   IDs generated."

# ====== Generate credential JSON files ==============================
echo ""
echo "4. Generating credential files..."
CRED_DIR=$(mktemp -d)

# PostgreSQL Database
cat > "$CRED_DIR/postgres-database.json" <<EOF
{
  "id": "${PG_CRED_ID}",
  "name": "PostgreSQL Database",
  "type": "postgres",
  "data": {
    "host": "postgres",
    "database": "${POSTGRES_DB}",
    "user": "${POSTGRES_USER}",
    "password": "${POSTGRES_PASSWORD}",
    "port": 5432,
    "maxConnections": 10,
    "allowUnauthorizedCerts": true,
    "ssl": "disable"
  }
}
EOF

# Ollama API
cat > "$CRED_DIR/ollama-api.json" <<EOF
{
  "id": "ollama-cred",
  "name": "Ollama",
  "type": "ollamaApi",
  "data": {
    "baseUrl": "http://ollama:11434"
  }
}
EOF

# OpenAI / OpenCode / OpenRouter (whichever key is available)
LLM_API_KEY="${OPENCODE_API_KEY:-${OPENAI_API_KEY:-${OPENROUTER_API_KEY:-}}}"
if [ -n "$LLM_API_KEY" ]; then
  LLM_CRED_ID=$(docker exec n8n-app node -e "console.log(require('crypto').randomUUID())" 2>/dev/null | tr -d '[:space:]')
  cat > "$CRED_DIR/openai-api.json" <<EOF
{
  "id": "${LLM_CRED_ID}",
  "name": "OpenAI API Key",
  "type": "openAiApi",
  "data": {
    "apiKey": "${LLM_API_KEY}"${LLM_BASE_URL:+,
    "baseURL": "${LLM_BASE_URL}"}
  }
}
EOF
  echo "   Generated: OpenAI-compatible credential (using key from .env)"
fi

echo "   Credential files created."

# ====== Delete stale workflows (from previous imports) ======
echo ""
echo "5. Cleaning stale workflows..."
docker exec n8n-postgres psql -U n8n -d n8n -c \
  "DELETE FROM public.workflow_entity WHERE name LIKE 'WF-%' OR name LIKE 'SW-%';" > /dev/null 2>&1 || true
echo "   Stale workflows removed."

# ====== Delete stale credentials (from previous imports) ==============
echo ""
echo "6. Cleaning stale credentials..."
docker exec n8n-postgres psql -U n8n -d n8n -c \
  "DELETE FROM public.credentials_entity WHERE name IN ('Ollama', 'PostgreSQL Database', 'OpenAI API Key');" > /dev/null 2>&1 || true
echo "   Stale credentials removed."

# ====== Copy credentials to container =================================
echo ""
echo "7. Copying credentials to container..."
docker exec n8n-app sh -c "mkdir -p /tmp/credentials"
docker cp "$CRED_DIR/." n8n-app:/tmp/credentials/
rm -rf "$CRED_DIR"

# ====== Import credentials ==================================================================
echo ""
echo "8. Importing credentials..."
docker exec n8n-app n8n import:credentials --separate --input=/tmp/credentials --userId "$USER_ID"
echo "   Credentials imported."

# ====== Import workflows ========================================================================
echo ""
echo "9. Importing workflows from subdirectories..."

for dir in reasoning/baseline reasoning/basic_guardrail platform/baseline subworkflows/SW-CRM-ReadOnly subworkflows/SW-Finance-Admin; do
  if docker exec n8n-app sh -c "[ -d /tmp/workflows/$dir ]"; then
    docker exec n8n-app n8n import:workflow --separate --input="/tmp/workflows/$dir" --userId "$USER_ID"
    echo "   Imported: $dir"
  else
    echo "   Skipping: $dir (not found)"
  fi
done

echo "   Workflows imported."

echo ""
echo "========================================"
echo " Setup complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Open http://localhost:5678"
echo "  2. Open each workflow and click Active"
echo "  3. If credentials need re-linking, edit each workflow"
echo "     and re-select them from the credential dropdown"
echo ""