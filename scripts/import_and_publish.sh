#!/usr/bin/env bash
# ============================================
# Import & Publish All Workflows
# ============================================
# Run this AFTER running setup.sh:
#   docker compose up -d
#   ./scripts/setup.sh
#   ./scripts/import_and_publish.sh
# ============================================

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "========================================"
echo " Import & Publish All Workflows"
echo "========================================"

# ── Wait for n8n ────────────────────────────
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

# ── Check owner user ────────────────────────
echo ""
echo "2. Checking owner user..."
USER_ID=$(docker exec n8n-postgres psql -U n8n -d n8n -t -A -c "SELECT id FROM public.user LIMIT 1;" 2>/dev/null | tr -d '[:space:]')
if [ -z "$USER_ID" ]; then
  echo "   ERROR: No user found. Run setup.sh first."
  exit 1
fi
echo "   Owner user: $USER_ID"

# ── Import workflows ────────────────────────
echo ""
echo "3. Importing workflows..."

for dir in reasoning/wf_rs_01 reasoning/wf_rs_02 reasoning/wf_rs_03 reasoning/wf_rs_04 reasoning/wf_rs_05 reasoning/wf_rs_06 platform/wf_ps_01 platform/wf_ps_02 platform/wf_ps_03 platform/wf_ps_04 platform/wf_ps_05 platform/wf_ps_06 chained/wf_cc_01 subworkflows/SW-CRM-ReadOnly subworkflows/SW-Finance-Admin; do
  if docker exec n8n-app sh -c "[ -d /tmp/workflows/$dir ]"; then
    echo "   Importing: $dir"
    docker exec n8n-app n8n import:workflow --separate --input="/tmp/workflows/$dir" --userId "$USER_ID"
  else
    echo "   Skipping: $dir (not found)"
  fi
done
echo "   Workflows imported."

# ── Get all workflow IDs ────────────────────
echo ""
echo "4. Getting workflow IDs..."

WORKFLOW_IDS=$(docker exec n8n-postgres psql -U n8n -d n8n -t -A -c "SELECT id FROM public.workflow_entity;" 2>/dev/null | grep -v '^$' || true)
COUNT=$(echo "$WORKFLOW_IDS" | grep -c . || echo "0")
echo "   Found $COUNT workflows."

# ── Publish workflows ───────────────────────
echo ""
echo "5. Publishing workflows..."

for wf_id in $WORKFLOW_IDS; do
  if [ -n "$wf_id" ]; then
    echo "   Publishing workflow: $wf_id"
    docker exec n8n-app n8n publish:workflow --id="$wf_id" 2>/dev/null || true
  fi
done
echo "   All workflows published."

# ── Restart n8n ─────────────────────────────
echo ""
echo "6. Restarting n8n..."
docker compose restart n8n
echo "   n8n restarting..."

# ── Wait for n8n to be ready again ──────────
echo ""
echo "7. Waiting for n8n to be ready..."
sleep 5
for i in $(seq 1 30); do
  if curl -sf http://localhost:5678/healthz > /dev/null 2>&1; then
    echo "   n8n is ready."
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "   WARNING: n8n may still be starting. Check: docker compose logs n8n"
  fi
  sleep 2
done

# ── Summary ─────────────────────────────────
echo ""
echo "========================================"
echo " Import & Publish Complete!"
echo "========================================"
echo ""
echo "Webhook URLs (after activation):"
echo "  Reasoning Suite:"
echo "    POST http://localhost:5678/webhook/wf-rs-01-baseline"
echo "    POST http://localhost:5678/webhook/wf-rs-02"
echo "    POST http://localhost:5678/webhook/wf-rs-03"
echo "    POST http://localhost:5678/webhook/wf-rs-04"
echo "    POST http://localhost:5678/webhook/wf-rs-05"
echo "    POST http://localhost:5678/webhook/wf-rs-06"
echo "    POST http://localhost:5678/webhook/wf-rs-01-guardrail"
echo "  Platform Suite:"
echo "    POST http://localhost:5678/webhook/wf-ps-01"
echo "    POST http://localhost:5678/webhook/wf-ps-02"
echo "    POST http://localhost:5678/webhook/wf-ps-03"
echo "    POST http://localhost:5678/webhook/wf-ps-04"
echo "    POST http://localhost:5678/webhook/wf-ps-05"
echo "    POST http://localhost:5678/webhook/wf-ps-06-baseline"
echo "  Composite/Chained:"
echo "    POST http://localhost:5678/webhook/wf-cc-01"
echo ""
echo "Next steps:"
echo "  1. Verify workflows are active in http://localhost:5678"
echo "  2. Run smoke tests: python -m pytest tests/ -v"
echo "  3. Run AVISE tests: python scripts/run_avise.py --slim"
echo ""
