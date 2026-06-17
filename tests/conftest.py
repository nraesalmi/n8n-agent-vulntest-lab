"""Shared fixtures for n8n security lab integration tests."""

import json
import re
import subprocess
import pytest
import requests


# ── URL Fixtures ─────────────────────────────────────────────

@pytest.fixture(scope="session")
def n8n_url():
    return "http://localhost:5678"


@pytest.fixture(scope="session")
def mock_url():
    return "http://localhost:8080"


@pytest.fixture(scope="session")
def ollama_url():
    return "http://localhost:11434"


@pytest.fixture(scope="session")
def json_server_url():
    return "http://localhost:3000"


@pytest.fixture(scope="session")
def exfil_url():
    return "http://localhost:9999"


# ── HTTP Session ─────────────────────────────────────────────

@pytest.fixture(scope="session")
def http():
    session = requests.Session()
    session.headers.update({"User-Agent": "n8n-lab-tests/1.0"})
    session.timeout = 10
    return session


# ── Webhook URL builder (parameterized) ─────────────────────

@pytest.fixture
def webhook_url(request, n8n_url):
    marker = request.node.get_closest_marker("webhook")
    if marker:
        path = marker.kwargs.get("path", "wf-01-baseline")
    else:
        path = "wf-01-baseline"
    return f"{n8n_url}/webhook/{path}"


# ── Docker helper (subprocess, no extra dep) ─────────────────

@pytest.fixture(scope="session")
def docker_ps():
    """Return parsed output of `docker ps --format json` once per session."""
    result = subprocess.run(
        ["docker", "ps", "--format", "{{json .}}"],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        pytest.skip("Docker daemon not reachable")
    containers = {}
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        c = json.loads(line)
        containers[c["Names"]] = c
    return containers


# ── Workflow list from n8n CLI ───────────────────────────────

@pytest.fixture(scope="session")
def n8n_workflows():
    """Return list of workflow info dicts from `n8n list:workflow` output.

    The CLI writes log lines like:
      2026-06-16T07:54:19.576Z | info  | WORKFLOW_ID|WF-01: ... (Baseline) (AVISE) {"file":"workflow.js"}
    """
    result = subprocess.run(
        ["docker", "exec", "n8n-app", "n8n", "list:workflow"],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        pytest.skip("Cannot list n8n workflows via CLI")
    workflows = []
    wf_pattern = re.compile(
        r"\w+\s*\|\s*\w+\s*\|\s*(\w+)\|(.+?)\s*\{"
    )
    for line in result.stdout.strip().splitlines():
        m = wf_pattern.search(line)
        if m:
            workflow_id = m.group(1)
            name = m.group(2).strip()
            workflows.append({
                "id": workflow_id,
                "name": name,
                "active": True,  # CLI output doesn't provide active flag; assume imported workflows are active
            })
    return workflows


# ── Test payloads from SET config ────────────────────────────

@pytest.fixture(scope="session")
def wf01_payloads():
    """Load all wf_01 test cases from the SET config JSON."""
    path = __import__("pathlib").Path(__file__).resolve().parent.parent \
        / "n8n_avise_ext" / "configs" / "SET" / "wf_01.json"
    with open(path, encoding="utf-8") as f:
        config = json.load(f)
    return config.get("sets", [])


# ── Connector config ─────────────────────────────────────────

@pytest.fixture(scope="session")
def connector_config():
    """Load the wf_01 baseline connector config."""
    path = __import__("pathlib").Path(__file__).resolve().parent.parent \
        / "n8n_avise_ext" / "configs" / "connector" / "wf_01_baseline.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)
