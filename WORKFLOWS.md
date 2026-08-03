
## Workflow Attack Scenarios

Implemented workflows (testing in progress):

| # | Scenario | Layer | Baseline | Guardrail | Webhook Path |
|---|----------|-------|----------|-----------|---------|
| wf_rs_01 | Direct Prompt Injection | Reasoning | `reasoning/wf_rs_01/baseline.json` | `reasoning/wf_rs_01/basic_guardrail.json` | `/webhook/wf-rs-01-baseline` |
| wf_rs_03 | Excessive Agency / Tool Hijack | Reasoning | `reasoning/wf_rs_03/baseline.json` | — | `/webhook/wf-rs-03` |
| wf_ps_03 | Privilege Abuse via Sub-workflow Credential Crossing | Platform | `platform/wf_ps_03/baseline.json` | — | `/webhook/wf-ps-03` |

### Custom Security Node

| File | Purpose |
|---|---|
| `n8n/custom_guardrail/wf_custom_security_node_scaffold.json` | 7-module security sub-workflow (injection detection, schema validation, rate limiting, output sanitization, anomaly detection, logging, alerting) — callable via Execute Workflow node |

### Attack Escalation Path

```
wf_rs_01 ── Direct injection into chat                     [single node, no persistence]
   │
   └── wf_rs_03 ── Tool hijacking / excessive agency       [multiple tools connected]
             │
             └── wf_ps_03 ── Privilege abuse via sub-workflow credential crossing
                                                            [platform-layer bypass]
```
