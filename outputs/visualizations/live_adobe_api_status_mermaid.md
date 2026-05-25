# Live Adobe API Status Mermaid

Generated: 2026-05-25T19:43:12Z

This generated Mermaid diagram is synchronized from current local reports and code/module names only. It does not change runtime behavior.

- Packaged strategy: `SQL_FIRST_API_VERIFY`
- live_success guard: `allowed_full_live_diagnostic_eval`

```mermaid
flowchart TD
  env[".env.local readiness<br/>presence only"] --> token["Token acquisition<br/>client_credentials or access_token"]
  token --> smoke["Safe GET smoke"]
  smoke --> outcomes["Endpoint outcomes<br/>auth / sandbox / path / service"]
  outcomes --> success{"live_success_count > 0?"}
  success -->|yes| allowed["live_success guard<br/>full live eval allowed"]
  success -->|no| blocked["live_success guard<br/>full live eval blocked"]
  blocked --> follow["Follow-up commands<br/>all-safe-get + endpoint filters"]
  allowed --> trial["Live evidence pipeline trial"]
  trial --> prompts["Live generated prompts<br/>diagnostic-only"]
  meta["Current status<br/>live_success_count: 10<br/>guard: allowed_full_live_diagnostic_eval<br/>usable evidence: unavailable"] -.-> success
  classDef ready fill:#ecfdf5,stroke:#16a34a,color:#111827
  classDef blocked fill:#fff7ed,stroke:#ea580c,color:#111827
  classDef neutral fill:#f8fafc,stroke:#64748b,color:#111827
  class env,token,smoke,outcomes,trial,prompts neutral
  class allowed ready
  class blocked,follow blocked
```
