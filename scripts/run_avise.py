#!/usr/bin/env python3
"""AVISE runner for n8n workflow security testing.

Registers custom n8n components with AVISE and runs security evaluation tests
against n8n webhook-triggered AI agent workflows.

Usage:
    # Run a single workflow
    python scripts/run_avise.py --wf wf_01 --variant baseline

    # Run all workflows
    python scripts/run_avise.py --all

    # Run with custom connector/SET configs
    python scripts/run_avise.py --connectorconf <path> --SETconf <path>

    # Run without evaluation model (default uses no eval model)
    python scripts/run_avise.py --wf wf_01 --variant baseline --no-eval

    # Run a slim subset of test cases (one per vulnerability category)
    python scripts/run_avise.py --wf wf_01 --variant baseline --slim

    # Specify report format and output directory
    python scripts/run_avise.py --all --format html --output reports/
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Add project root to Python path so avise is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import custom modules FIRST to register them with AVISE registries
import n8n_avise_ext.connectors  # noqa: F401 (registers n8n-webhook-lm connector)
import n8n_avise_ext.evaluators  # noqa: F401 (registers custom evaluators)
import n8n_avise_ext.sets  # noqa: F401 (registers n8n_workflow SET)

from avise.cli import main as avise_main
from avise.utils import ReportFormat

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

VARIANTS = ["baseline", "guardrail"]
WORKFLOWS = [f"wf_{i:02d}" for i in range(1, 11)]
CONFIG_DIR = PROJECT_ROOT / "n8n_avise_ext" / "configs"
CONNECTOR_DIR = CONFIG_DIR / "connector"
SET_DIR = CONFIG_DIR / "SET"


def build_args(
    wf_key: str,
    variant: str,
    report_format: str = "html",
    output_dir: str = "avise-reports",
    runs: int = 1,
    no_eval: bool = True,
    slim: bool = False,
) -> list:
    """Build AVISE CLI argument list for a single workflow test."""
    connector_conf = CONNECTOR_DIR / f"{wf_key}_{variant}.json"
    set_filename = f"{wf_key}_slim.json" if slim else f"{wf_key}.json"
    set_conf = SET_DIR / set_filename

    if not connector_conf.exists():
        logger.error(f"Connector config not found: {connector_conf}")
        return None
    if not set_conf.exists():
        logger.error(f"SET config not found: {set_conf}")
        return None

    args = [
        "--SET", "n8n_workflow",
        "--connectorconf", str(connector_conf),
        "--SETconf", str(set_conf),
        "--format", report_format,
        "--output", output_dir,
        "--runs", str(runs),
    ]

    if no_eval:
        args.extend(["--elm", "False"])
    else:
        args.extend(["--elm", "True"])

    return args


def run_single(wf_key: str, variant: str, slim: bool = False, **kwargs):
    """Run AVISE for a single workflow variant."""
    args = build_args(wf_key, variant, slim=slim, **kwargs)
    if args is None:
        return False

    try:
        logger.info(f"Running {wf_key} ({variant})...")
        avise_main(args)
        logger.info(f"Completed {wf_key} ({variant})")
        return True
    except SystemExit:
        return True
    except Exception as e:
        logger.error(f"Failed {wf_key} ({variant}): {e}")
        return False


def run_all(**kwargs):
    """Run AVISE for all workflow variants."""
    results = {}
    for wf_key in WORKFLOWS:
        for variant in VARIANTS:
            success = run_single(wf_key, variant, **kwargs)
            results[f"{wf_key}_{variant}"] = "OK" if success else "FAIL"

    print("\n=== Summary ===")
    for key, status in results.items():
        print(f"  {key:25s} {status}")
    print(f"\nTotal: {sum(1 for v in results.values() if v == 'OK')}/{len(results)} passed")


def main():
    parser = argparse.ArgumentParser(
        description="Run AVISE security tests against n8n workflows"
    )
    parser.add_argument("--wf", help="Workflow ID (e.g., wf_01)")
    parser.add_argument("--variant", choices=VARIANTS, default="baseline",
                        help="Workflow variant (default: baseline)")
    parser.add_argument("--all", action="store_true",
                        help="Run all workflows")
    parser.add_argument("--format", choices=["json", "html", "md"], default="html",
                        help="Report format (default: html)")
    parser.add_argument("--output", "-o", default="avise-reports",
                        help="Output directory for reports")
    parser.add_argument("--runs", "-r", type=int, default=1,
                        help="Number of runs per test case (default: 1)")
    parser.add_argument("--no-eval", action="store_true", default=True,
                        help="Disable evaluation language model (default: True)")
    parser.add_argument("--with-eval", action="store_true",
                        help="Enable evaluation language model (requires ELM)")
    parser.add_argument("--slim", action="store_true",
                        help="Run a slim subset of test cases (one per vulnerability category)")

    args = parser.parse_args()

    kwargs = {
        "report_format": args.format,
        "output_dir": args.output,
        "runs": args.runs,
        "no_eval": not args.with_eval,
        "slim": args.slim,
    }

    if args.all:
        run_all(**kwargs)
    elif args.wf:
        if args.wf not in WORKFLOWS:
            logger.error(f"Unknown workflow: {args.wf}. Choose from: {', '.join(WORKFLOWS)}")
            sys.exit(1)
        run_single(args.wf, args.variant, **kwargs)
    else:
        parser.print_help()
        print("\nError: specify --wf <id> or --all")
        sys.exit(1)


if __name__ == "__main__":
    main()
