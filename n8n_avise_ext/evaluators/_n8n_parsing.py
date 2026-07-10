"""Shared parsing helper for n8n webhook response JSON."""

import json
import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


def parse_n8n_response(response: str) -> Tuple[str, str, List[Dict[str, Any]]]:
    """Parse the n8n Respond-to-Webhook JSON payload.

    Returns (user_prompt, ai_response, tool_calls). On parse failure returns
    ("", response, []) so evaluators degrade to treating `response` as plain
    text rather than raising.
    """
    try:
        data = json.loads(response)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("Could not parse n8n response as JSON: %s", e)
        return "", response, []

    return (
        data.get("userPrompt", "") or "",
        data.get("aiResponse", "") or "",
        data.get("toolCalls", []) or [],
    )
