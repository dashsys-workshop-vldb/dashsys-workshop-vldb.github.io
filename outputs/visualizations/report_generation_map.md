# Report Generation Map

Generated: 2026-05-18T12:30:10Z

This generated Mermaid diagram is synchronized from current local reports and code/module names only. It does not change runtime behavior.

- Packaged strategy: `SQL_FIRST_API_VERIFY`
- live_success guard: `blocked`

```mermaid
flowchart LR
  dev["scripts/run_dev_eval.py"] --> strict["outputs/eval_results_strict.json"]
  hidden["scripts/run_hidden_style_eval.py"] --> hidden_report["outputs/hidden_style_eval.json"]
  workflow["scripts/run_workflow_decision_audit.py"] --> decision_map["workflow_decision_map.md/json"]
  workflow --> decision_audit["workflow_decision_audit.md/json"]
  live_smoke["scripts/run_live_api_readiness_smoke.py"] --> smoke_report["live_api_readiness_smoke.md/json"]
  live_guard["dashagent/live_api_guard.py"] --> blocker["live_api_full_run_blocker.md/json"]
  waiting["scripts/run_post_permission_live_api_verification.py"] --> waiting_report["adobe_access_waiting_status.md/json"]
  context7["scripts/run_context7_code_alignment_audit.py"] --> context7_report["context7_code_alignment_audit.md/json"]
  mermaid["scripts/generate_project_mermaid_visualizations.py"] --> c4["project_architecture_c4.md/mmd"]
  mermaid --> pipeline["end_to_end_pipeline_mermaid.md/mmd"]
  mermaid --> live_viz["live_adobe_api_status_mermaid.md/mmd"]
  mermaid --> report_map["report_generation_map.md/mmd"]
  mermaid --> sync["visualization_sync_audit.md/json"]
  consolidated["scripts/generate_consolidated_reports.py"] --> index["report_index.md/json"]
  consolidated --> system["system_summary.md/json"]
  consolidated --> viz_summary["visualization_summary.md/json"]
  c4 --> index
  pipeline --> index
  live_viz --> index
  report_map --> index
  sync --> index
  guard_label["live_success guard"] -. protects .-> dev
  strategy["SQL_FIRST_API_VERIFY"] -. packaged default .-> strict
  classDef script fill:#eaf3ff,stroke:#2563eb,color:#111827
  classDef report fill:#f0fdf4,stroke:#16a34a,color:#111827
  classDef guard fill:#f5f5f5,stroke:#6b7280,stroke-dasharray: 5 5,color:#111827
  class dev,hidden,workflow,live_smoke,waiting,context7,mermaid,consolidated script
  class strict,hidden_report,decision_map,decision_audit,smoke_report,blocker,waiting_report,context7_report,c4,pipeline,live_viz,report_map,sync,index,system,viz_summary report
  class guard_label,strategy guard
```
