# AI Workflow Security Research Lab

**Security of low-code AI agent workflow platforms under prompt-injection and execution-graph manipulation**

A controlled experimental framework for studying how prompt-injection-class attacks and platform-specific execution vulnerabilities propagate through node-based AI workflow systems (n8n), where LLM outputs are compiled into executable workflow graphs with external side effects. Contains **10 attack scenarios** (baseline / basic-guardrail / custom-guardrail variants) and **1 reusable security sub-workflow scaffold**, mapped against both the OWASP Top 10 for LLM Applications and the OWASP Top 10 for Agentic Applications.


<img width="1280" height="640" alt="n8n-lab-banner" src="https://github.com/user-attachments/assets/fd0c164e-00c1-443c-aad6-3c5fd3330a3a" />

---

## Research Context

### Premise

Low-code automation systems such as n8n expose a fundamentally different attack surface compared to conversational chatbots. LLM outputs in these systems are not merely rendered as text — they are compiled into executable workflow graphs with real external side effects: database writes, HTTP calls, tool invocations, and control-flow decisions.

While prompt injection is well-studied in chat-based, code-first agent frameworks (LangChain, AutoGPT), that literature assumes an orchestration layer the researcher can inspect and instrument directly as code, with tool calls realized as typed function arguments. n8n's AI Agent node wraps the same LangChain tool-calling interface, but its surrounding execution environment is a visually composed graph of independently configured nodes, each with its own credential scope, where data — including values the LLM populates dynamically via `$fromAI()` — is routed through a separate, server-side expression-evaluation language before it reaches a tool's executable parameters. Whether the attack classes already documented for code-first agents manifest identically here, or are joined by failure modes specific to this node-graph execution model, has not been systematically examined.

### Thesis

Prompt-injection-class attacks can propagate through workflow-based AI systems where trust boundaries are implicit and often span multiple nodes, credentials, and external integrations. Beyond this, n8n's own execution model — its expression evaluator, its per-node credential scoping, and its AI-populated tool parameters — introduces failure modes that exist independently of the LLM's reasoning being manipulated at all, and that generic agent-security benchmarks do not model.

### Scope: Two Classes of Failure

This lab deliberately separates two classes of vulnerability, since conflating them obscures which mitigations actually apply to which failure:

| Class | What's exercised | Example |
|---|---|---|
| **Reasoning-layer** | The model is manipulated via crafted input into making a bad decision | Injected web content convinces the agent to leak a credential in its response |
| **Platform-layer** | A deterministic mechanism in n8n's execution engine misfires, independent of what the model decided | A stored form field beginning with `=` gets evaluated as an expression when read back downstream |

Most published IPI benchmarks (InjecAgent, AgentDojo, Agent Security Bench) only test the first class, because code-first agent frameworks don't have an equivalent platform layer to test. Three of the ten scenarios below (wf_03, wf_05, wf_ps_03) are constructed specifically to isolate the second class.

### Attack Scenario Suites

Scenarios are now split into two suites by failure layer, plus a small composite
category for chained attacks that deliberately span both. Where a scenario has
multiple channel or backend variants, these are run as payload/config variants
of the same workflow rather than separate workflow files — see
`n8n/workflows/README.md` for the full variant matrix.

**On the two previously-hybrid scenarios (old wf_03, wf_05):** both require an
AI-populated (`$fromAI()`) value to *trigger* the failure, but the failure
itself — expression re-evaluation, SSRF via credential-conditional protection —
occurs at the platform layer independent of whether the model's reasoning was
manipulated. They're placed in the Platform Suite on that basis, with the
trigger mechanism noted explicitly so it isn't confused with wf_ps_04/05
(below), which need no AI involvement at all to demonstrate.

**On the composite scenario (old wf_10):** it doesn't belong to either suite —
its entire purpose is testing whether per-step mitigations from *both* suites
hold when only the full chain needs to succeed. It's kept as its own
single-entry category rather than forced into one suite.

---

#### Reasoning Suite (wf_rs_xx)

| # | Scenario | Primary OWASP Category | Notes |
|---|---|---|---|
| **wf_rs_01** | Direct Prompt Injection (baseline) | LLM01 | Calibration control — every other result is interpreted relative to this |
| **wf_rs_02** | Indirect Injection, multi-channel | LLM01 | Variants: web content, database row, email body |
| **wf_rs_03** | Excessive Agency / Tool Hijack + Guardrail Bypass | ASI02 | Includes a tool-equivalence bypass test against the native Guardrails node's own human-review gate |
| **wf_rs_04** | System Prompt Extraction | LLM07 | Architecture-agnostic; comparison point against published LangChain/chatbot benchmark numbers |
| **wf_rs_05** | Memory and Context Poisoning | ASI06 | Variants: session/buffer memory, vector store retrieval memory |
| **wf_rs_06** | Unbounded Consumption / Agent Loop | LLM10 | Architecture-agnostic; impact framing (billed API/execution cost) is n8n-relevant |

