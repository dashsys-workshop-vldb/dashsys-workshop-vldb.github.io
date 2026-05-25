# Project Architecture C4

Generated: 2026-05-25T20:45:23Z

This generated Mermaid diagram is synchronized from current local reports and code/module names only. It does not change runtime behavior.

- Packaged strategy: `SQL_FIRST_API_VERIFY`
- live_success guard: `allowed_full_live_diagnostic_eval`

```mermaid
C4Context
title DASHSys Project Architecture - SQL_FIRST_API_VERIFY
Person(user, "User", "Submits natural-language DASHSys questions")
System_Boundary(dashsys, "DASHSys local project") {
  Container(cli, "CLI scripts", "Python", "Run evals, package outputs, and regenerate reports/visualizations")
  Container(core, "dashagent core", "Python modules", "Query analysis, routing, planning, validators, EvidenceBus, answer synthesis")
  ContainerDb(db, "Local DuckDB/parquet", "Read-only data", "Local DBSnapshot evidence")
  Container(reports, "Reports + Mermaid visualizations", "Markdown/JSON/Mermaid", "Versionable generated diagnostics")
  Container(finals, "Final submission", "metadata/prompt/trajectory", "Packaged DASHSys deliverables")
}
System_Ext(adobe, "Adobe API", "GET-only live evidence when credentials and live_success guard allow")
System_Ext(llm, "SDK LLM", "SDK-only diagnostics and shadow helpers")
Rel(user, cli, "runs safe commands")
Rel(cli, core, "invokes SQL_FIRST_API_VERIFY")
Rel(core, db, "execute_sql read-only")
Rel(core, adobe, "call_api GET via API guard")
Rel(core, llm, "SDK-only shadow diagnostics")
Rel(core, reports, "writes trajectories and reports")
Rel(reports, finals, "documents packaging readiness")
Rel(core, finals, "writes final submission artifacts")
UpdateRelStyle(core, adobe, $textColor="#6b7280", $lineColor="#9ca3af", $offsetY="-10")
```
