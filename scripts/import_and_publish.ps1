# ============================================
# Import & Publish All Workflows
# ============================================
# Run this AFTER running setup.ps1:
#   docker compose up -d
#   .\scripts\setup.ps1
#   .\scripts\import_and_publish.ps1
# ============================================

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent (Split-Path -Parent $PSCommandPath)

Write-Host "========================================"
Write-Host " Import & Publish All Workflows"
Write-Host "========================================"

# ── Step 1: Wait for n8n ───────────────────
Write-Host ""
Write-Host "1. Waiting for n8n..."
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:5678/healthz" -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
    Start-Sleep -Seconds 2
}
if (-not $ready) {
    Write-Host "   ERROR: n8n did not become ready. Check: docker compose logs n8n"
    exit 1
}
Write-Host "   n8n is ready."

# ── Step 2: Check owner user ─────────────────
Write-Host ""
Write-Host "2. Checking owner user..."
$userId = docker exec n8n-postgres psql -U n8n -d n8n -t -A -c "SELECT id FROM public.user LIMIT 1;" 2>&1
if (-not $userId -or $userId.Trim() -eq "") {
    Write-Host "   ERROR: No user found. Run setup.ps1 first."
    exit 1
}
$userId = $userId.Trim()
Write-Host "   Owner user: $userId"

# ── Step 3: Import workflows ─────────────────
Write-Host ""
Write-Host "3. Importing workflows..."

$workflowDirs = @(
    "/tmp/workflows/reasoning/wf_rs_01",
    "/tmp/workflows/reasoning/wf_rs_02",
    "/tmp/workflows/reasoning/wf_rs_03",
    "/tmp/workflows/reasoning/wf_rs_04",
    "/tmp/workflows/reasoning/wf_rs_05",
    "/tmp/workflows/reasoning/wf_rs_06",
    "/tmp/workflows/platform/wf_ps_01",
    "/tmp/workflows/platform/wf_ps_02",
    "/tmp/workflows/platform/wf_ps_03",
    "/tmp/workflows/platform/wf_ps_04",
    "/tmp/workflows/platform/wf_ps_05",
    "/tmp/workflows/platform/wf_ps_06",
    "/tmp/workflows/chained/wf_cc_01",
    "/tmp/workflows/subworkflows/SW-CRM-ReadOnly",
    "/tmp/workflows/subworkflows/SW-Finance-Admin"
)

foreach ($dir in $workflowDirs) {
    $exists = docker exec n8n-app sh -c "[ -d $dir ] && echo 'yes' || echo 'no'"
    if ($exists.Trim() -eq "yes") {
        Write-Host "   Importing: $dir"
        docker exec n8n-app n8n import:workflow --separate --input=$dir --userId $userId
    } else {
        Write-Host "   Skipping: $dir (not found)"
    }
}
Write-Host "   Workflows imported."

# ── Step 4: Get all workflow IDs ─────────────
Write-Host ""
Write-Host "4. Getting workflow IDs..."

$workflowIds = @()
$allWorkflows = docker exec n8n-postgres psql -U n8n -d n8n -t -A -c "SELECT id FROM public.workflow_entity;" 2>&1
if ($allWorkflows) {
    $workflowIds = $allWorkflows -split "`n" | Where-Object { $_.Trim() -ne "" }
}
Write-Host "   Found $($workflowIds.Count) workflows."

# ── Step 5: Publish workflows ────────────────
Write-Host ""
Write-Host "5. Publishing workflows..."

foreach ($wfId in $workflowIds) {
    $wfId = $wfId.Trim()
    if ($wfId) {
        Write-Host "   Publishing workflow: $wfId"
        docker exec n8n-app n8n publish:workflow --id=$wfId 2>&1 | Out-Null
    }
}
Write-Host "   All workflows published."

# ── Step 6: Restart n8n ──────────────────────
Write-Host ""
Write-Host "6. Restarting n8n..."
docker compose restart n8n
Write-Host "   n8n restarting..."

# ── Step 7: Wait for n8n to be ready again ───
Write-Host ""
Write-Host "7. Waiting for n8n to be ready..."
Start-Sleep -Seconds 5
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:5678/healthz" -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
    Start-Sleep -Seconds 2
}
if (-not $ready) {
    Write-Host "   WARNING: n8n may still be starting. Check: docker compose logs n8n"
} else {
    Write-Host "   n8n is ready."
}

# ── Summary ──────────────────────────────────
Write-Host ""
Write-Host "========================================"
Write-Host " Import & Publish Complete!"
Write-Host "========================================"
Write-Host ""
Write-Host "Imported workflows:"
foreach ($wfId in $workflowIds) {
    $wfId = $wfId.Trim()
    if ($wfId) {
        $name = docker exec n8n-postgres psql -U n8n -d n8n -t -A -c "SELECT name FROM public.workflow_entity WHERE id = '$wfId';" 2>&1
        Write-Host "  - $wfId : $($name.Trim())"
    }
}
Write-Host ""
Write-Host "Webhook URLs (after activation):"
Write-Host "  Reasoning Suite:"
Write-Host "    POST http://localhost:5678/webhook/wf-rs-01-baseline"
Write-Host "    POST http://localhost:5678/webhook/wf-rs-02"
Write-Host "    POST http://localhost:5678/webhook/wf-rs-03"
Write-Host "    POST http://localhost:5678/webhook/wf-rs-04"
Write-Host "    POST http://localhost:5678/webhook/wf-rs-05"
Write-Host "    POST http://localhost:5678/webhook/wf-rs-06"
Write-Host "    POST http://localhost:5678/webhook/wf-rs-01-guardrail"
Write-Host "  Platform Suite:"
Write-Host "    POST http://localhost:5678/webhook/wf-ps-01"
Write-Host "    POST http://localhost:5678/webhook/wf-ps-02"
Write-Host "    POST http://localhost:5678/webhook/wf-ps-03"
Write-Host "    POST http://localhost:5678/webhook/wf-ps-04"
Write-Host "    POST http://localhost:5678/webhook/wf-ps-05"
Write-Host "    POST http://localhost:5678/webhook/wf-ps-06-baseline"
Write-Host "  Composite/Chained:"
Write-Host "    POST http://localhost:5678/webhook/wf-cc-01"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Verify workflows are active in http://localhost:5678"
Write-Host "  2. Run smoke tests: python -m pytest tests/ -v"
Write-Host "  3. Run AVISE tests: python scripts/run_avise.py --slim"
Write-Host ""
