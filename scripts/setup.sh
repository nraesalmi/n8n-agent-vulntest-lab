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

# ====== Generate credential JSON files ==============================
echo ""
echo "1. Generating credential files..."
CRED_DIR=$(mktemp -d)


# PostgreSQL Database
cat > "$CRED_DIR/postgres-database.json" <<EOF
{
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

# OpenAI / OpenCode / OpenRouter (whichever key is available)
LLM_API_KEY="${OPENCODE_API_KEY:-${OPENAI_API_KEY:-${OPENROUTER_API_KEY:-}}}"
if [ -n "$LLM_API_KEY" ]; then
  cat > "$CRED_DIR/openai-api.json" <<EOF
{
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

# ====== Wait for n8n ====================================================================================
echo ""
echo "2. Waiting for n8n..."
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

# ====== Delete stale workflows (from previous imports) ======
echo ""
echo "3. Cleaning stale workflows..."
docker exec n8n-postgres psql -U n8n -d n8n -c \
  "DELETE FROM public.workflow_entity WHERE name LIKE 'WF-%' OR name LIKE 'SW-%';" > /dev/null 2>&1 || true
echo "   Stale workflows removed."

# ====== Copy credentials to container =================================
echo ""
echo "4. Copying credentials to container..."
docker cp "$CRED_DIR/." n8n-app:/tmp/credentials/
rm -rf "$CRED_DIR"

# ====== Import credentials ==================================================================
echo ""
echo "5. Importing credentials..."
docker exec n8n-app n8n import:credentials --separate --input=/tmp/credentials
echo "   Credentials imported."

# ====== Import workflows ========================================================================
echo ""
echo "6. Importing workflows from subdirectories..."

for dir in baseline basic_guardrail subworkflows/SW-CRM-ReadOnly subworkflows/SW-Finance-Admin; do
  if docker exec n8n-app sh -c "[ -d /tmp/workflows/$dir ]"; then
    docker exec n8n-app n8n import:workflow --separate --input="/tmp/workflows/$dir"
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