"""Tests for json-server (:3000) API."""

import pytest


JSON_SERVER_ENDPOINTS = [
    "/",
    "/documents",
]


@pytest.mark.json_server
class TestJsonServer:

    @pytest.mark.parametrize("path", JSON_SERVER_ENDPOINTS)
    def test_endpoint_reachable(self, http, json_server_url, path):
        r = http.get(f"{json_server_url}{path}", timeout=5)
        assert r.status_code == 200, \
            f"GET :3000{path} returned {r.status_code}"

    def test_documents_have_expected_structure(self, http, json_server_url):
        r = http.get(f"{json_server_url}/documents", timeout=5)
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1, "Expected at least 1 document"
        doc = data[0]
        assert "id" in doc, f"Document missing 'id': {doc}"
        assert "title" in doc, f"Document missing 'title': {doc}"
        assert "content" in doc, f"Document missing 'content': {doc}"
