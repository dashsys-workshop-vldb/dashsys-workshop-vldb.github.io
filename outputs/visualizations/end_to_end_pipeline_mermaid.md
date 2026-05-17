# End-To-End Pipeline Mermaid

Generated: 2026-05-17T12:58:37Z

This generated Mermaid diagram is synchronized from current local reports and code/module names only. It does not change runtime behavior.

- Packaged strategy: `SQL_FIRST_API_VERIFY`
- live_success guard: `blocked`

```mermaid
flowchart TD
  user["User Prompt"] --> analysis["Query Analysis"]
  analysis --> router["Deterministic Router"]
  router --> strategy["SQL_FIRST_API_VERIFY<br/>packaged default"]
  strategy --> plan["SQL/API Plan"]
  plan --> sqlv["SQL Validation<br/>read-only guard"]
  plan --> apig["API Guard<br/>GET-only catalog"]
  sqlv --> sql["execute_sql<br/>DuckDB/parquet"]
  apig --> api["call_api<br/>Adobe API or dry-run"]
  sql --> bus["EvidenceBus"]
  api --> bus
  bus --> slots["Answer Slots"]
  slots --> synth["Answer Synthesis"]
  synth --> verifier["Verifier"]
  verifier --> eval["Eval"]
  eval --> package["Packaging"]
  guard["live_success guard"] -. blocks large live runs when 0 .-> apig
  reports["Reports + Mermaid sync audit"] -. generated locally .-> eval
  classDef main fill:#eaf3ff,stroke:#2563eb,color:#111827
  classDef evidence fill:#ecfdf5,stroke:#16a34a,color:#111827
  classDef guard fill:#f5f5f5,stroke:#6b7280,stroke-dasharray: 5 5,color:#111827
  class user,analysis,router,strategy,plan,synth,verifier,eval,package main
  class sqlv,sql,apig,api,bus,slots evidence
  class guard,reports guard
```
