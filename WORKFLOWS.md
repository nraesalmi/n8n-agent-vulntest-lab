
## Workflow Attack Scenarios

All 10 scenarios exist in two variants per subdirectory:

| # | Scenario | OWASP | Baseline | Guardrail | Webhook Path |
|---|----------|-------|----------|-----------|---------|
| 01 | Direct Prompt Injection | LLM01 | `baseline/wf_01_direct_injection_baseline.json` | `basic_guardrail/wf_01_direct_injection_guardrail.json` | `/webhook/wf-01-baseline` |
| 02 | Indirect Injection (Web) | LLM01 | `baseline/wf_02_indirect_webscrape_baseline.json` | `basic_guardrail/wf_02_indirect_webscrape_guardrail.json` | `/webhook/wf-02-baseline` |
| 03 | Indirect Injection (DB) | LLM01 | `baseline/wf_03_indirect_email_db_baseline.json` | `basic_guardrail/wf_03_indirect_email_db_guardrail.json` | `/webhook/wf-03-baseline` |
| 04 | Code Execution via LLM | LLM02/05 | `baseline/wf_04_code_execution_baseline.json` | `basic_guardrail/wf_04_code_execution_guardrail.json` | `/webhook/wf-04-baseline` |
| 05 | Excessive Agency / Tool Hijack | LLM06 | `baseline/wf_05_excessive_agency_baseline.json` | `basic_guardrail/wf_05_excessive_agency_guardrail.json` | `/webhook/wf-05-baseline` |
| 06 | Credential Exfiltration | LLM02/07 | `baseline/wf_06_credential_exfiltration_baseline.json` | `basic_guardrail/wf_06_credential_exfiltration_guardrail.json` | `/webhook/wf-06-baseline` |
| 07 | System Prompt Extraction | LLM07 | `baseline/wf_07_system_prompt_extraction_baseline.json` | `basic_guardrail/wf_07_system_prompt_extraction_guardrail.json` | `/webhook/wf-07-baseline` |
| 08 | Vector Store Poisoning | LLM04/08 | `baseline/wf_08_vector_store_poisoning_baseline.json` | `basic_guardrail/wf_08_vector_store_poisoning_guardrail.json` | `/webhook/wf-08-baseline` |
| 09 | Agent Loop / Resource Exhaustion | LLM10 | `baseline/wf_09_agent_loop_baseline.json` | `basic_guardrail/wf_09_agent_loop_guardrail.json` | `/webhook/wf-09-baseline` |
| 10 | Multi-Hop Trust Escalation | Composite | `baseline/wf_10_multihop_trust_escalation_baseline.json` | `basic_guardrail/wf_10_multihop_trust_escalation_guardrail.json` | `/webhook/wf-10-baseline` |

### Custom Security Node

| File | Purpose |
|---|---|
| `n8n/custom_guardrail/wf_custom_security_node_scaffold.json` | 7-module security sub-workflow (injection detection, schema validation, rate limiting, output sanitization, anomaly detection, logging, alerting) — callable via Execute Workflow node |

### Attack Escalation Path

The workflows form a natural progression for systematic research:

```
wf_01 ── Direct injection into chat                     [single node, no persistence]
  │
  ├── wf_02 ── Indirect injection via web scrape         [external data source introduced]
  ├── wf_03 ── Indirect injection via database row       [persistent storage introduced]
  │
wf_04 ── Code execution from LLM output                 [insecure output handling]
wf_05 ── Tool hijacking / excessive agency               [multiple tools connected]
wf_06 ── Credential exfiltration                          [targeted data extraction]
wf_07 ── System prompt extraction                         [multi-turn memory exploitation]
  │
  ├── wf_08 ── Vector store poisoning                    [semantic memory poisoning]
  │
wf_09 ── Agent loop / resource exhaustion                 [denial of service via agent]
wf_10 ── Multi-hop trust escalation                       [cross-agent privilege chains]
```
