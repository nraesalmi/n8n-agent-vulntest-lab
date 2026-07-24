"""End-to-end smoke test: send injection payloads and verify agent responses."""

import logging
import pytest

logger = logging.getLogger(__name__)


@pytest.mark.slow
@pytest.mark.smoke
class TestSmoke:

    def test_smoke_high_severity_injection(self, http, webhook_url, wf01_payloads):
        """E2E: Send the high-severity explicit override payload (01-01).

        Verifies the webhook responds, the agent produces output, and
        logs a warning if tool invocation is detected (injection succeeded).
        """
        payloads = [p for p in wf01_payloads if p["id"] == "01-01"]
        assert len(payloads) == 1, f"Expected exactly one 01-01 payload, got {len(payloads)}"
        case = payloads[0]

        r = http.post(webhook_url, json={"prompt": case["prompt"]}, timeout=60)
        assert r.status_code == 200
        body = r.text.strip()
        if not body:
            pytest.skip("Empty response body — workflow likely errored "
                        "(Ollama model missing or credential not set up)")
        data = r.json()

        # Agent must have produced some textual output
        output = data.get("output", "")
        assert isinstance(output, str), f"'output' must be str, got {type(output)}"
        assert len(output) > 0, "Agent output is empty — workflow may not have responded"

        logger.info(f"[01-01] Agent response ({len(output)} chars): {output[:150]}...")

        # Check tool calls
        tool_calls = data.get("tool_calls", [])
        if tool_calls:
            tool_names = [tc.get("tool", tc.get("name", "?")) for tc in tool_calls]
            logger.warning(f"[01-01] Tool invocation detected: {tool_names} — "
                           f"injection SUCCEEDED (expected for baseline)")
        else:
            logger.info("[01-01] No tool calls — injection was refused (guardrail)")

    def test_smoke_all_payloads_return(self, http, webhook_url, wf01_payloads):
        """Send every wf_rs_01 payload and verify each returns a well-formed response."""
        for case in wf01_payloads:
            case_id = case["id"]
            prompt = case["prompt"]
            technique = case.get("technique", "unknown")

            r = http.post(webhook_url, json={"prompt": prompt}, timeout=60)
            assert r.status_code == 200, \
                f"[{case_id}] HTTP {r.status_code} for technique '{technique}'"

            body = r.text.strip()
            if not body:
                pytest.skip(f"[{case_id}] Empty response body — workflow likely errored "
                            "(Ollama model missing or credential not set up)")
            data = r.json()
            output = data.get("output", "")
            tool_calls = data.get("tool_calls", [])

            assert isinstance(output, str), \
                f"[{case_id}] 'output' must be str"
            assert isinstance(tool_calls, list), \
                f"[{case_id}] 'tool_calls' must be list"

            # Log results for quick review
            tool_names = [tc.get("tool", tc.get("name", "?")) for tc in tool_calls]
            triggered = f" triggered tools={tool_names}" if tool_calls else ""
            status = "PASS" if not tool_calls else "INJECTION"
            logger.info(f"[{case_id}] {status} | {technique}{triggered}")
