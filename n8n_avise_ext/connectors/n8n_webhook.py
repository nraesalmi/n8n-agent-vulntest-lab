"""AVISE Connector for n8n Webhook Trigger workflows.

POSTs attack payloads to n8n webhook endpoints and parses the agent response
including tool call history.
"""

import json
import logging
import requests

from avise.registry import connector_registry

logger = logging.getLogger(__name__)


@connector_registry.register("n8n-webhook-lm")
class N8nWebhookLMConnector:
    """Connector for n8n webhook-triggered AI agent workflows.

    Configuration (connector JSON):
        webhook_url (str): n8n webhook URL (e.g. http://localhost:5678/webhook/wf-rs-01-baseline)
        method (str): HTTP method (default POST)
        input_field (str): JSON body field name for the prompt (default "prompt")
        response_field (str): JSON response field name for agent output text (default "output")
        tool_calls_field (str): JSON response field name for tool call list (default "tool_calls")
        headers (dict): Optional extra HTTP headers
        timeout (int): Request timeout in seconds (default 60)
    """

    name = "n8n-webhook-lm"

    def __init__(self, config: dict, evaluation: bool = False):
        if evaluation:
            target = config.get("eval_model", {})
        else:
            target = config.get("target_model", {})

        self.webhook_url = target.get("webhook_url", "")
        self.method = target.get("method", "POST").upper()
        self.input_field = target.get("input_field", "prompt")
        self.response_field = target.get("response_field", "output")
        self.tool_calls_field = target.get("tool_calls_field", "tool_calls")
        self.timeout = target.get("timeout", 60)
        self.headers = target.get("headers") or {}
        self.model = target.get("name", "n8n-workflow")

        if not self.webhook_url:
            raise ValueError(
                "n8n webhook connector requires 'webhook_url' in config"
            )

        if "Content-Type" not in self.headers:
            self.headers["Content-Type"] = "application/json"

        logger.info(f"  n8n Webhook Connector Initialized")
        logger.info(f"  Webhook URL: {self.webhook_url}")
        logger.info(f"  Input field: '{self.input_field}'")
        logger.info(f"  Response field: '{self.response_field}'")

    def generate(self, data: dict) -> dict:
        """Send a prompt to the n8n webhook and return the agent response.

        Args:
            data: Dictionary with at least a "prompt" key (or the configured input_field).

        Returns:
            dict with:
                - "response": Agent output text
                - "tool_calls": List of tool call objects (may be empty)
                - "raw": The full webhook response body
        """
        prompt_text = data.get("prompt", data.get(self.input_field, ""))
        body = {self.input_field: prompt_text}

        try:
            response = requests.post(
                url=self.webhook_url,
                data=json.dumps(body),
                headers=self.headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.Timeout:
            raise RuntimeError(
                f"n8n webhook timed out after {self.timeout}s: {self.webhook_url}"
            )
        except requests.ConnectionError:
            raise RuntimeError(
                f"Cannot connect to n8n webhook: {self.webhook_url}"
            )
        except requests.HTTPError as e:
            raise RuntimeError(
                f"n8n webhook returned HTTP {e.response.status_code}: {e.response.text}"
            )

        response.encoding = "utf-8"
        try:
            result = response.json()
        except ValueError:
            result = {"output": response.text, "toolCalls": []}

        if isinstance(result, list):
            result = result[0] if result else {}

        elif not isinstance(result, dict):
            result = {"output": str(result), "toolCalls": []}

        # Return the full webhook JSON as the response string so evaluators
        # can parse it via parse_n8n_response() for userPrompt/aiResponse/toolCalls.
        tool_calls = result.get("toolCalls", result.get(self.tool_calls_field, []))

        return {
            "response": json.dumps(result),
            "tool_calls": tool_calls if isinstance(tool_calls, list) else [],
            "raw": result,
        }

    def status_check(self) -> bool:
        """Verify the n8n webhook endpoint is reachable."""
        try:
            response = requests.get(
                self.webhook_url.rsplit("/webhook/", 1)[0] + "/healthz",
                timeout=10,
            )
            if response.status_code == 200:
                logger.info(f"n8n health check passed at {self.webhook_url}")
                return True
        except Exception:
            pass

        # Fallback: try POST with a test payload
        try:
            resp = requests.post(
                self.webhook_url,
                data=json.dumps({self.input_field: "__status_check__"}),
                headers=self.headers,
                timeout=10,
            )
            if resp.status_code in (200, 201, 202):
                logger.info(f"n8n webhook reachable at {self.webhook_url}")
                return True
        except Exception as e:
            raise ConnectionError(
                f"n8n webhook not reachable at {self.webhook_url}: {e}"
            )

        return True
