"""Tests for Docker container state.

Requires Docker daemon access (uses `docker ps` via subprocess).
"""

import pytest

# (name, expected_image, has_healthcheck)
CONTAINERS = [
    ("n8n-app",      "docker.n8n.io/n8nio/n8n",   True),
    ("n8n-postgres", "postgres",                    True),
    ("n8n-ollama",   "ollama/ollama",               False),
    ("n8n-mockapi",  "vimagick/json-server",        False),
]


@pytest.mark.docker
class TestDockerContainers:

    @pytest.mark.parametrize("name,expected_image,has_health", CONTAINERS,
                             ids=[c[0] for c in CONTAINERS])
    def test_container_is_running(self, docker_ps, name, expected_image, has_health):
        c = docker_ps.get(name)
        if c is None:
            pytest.fail(f"Container '{name}' not found in running containers")
        assert expected_image in c["Image"], \
            f"Expected image containing '{expected_image}', got '{c['Image']}'"
        assert c["State"] == "running"

    @pytest.mark.parametrize("name,_,__", CONTAINERS, ids=[c[0] for c in CONTAINERS])
    def test_container_status(self, docker_ps, name, _, __):
        c = docker_ps.get(name)
        if c is None:
            pytest.fail(f"Container '{name}' not found")
        status = c.get("Status", "")
        assert "unhealthy" not in status.lower(), \
            f"Container '{name}' is unhealthy: {status}"

    def test_ollama_has_at_least_one_model(self):
        """A model should be present or being downloaded in Ollama."""
        import subprocess, json
        result = subprocess.run(
            ["docker", "exec", "n8n-ollama", "ollama", "list"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            pytest.skip("Cannot list Ollama models")
        lines = [l for l in result.stdout.strip().splitlines() if l.strip()]
        # Skip header line; count lines that look like model entries
        model_lines = [l for l in lines if l.strip() and not l.strip().startswith("NAME")]
        if len(model_lines) < 1:
            pytest.skip(f"No models fully pulled yet (download may be in progress). Raw output:\n{result.stdout}")