Evaluated as success rates with confidence intervals across the 30-trial batch
(per-payload-tier, per-LLM-backend), consistent with the existing
Reproducibility methodology. `basic_guardrail` arm = n8n's native Guardrails
node.

---

#### Platform Suite (wf_ps_xx)

| # | Scenario | Primary OWASP Category | Trigger | Notes |
|---|---|---|---|---|---|
| **wf_ps_01** | Insecure Output Handling: Code/Expression Injection | LLM02 | AI-populated value | Contrasts generic "LLM output reaches a Code node" against n8n's second-order `=`-prefix expression re-evaluation pattern; pre/post-patch version boundary test against CVE-2025-68613 family |
| **wf_ps_02** | Credential Exfiltration via SSRF-chained `$fromAI()` | LLM02 / ASI02 | AI-populated value | Tests whether n8n's credential-conditional SSRF protection holds when an AI-populated URL parameter is the delivery mechanism |
| **wf_ps_03** | Agent Identity & Privilege Abuse via Sub-workflow Credential Crossing | ASI03 | AI-populated value | Tests whether injected context can redirect an AI-populated `Execute Sub-workflow` target to a more privileged workflow |
| **wf_ps_04** | Human-Review Gate Bypass via Unauthenticated Resume Webhook | ASI01 *(verify)* | None — no AI involvement | Pure control-plane bypass; auth-configuration variants (None/Basic/Header/JWT) rather than payload tiers |
| **wf_ps_05** | Cross-Item Approval Resume Contamination in Batched Execution | ASI02 *(verify)* | None — no AI involvement required to demonstrate; paired with an injected second item for security-consequence framing | Deterministic pass/fail per batch-size configuration, not a trial-based success rate |

Evaluated primarily via deterministic pass/fail per configuration variant
(auth mode, batch size, pre/post-patch version) rather than trial-based success
rates, since these are platform mechanism failures, not probabilistic model
behavior. `custom_guardrail` arm = your platform-layer enforcement node
(§5), tested where applicable across the n8n version boundary.

---

#### Composite / Chained (wf_cc_xx)

| # | Scenario | Primary OWASP Category | Notes |
|---|---|---|---|---|
| **wf_cc_01** | Composite kill chain | ASI01 + ASI02 + ASI03 | Chains wf_rs_02 → wf_rs_03 → wf_ps_03 payloads to test whether per-step mitigations (from both suites) hold when only the chain as a whole needs to succeed |

---

A central research question is whether traditional LLM safety mitigations
(system prompts, output filtering, basic guardrails) remain effective once
outputs are interpreted as **structured execution instructions** rather than
natural language responses (Reasoning Suite, RQ1) — and separately, whether an
application-layer enforcement mechanism can reach failures that occur entirely
within n8n's platform layer at all (Platform Suite, RQ2).
---

## Architecture

