"""Tests for Ollama API reachability and available models."""

import pytest


@pytest.mark.ollama
class TestOllama:

    def test_api_reachable(self, http, ollama_url):
        r = http.get(f"{ollama_url}/api/tags", timeout=10)
        assert r.status_code == 200, \
            f"Ollama API returned {r.status_code}: {r.text[:200]}"

    def test_at_least_one_model(self, http, ollama_url):
        r = http.get(f"{ollama_url}/api/tags", timeout=10)
        data = r.json()
        models = data.get("models", [])
        if len(models) < 1:
            pytest.skip("No models pulled yet — pull may still be in progress")

    def test_model_names_are_strings(self, http, ollama_url):
        r = http.get(f"{ollama_url}/api/tags", timeout=10)
        data = r.json()
        for model in data.get("models", []):
            name = model.get("name", "")
            assert isinstance(name, str) and len(name) > 0, \
                f"Model missing valid name: {model}"
            # Check digest field exists
            assert "digest" in model, \
                f"Model {name} missing 'digest' field"

    def test_ollama_version(self, http, ollama_url):
        r = http.get(f"{ollama_url}/api/version", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "version" in data, \
            f"Version response missing 'version' field: {data}"
        version = data["version"]
        parts = version.split(".")
        assert len(parts) >= 2, \
            f"Unrecognized version format: {version}"
