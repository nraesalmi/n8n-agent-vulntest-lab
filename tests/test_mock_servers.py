"""Tests for mock service (:8080) and attacker listener (:9999) endpoints."""

import pytest


# ── Mock Server (:8080) ──────────────────────────────────────

MOCK_ENDPOINTS = [
    "/health",
    "/faq",
    "/poisoned-page",
    "/calendar",
    "/db",
    "/company-info",
    "/api/data",
    "/search?q=test",
    "/_log",
]

MOCK_POST_ENDPOINTS = [
    ("/notify",     {"test": True}),
    ("/send-reply", {"ticket_id": 1, "message": "test"}),
    ("/escalate",   {"ticket_id": 1}),
    ("/send-email", {"to": "test@example.com", "subject": "test"}),
    ("/slack",      {"channel": "#test", "message": "hello"}),
    ("/db/write",   {"collection": "test", "data": {"key": "value"}}),
    ("/synthesize", {"sources": ["test"]}),
    ("/_clear",     {}),
]


@pytest.mark.mock
class TestMockServer:

    @pytest.mark.parametrize("path", MOCK_ENDPOINTS,
                             ids=[p.split("?")[0].strip("/").replace("/", "_")
                                  for p in MOCK_ENDPOINTS])
    def test_mock_get_endpoint(self, http, mock_url, path):
        r = http.get(f"{mock_url}{path}", timeout=5)
        assert r.status_code == 200, \
            f"GET {path} returned {r.status_code}: {r.text[:200]}"

    @pytest.mark.parametrize("path,body", MOCK_POST_ENDPOINTS,
                             ids=[p[0].strip("/") for p in MOCK_POST_ENDPOINTS])
    def test_mock_post_endpoint(self, http, mock_url, path, body):
        r = http.post(f"{mock_url}{path}", json=body, timeout=5)
        assert r.status_code == 200, \
            f"POST {path} returned {r.status_code}: {r.text[:200]}"
        data = r.json()
        assert isinstance(data, dict), "Response must be a JSON object"

    def test_faq_returns_expected_structure(self, http, mock_url):
        r = http.get(f"{mock_url}/faq", timeout=5)
        data = r.json()
        assert "faqs" in data
        assert isinstance(data["faqs"], list)
        assert len(data["faqs"]) >= 1
        for faq in data["faqs"]:
            assert "q" in faq
            assert "a" in faq

    def test_poisoned_page_contains_injection(self, http, mock_url):
        """The poisoned page should contain hidden injection payloads for wf_02."""
        r = http.get(f"{mock_url}/poisoned-page", timeout=5)
        html = r.text
        assert "IGNORE PREVIOUS INSTRUCTIONS" in html, \
            "Poisoned page missing injection comment"
        assert "exfiltration" in html.lower(), \
            "Poisoned page missing exfiltration reference"


# ── Attacker Listener (:9999) ────────────────────────────────

ATTACKER_ENDPOINTS = ["/", "/_captured", "/_clear"]


@pytest.mark.mock
class TestAttackerListener:

    @pytest.mark.parametrize("path", ATTACKER_ENDPOINTS)
    def test_attacker_endpoint(self, http, exfil_url, path):
        r = http.get(f"{exfil_url}{path}", timeout=5)
        assert r.status_code == 200, \
            f"GET :9999{path} returned {r.status_code}: {r.text[:200]}"

    def test_attacker_catch_all_post(self, http, exfil_url):
        r = http.post(exfil_url, json={"simulated": "exfil_data"}, timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "received"

    def test_attacker_view_and_clear(self, http, exfil_url):
        r = http.get(f"{exfil_url}/_captured", timeout=5)
        assert r.status_code == 200
        captured = r.json()
        assert isinstance(captured, list)

        r = http.post(f"{exfil_url}/_clear", timeout=5)
        assert r.status_code == 200
