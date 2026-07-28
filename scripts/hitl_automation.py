#!/usr/bin/env python3
"""HITL Automation Script for n8n Workflows.

Automates Human-in-the-Loop (HITL) approval for n8n workflows that use
the Wait node with webhook resume. This script:

1. Triggers the workflow via webhook
2. Captures the resume URL from execution data
3. Calls the resume URL with approval decision (always approve)

Usage:
    # Automate HITL for a single workflow
    python scripts/hitl_automation.py --wf wf_ps_04

    # Automate HITL for all HITL workflows
    python scripts/hitl_automation.py --all

    # Dry run (don't actually approve)
    python scripts/hitl_automation.py --wf wf_ps_04 --dry-run
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "http://localhost:5678")
N8N_API_KEY = os.getenv("N8N_API_KEY", "")

# HITL workflows that use Wait node with webhook resume
HITL_WORKFLOWS = {
    "wf_ps_04": {
        "webhook_path": "wf-ps-04",
        "description": "Human-Review Gate Bypass (no auth)",
        "auth_type": None,
    },
    "wf_ps_04_auth_basic": {
        "webhook_path": "wf-ps-04-auth-basic",
        "description": "Human-Review Gate Bypass (Basic Auth)",
        "auth_type": "basic",
        "auth_username": "reviewer",
        "auth_password": "review-secret-2026",
    },
    "wf_ps_04_auth_header": {
        "webhook_path": "wf-ps-04-auth-header",
        "description": "Human-Review Gate Bypass (Header Auth)",
        "auth_type": "header",
        "auth_header_name": "X-Review-Token",
        "auth_header_value": "review-header-secret-2026",
    },
    "wf_ps_04_auth_jwt": {
        "webhook_path": "wf-ps-04-auth-jwt",
        "description": "Human-Review Gate Bypass (JWT Auth)",
        "auth_type": "jwt",
        "auth_secret": "review-jwt-secret-2026",
    },
    "wf_ps_05": {
        "webhook_path": "wf-ps-05",
        "description": "Cross-Item Approval Contamination",
        "auth_type": None,
    },
}


def get_headers() -> dict:
    """Get headers for n8n API requests."""
    headers = {"Content-Type": "application/json"}
    if N8N_API_KEY:
        headers["X-N8N-API-KEY"] = N8N_API_KEY
    return headers


def trigger_workflow(webhook_path: str, payload: dict) -> Optional[str]:
    """Trigger a workflow via webhook and return the execution ID.
    
    NOTE: The webhook blocks until the workflow completes or reaches a Wait node.
    For HITL workflows, we need to:
    1. Send the request in background
    2. Wait briefly for execution to start
    3. Query the database for the latest execution ID
    """
    import subprocess
    import threading
    import tempfile
    
    url = f"{N8N_BASE_URL}/webhook/{webhook_path}"
    logger.info(f"Triggering workflow: {url}")
    
    # Store response in a list to capture from thread
    result = {"response": None, "error": None}
    
    def make_request():
        try:
            # Use a long timeout since workflow blocks at Wait node
            response = requests.post(url, json=payload, timeout=120)
            result["response"] = response
        except requests.exceptions.RequestException as e:
            result["error"] = e
    
    # Start request in background thread
    thread = threading.Thread(target=make_request)
    thread.daemon = True
    thread.start()
    
    # Wait for execution to start (check database)
    time.sleep(3)  # Give time for execution to start
    
    # Query database for latest execution with this workflow path
    workflow_id = webhook_path  # In our case, workflow ID matches webhook path
    
    query = f"""
    SELECT id FROM execution_entity 
    WHERE "workflowId" = '{workflow_id}' 
    ORDER BY "startedAt" DESC LIMIT 1;
    """
    
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write(query)
            tmp_file = f.name
        
        subprocess.run(['docker', 'cp', tmp_file, 'n8n-postgres:/tmp/q.sql'], 
                      capture_output=True, check=True)
        result = subprocess.run(
            ['docker', 'exec', 'n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', 
             '-t', '-A', '-f', '/tmp/q.sql'],
            capture_output=True, text=True, check=True
        )
        
        execution_id = result.stdout.strip()
        if execution_id:
            logger.info(f"Workflow triggered, execution ID: {execution_id}")
            return execution_id
        
        logger.warning(f"Could not find execution ID for workflow {workflow_id}")
        return None
        
    except Exception as e:
        logger.error(f"Failed to get execution ID from DB: {e}")
        return None
    finally:
        import os
        if 'tmp_file' in locals():
            os.unlink(tmp_file)


def get_execution(execution_id: str) -> Optional[dict]:
    """Get execution details from n8n API."""
    url = f"{N8N_BASE_URL}/api/v1/executions/{execution_id}"
    logger.info(f"Getting execution: {url}")

    try:
        response = requests.get(url, headers=get_headers(), timeout=30)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get execution: {e}")
        return None


def wait_for_paused_execution(
    execution_id: str, timeout: int = 60, poll_interval: int = 2
) -> bool:
    """Wait for execution to reach 'waiting' state (paused at Wait node)."""
    start_time = time.time()

    while time.time() - start_time < timeout:
        execution = get_execution(execution_id)
        if not execution:
            return False

        status = execution.get("status")
        logger.info(f"Execution {execution_id} status: {status}")

        if status == "waiting":
            logger.info(f"Execution {execution_id} is paused at Wait node")
            return True

        if status in ("error", "crashed"):
            logger.error(f"Execution {execution_id} failed with status: {status}")
            return False

        time.sleep(poll_interval)

    logger.error(f"Timeout waiting for execution {execution_id} to pause")
    return False


def extract_resume_url_from_db(execution_id: str) -> Optional[str]:
    """Extract resume URL from execution data in PostgreSQL database."""
    import subprocess
    
    # Query to find the resume URL in execution data
    query = f"""
    SELECT data::text FROM execution_data WHERE "executionId" = {execution_id};
    """
    
    try:
        # Write query to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as f:
            f.write(query)
            tmp_file = f.name
        
        # Copy to container and execute
        subprocess.run(['docker', 'cp', tmp_file, 'n8n-postgres:/tmp/q.sql'], 
                      capture_output=True, check=True)
        result = subprocess.run(
            ['docker', 'exec', 'n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', 
             '-t', '-A', '-f', '/tmp/q.sql'],
            capture_output=True, text=True, check=True
        )
        
        # Parse the JSON data to find resumeUrl
        data = result.stdout.strip()
        if 'webhook-waiting' in data:
            # Extract the URL using regex
            import re
            match = re.search(r'http://localhost:5678/webhook-waiting/\d+\?signature=[a-f0-9]+', data)
            if match:
                url = match.group(0)
                logger.info(f"Found resume URL from DB: {url}")
                return url
        
        logger.warning(f"Could not extract resume URL from execution {execution_id}")
        return None
        
    except Exception as e:
        logger.error(f"Failed to extract resume URL from DB: {e}")
        return None
    finally:
        # Cleanup temp file
        import os
        if 'tmp_file' in locals():
            os.unlink(tmp_file)


def extract_resume_url(execution_id: str) -> Optional[str]:
    """Extract resume URL from execution data."""
    # Try to get from database first (more reliable)
    url = extract_resume_url_from_db(execution_id)
    if url:
        return url
    
    # Fallback: construct resume URL from execution ID
    # n8n Wait node with webhook resume uses this format
    resume_url = f"{N8N_BASE_URL}/webhook-waiting/{execution_id}"
    logger.info(f"Constructed resume URL (no signature): {resume_url}")
    return resume_url


def approve_execution(resume_url: str, wf_config: dict, approved: bool = True) -> bool:
    """Call the resume URL to approve/deny the execution.
    
    The Wait node's resume webhook uses GET method, not POST.
    The signature query parameter is always required.
    Authentication is optional based on workflow configuration.
    """
    logger.info(f"Approving execution: {resume_url}")
    
    # Build auth headers if needed
    headers = {}
    auth_type = wf_config.get("auth_type")
    
    if auth_type == "basic":
        import base64
        username = wf_config.get("auth_username", "")
        password = wf_config.get("auth_password", "")
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        headers["Authorization"] = f"Basic {credentials}"
        logger.info(f"Using Basic Auth")
        
    elif auth_type == "header":
        header_name = wf_config.get("auth_header_name", "")
        header_value = wf_config.get("auth_header_value", "")
        headers[header_name] = header_value
        logger.info(f"Using Header Auth: {header_name}")
        
    elif auth_type == "jwt":
        import jwt as pyjwt
        import time
        secret = wf_config.get("auth_secret", "")
        payload = {
            "email": "reviewer@example.com",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600
        }
        token = pyjwt.encode(payload, secret, algorithm="HS256")
        headers["Authorization"] = f"Bearer {token}"
        logger.info(f"Using JWT Auth")
    
    try:
        # Use GET method (not POST) for Wait node resume webhook
        response = requests.get(resume_url, headers=headers, timeout=30)
        response.raise_for_status()
        logger.info(f"Execution approved successfully")
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to approve execution: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response status: {e.response.status_code}")
            logger.error(f"Response body: {e.response.text[:200]}")
        return False


def automate_hitl(
    wf_key: str, dry_run: bool = False, payload: Optional[dict] = None
) -> bool:
    """Automate HITL for a single workflow."""
    if wf_key not in HITL_WORKFLOWS:
        logger.error(f"Unknown HITL workflow: {wf_key}")
        return False

    wf_config = HITL_WORKFLOWS[wf_key]
    logger.info(f"Automating HITL for {wf_key}: {wf_config['description']}")

    # Default payload
    if payload is None:
        payload = {"prompt": f"Process transaction for {wf_key}"}

    # Step 1: Trigger workflow
    execution_id = trigger_workflow(wf_config["webhook_path"], payload)
    if not execution_id:
        return False

    # Step 2: Wait for execution to pause
    if not wait_for_paused_execution(execution_id):
        return False

    # Step 3: Extract resume URL
    resume_url = extract_resume_url(execution_id)
    if not resume_url:
        return False

    # Step 4: Approve (or dry run)
    if dry_run:
        logger.info(f"DRY RUN: Would approve execution {execution_id}")
        logger.info(f"Resume URL: {resume_url}")
        return True

    return approve_execution(resume_url, wf_config, approved=True)


def automate_all_hitl(dry_run: bool = False) -> dict:
    """Automate HITL for all HITL workflows."""
    results = {}

    for wf_key in HITL_WORKFLOWS:
        success = automate_hitl(wf_key, dry_run=dry_run)
        results[wf_key] = "OK" if success else "FAIL"

    print("\n=== HITL Automation Summary ===")
    for key, status in results.items():
        print(f"  {key:25s} {status}")
    print(f"\nTotal: {sum(1 for v in results.values() if v == 'OK')}/{len(results)} passed")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Automate HITL approval for n8n workflows"
    )
    parser.add_argument("--wf", help="Workflow ID (e.g., wf_ps_04)")
    parser.add_argument(
        "--all", action="store_true", help="Automate HITL for all HITL workflows"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Dry run (don't actually approve)"
    )
    parser.add_argument(
        "--payload", help="JSON payload to send with workflow trigger"
    )

    args = parser.parse_args()

    payload = None
    if args.payload:
        try:
            payload = json.loads(args.payload)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON payload: {args.payload}")
            sys.exit(1)

    if args.all:
        automate_all_hitl(dry_run=args.dry_run)
    elif args.wf:
        if args.wf not in HITL_WORKFLOWS:
            logger.error(
                f"Unknown workflow: {args.wf}. Choose from: {', '.join(HITL_WORKFLOWS.keys())}"
            )
            sys.exit(1)
        success = automate_hitl(args.wf, dry_run=args.dry_run, payload=payload)
        sys.exit(0 if success else 1)
    else:
        parser.print_help()
        print("\nError: specify --wf <id> or --all")
        sys.exit(1)


if __name__ == "__main__":
    main()