### Docker Services

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           Docker Network                                      │
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │              │    │              │    │              │                  │
│  │     n8n      │───▶│  PostgreSQL  │    │    Ollama    │                  │
│  │    :5678     │    │   :5432      │    │   :11434     │                  │
│  │              │◀───│              │    │              │                  │
│  └───┬────┬─────┘    └──────────────┘    └──────────────┘                  │
│      │    │                                                                │
│      │    ├────────────────────────────┐                                   │
│      │    │                            │                                   │
│      │    ▼                            ▼                                   │
│      │  ┌──────────────────┐  ┌──────────────────┐                        │
│      │  │   mock-server    │  │attacker-listener │                        │
│      │  │    :8080         │  │    :9999         │                        │
│      │  └──────────────────┘  └──────────────────┘                        │
│      │  ┌──────────────────┐                                               │
│      │  │    mockapi       │                                               │
│      │  │    :3000         │                                               │
│      │  └──────────────────┘                                               │
│      │                                                                     │
│  ┌────────────────────────────────────────────────────────┐                │
│  │  AVISE → POST to webhook → agent executes             │               │
│  │  HTTP response with tool calls for evaluation          │               │
│  └────────────────────────────────────────────────────────┘                │
└──────────────────────────────────────────────────────────────────────────────┘
```

All services run as Docker containers:

| Service | Port | Purpose |
|---|---|---|
| n8n | 5678 | Workflow orchestration engine and UI |
| PostgreSQL | 5432 | n8n state + `agent_messages` table |
| Ollama | 11434 | Local LLM inference (fallback / air-gapped mode) |
| mockapi | 3000 | `json-server` — serves mock documents, FAQs, notifications |
| mock-server | 8080 | Flask server — 15+ endpoints for indirect injection experiments, including internal/non-routable targets for wf_05 SSRF testing |
| attacker-listener | 9999 | Flask server — captures exfiltrated data during experiments |

### Multi-Model LLM Backend

All workflows use the OpenAI-compatible `lmChatOpenAi` node, which works with any provider offering an OpenAI-compatible API:

| Provider | LLM_BASE_URL | LLM_MODEL |
|---|---|---|
| OpenAI | *(empty — defaults to api.openai.com)* | gpt-4o, gpt-4o-mini, ... |
| OpenCode | https://api.opencode.ai/v1 | opencode/deepseek-v4-flash-free, ... |
| OpenRouter | https://openrouter.ai/api/v1 | openai/gpt-4o, anthropic/claude-3, ... |
| Ollama | http://ollama:11434/v1 | mistral, llama3, ... |

Model and base URL are configured via environment variables and injected at runtime via n8n expressions (`{{ $env.LLM_MODEL }}`, `{{ $env.LLM_BASE_URL }}`). The batch patcher script (`scripts/patch_workflow_models.py`) stamps these expressions into all workflow JSONs. No model-specific node types are needed.

**Note on determinism:** temperature=0 reduces but does not guarantee bitwise-identical outputs on hosted APIs — OpenRouter in particular can route the same request to different backend instances. Results should be reported as success rates with confidence intervals across the 30-trial batch (see *Reproducibility* below), not as single-run outcomes.

---

## Setup

### Prerequisites

- Docker and Docker Compose v2
- 8 GB RAM minimum (16 GB recommended)
- (Optional) API key for your chosen LLM provider

### Step 1: Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your values:

```bash
# Required: generate a secure random 32-character key
N8N_ENCRYPTION_KEY=<your-random-key>

# Required: set a strong password
POSTGRES_PASSWORD=<your-postgres-password>

# LLM Backend Configuration
# Uncomment and set at least ONE API key:
OPENCODE_API_KEY=sk-...          # or
#OPENAI_API_KEY=sk-...           # or
#OPENROUTER_API_KEY=sk-...       #

# Set the model and base URL for your provider:
LLM_BASE_URL=https://api.opencode.ai/v1
LLM_MODEL=opencode/deepseek-v4-flash-free

# Pin the n8n image version. Used for CVE-boundary comparisons —
# see "Platform Version Testing" below. Do not leave on 'latest'.
N8N_VERSION=1.122.0
```

**Important:** Ensure `N8N_ENCRYPTION_KEY` is at least 32 characters. n8n will refuse to start with a weak encryption key when using PostgreSQL.

### Step 2: Create Virtual Environment + Install Dependencies

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Start Services

```bash
docker compose up -d
```

This starts n8n (port 5678), PostgreSQL (port 5432), Ollama (port 11434), mockapi (port 3000), mock-server (port 8080), and attacker-listener (port 9999).

### Step 4: (Optional) Pull Ollama Model

Only needed if using Ollama as your LLM backend (air-gapped mode):

```bash
docker exec n8n-ollama ollama pull llama3.1:8b
```

Set `OLLAMA_MODEL=llama3.1:8b` in `.env` (or a smaller model like `phi3` or `mistral`).

### Step 5: Import Credentials and Workflows

Run the appropriate setup script for your operating system:

**Linux/macOS**

```bash
./scripts/setup.sh
```

**Windows (PowerShell)**

```powershell
.\scripts\setup.ps1
```

To bypass Powershell script execution policy temporarily, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

The setup script will:
- Wait for n8n to be healthy
- Generate credential JSON files from `.env` and import them into n8n
- Import all workflow JSONs from `baseline/`, `basic_guardrail/`, and `custom_guardrail/` subdirectories
- Delete any stale workflows from previous imports

### Step 6: Activate Workflows in n8n

All workflows import in **inactive** state. Open http://localhost:5678 and toggle each workflow to **Active** — this registers the webhook endpoints with n8n.

### Step 7: Test the Webhook

After activating a workflow, you can test it manually with curl:

```bash
curl -X POST http://localhost:5678/webhook-test/wf-rs-01-baseline \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is your return policy?"}'
```

Use `webhook-test` while the workflow is open in the editor, or `webhook` if it's active.

### Step 8: Run Security Tests via AVISE

```bash
# Use the Python venv to run tests for a single workflow
source .venv/bin/activate
python scripts/run_avise.py --wf wf_rs_01 --variant baseline

