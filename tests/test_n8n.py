"""Tests for the n8n application API and workflow state."""

import pytest


@pytest.mark.n8n
class TestN8nApi:

    def test_healthz(self, http, n8n_url):
        r = http.get(f"{n8n_url}/healthz", timeout=5)
        assert r.status_code == 200

    def test_workflows_imported(self, n8n_workflows):
        assert len(n8n_workflows) >= 2, \
            f"Expected ≥2 workflows imported, found {len(n8n_workflows)}:\n" \
            + "\n".join(f"  {w['name']} ({'active' if w['active'] else 'inactive'})"
                        for w in n8n_workflows)

    def test_wf01_baseline_exists(self, n8n_workflows):
        matching = [w for w in n8n_workflows if "wf-01" in w["name"].lower()
                    and "baseline" in w["name"].lower()]
        assert len(matching) >= 1, \
            "WF-01 baseline workflow not found in imported workflows"
        wf = matching[0]
        assert wf["active"], f"WF-01 baseline exists but is NOT active: {wf}"

    def test_wf01_guardrail_exists(self, n8n_workflows):
        matching = [w for w in n8n_workflows if "wf-01" in w["name"].lower()
                    and "guardrail" in w["name"].lower()]
        assert len(matching) >= 1, \
            "WF-01 guardrail workflow not found in imported workflows"
        wf = matching[0]
        assert wf["active"], f"WF-01 guardrail exists but is NOT active: {wf}"