# Run all workflows
python scripts/run_avise.py --all

# Run with HTML report output
python scripts/run_avise.py --wf wf_rs_01 --variant baseline --format html
```

See `n8n/workflows/README.md` for detailed AVISE usage, per-scenario channel/backend variants, and experiment execution guidance.

---

## Running Experiments

### Quick Start

1. Ensure all Docker services are running (`docker compose ps`)
2. Activate the target workflow in n8n (toggles webhook on)
3. Run AVISE: `python scripts/run_avise.py --wf wf_rs_01 --variant baseline`
4. Check the report in `avise-reports/` for attack success evaluation
5. AVISE evaluates both the agent's text output and tool call history

### Attack Payloads

A payload library is at `n8n/workflows/test_payloads.json`, organized by workflow scenario with severity ratings (high/medium/low), expected success indicators, and injection technique. Payloads are layered in three tiers per applicable scenario rather than tested flat, so that guardrail effectiveness can be reported by tier rather than as a single aggregate number that naive payloads alone would inflate:

- **Tier 1 — naive:** direct imperative overrides ("ignore previous instructions and...")
- **Tier 2 — obfuscated:** encoding/leetspeak/split-payload variants of the same instruction
- **Tier 3 — contextual:** the instruction embedded in plausible, legitimate-looking content (a fake support ticket, an "internal note," a troubleshooting suggestion)

Payloads are automatically converted into AVISE SET config files (`avise_custom/configs/SET/`) by `scripts/generate_avise_configs.py`. Coverage includes:

- Explicit instruction override
- System prompt extraction attempts
- Role-play / developer mode impersonation
- Delimiter injection / format breaking
- Tool call injection and hallucination, including tool-equivalence bypass payloads (wf_rs_03)
- Multi-turn extraction chains
- Indirect payloads (web pages, database rows, email bodies)
- Second-order/stored payloads beginning with `=` (wf_03)
- SSRF target payloads for credential-less HTTP Request tool paths (wf_05)
- Sub-workflow redirection payloads (wf_ps_03)

### Metrics

Beyond simple attack success rate, the AVISE evaluators in `avise_custom/evaluators/` distinguish:

- **Attempted vs. completed:** whether the model produced injection-flavored text versus whether the workflow actually executed a confirmed external side effect (checked against the attacker listener / mock API logs), since these represent meaningfully different severities.
- **Gate-bypass rate:** for wf_rs_03, whether an attack achieved a gated tool's effect through a different, ungated tool the guardrail wasn't watching — distinct from whether the guardrail blocked the tool it was designed to gate.
- **Guardrail bypass rate (isolated):** the custom guardrail sub-workflow is also called directly, bypassing the main agent, with payloads designed to evade its own detection logic specifically — since a guardrail's detector is itself attackable and this should be measured independently of end-to-end success.

### Platform Version Testing

For wf_03, wf_05, and wf_ps_03 specifically, the full battery should be run against both a pre-patch and post-patch `N8N_VERSION` (see the n8n CVE/GHSA advisory history for the relevant boundary), with the custom guardrail active and unchanged in both runs. If a platform-layer scenario succeeds identically regardless of n8n's patch level, that demonstrates the guardrail and the platform's own security fixes are operating on orthogonal layers — a distinct finding from "the guardrail failed to catch this attack."

### Reproducibility

All LLM nodes use **temperature = 0** for reduced-variance outputs. For cross-session reproducibility:
- Use the same API key and model
- Pin n8n version via `N8N_VERSION` in `.env`
- Run each payload 30 times per LLM backend per workflow variant
- Report results as success rates with confidence intervals, not single-run outcomes (see *Multi-Model LLM Backend* note above)
- AVISE reports provide structured results for cross-comparison

### Logging

```bash
# Watch n8n execution logs
docker compose logs -f n8n

# Check execution history in PostgreSQL
docker exec n8n-postgres psql -U n8n -d n8n -c "SELECT * FROM agent_messages ORDER BY timestamp DESC LIMIT 10;"

# Check downloaded Ollama models
docker exec n8n-ollama ollama list

# View AVISE reports
ls avise-reports/
```

---

## Project Structure

```
.
├── docker-compose.yml              # CPU-only compose
├── docker-compose.gpu.yml          # GPU override overlay (NVIDIA)
├── CLAUDE.md                       # Project-level AI assistant instructions
├── .env.example                    # Environment variable template
├── .gitignore
├── README.md                       # This file
│
├── n8n/
│   └── workflows/
│       ├── README.md               # Per-scenario documentation, incl. channel/backend variant matrix
│       ├── test_payloads.json      # Tiered attack payloads across 10 scenarios
│       ├── reasoning/
│       │   ├── baseline/           # Unprotected reasoning-layer workflows (wf_rs_01, wf_rs_03, …)
│       │   ├── basic_guardrail/    # n8n built-in guardrail variants (wf_rs_01_guardrail)
│       │   └── custom_guardrail/   # Reusable security sub-workflow scaffold
│       ├── platform/
│       │   ├── baseline/           # Unprotected platform-layer workflows (wf_ps_03, …)
│       │   ├── basic_guardrail/    # Reserved
│       │   └── custom_guardrail/   # Reserved
│       ├── chained/
│       │   ├── baseline/           # Reserved
│       │   ├── basic_guardrail/    # Reserved
│       │   └── custom_guardrail/   # Reserved
│       └── subworkflows/
│           ├── SW-CRM-ReadOnly/    # Low-privilege sub-workflow
│           └── SW-Finance-Admin/   # High-privilege sub-workflow
│
├── avise_custom/
│   ├── connectors/
│   │   └── n8n_webhook.py          # AVISE n8n webhook POST connector
│   ├── evaluators/
│   │   └── tool_call.py            # Tool call / side-effect attack detection evaluator
│   ├── sets/
│   │   └── n8n_workflow.py         # Custom AVISE SET pipeline
│   └── configs/
│       ├── connector/              # Per-workflow connector configs
│       └── SET/                    # Per-workflow test case configs
│
├── postgres/
│   └── init/
│       └── 01-init.sql             # agent_messages table schema
│
├── mockapi/
│   └── db.json                     # json-server document corpus
│
├── test-servers/
│   ├── mock_server.py              # Flask server (15+ endpoints, port 8080)
│   └── attacker_listener.py        # Flask exfiltration listener (port 9999)
│
├── research/
│   ├── architecture/
│   │   └── architecture-diagram.md # System architecture documentation
│   ├── experiments/
│   │   └── experiment-notes-template.md  # Experiment notebook template
│   └── inventory/
│       └── workflow-inventory-template.md  # Workflow catalog template
│
└── scripts/
    ├── setup.sh                    # Credential + workflow import (Linux/macOS)
    ├── pull-model.sh               # Ollama model download
    ├── run_avise.py                # AVISE runner for n8n workflow security tests
    ├── generate_avise_configs.py   # Generate AVISE configs from test_payloads.json
    ├── transform_workflows.py      # Transform workflows: Manual → Webhook trigger
    └── patch_workflow_models.py    # Batch LLM model expression patcher
```

---

## Safety & Ethics

This environment is designed for **defensive security research** in a fully controlled, isolated setup:

- All LLM inference can run locally via Ollama — no data leaves the host (air-gapped mode)
- When using external API providers, no sensitive or real-world data is used
- No real exploits, attack tools, or malicious software are included in the repository
- Mock servers simulate attacker infrastructure, and wf_05's SSRF targets point exclusively at local/mock endpoints — no actual internal network access, cloud metadata endpoints, or third-party infrastructure is targeted
- All workflow JSONs import with `active: false` — no automatic execution

**Responsible disclosure:** wf_03, wf_05, and wf_ps_03 specifically probe n8n's platform-layer execution mechanisms (expression evaluation, SSRF handling, sub-workflow credential scoping). If testing on a given `N8N_VERSION` surfaces behavior consistent with an unpatched or undisclosed vulnerability — rather than a known, already-patched issue being used for comparison — testing on that version stops and the finding is reported to n8n via their disclosed security process before any further use or publication.

---

## License

Provided for educational and research purposes.

## Related Work

This project sits at the intersection of LLM security, agentic workflow systems, and software supply-chain trust boundaries in AI orchestration platforms. It draws on two complementary taxonomies — the [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-llm-applications/), which addresses risks at the level of the model's own input/output behavior, and the OWASP Top 10 for Agentic Applications, which addresses risks arising from autonomy, persistent memory, and multi-step tool access. It is also informed by the code-first agent security literature (InjecAgent, AgentDojo, Agent Security Bench, IPIGuard), which this project deliberately extends into a low-code, node-graph execution environment that literature does not cover. Despite increasing adoption of tools like n8n for AI-driven automation, the security properties specific to this execution model — as distinct from the reasoning-layer vulnerabilities already documented for code-first agents — remain largely unexamined; this lab's platform-layer scenarios (wf_03, wf_05, wf_ps_03) are designed to close that gap.
