# Strategy Comparison: example_031

This view compares deterministic, Raw real LLM, Guided real LLM, and optimized-controller paths when those artifacts exist.

```mermaid
flowchart LR
  prompt["Query<br/>example_031"]
  prompt --> s0_route["SQL_FIRST_API_VERIFY<br/>route=API_ONLY"]
  s0_route --> s0_tools["tools=1<br/>invalid=n/a - no invalid-call metric recorded"]
  s0_tools --> s0_evidence["evidence=False<br/>dry_run=True"]
  s0_evidence --> s0_answer["answer<br/>Batch file details require live API evidence. Live API verification was not executed because Adobe c"]
  prompt --> s1_route["SQL_FIRST_API_VERIFY<br/>route=API_ONLY"]
  s1_route --> s1_tools["tools=1<br/>invalid=n/a - no invalid-call metric recorded"]
  s1_tools --> s1_evidence["evidence=False<br/>dry_run=True"]
  s1_evidence --> s1_answer["answer<br/>Batch file details require live API evidence. Live API verification was not executed because Adobe c"]
  prompt --> s2_route["Raw<br/>route=n/a - no prompt router decision"]
  s2_route --> s2_tools["tools=0<br/>invalid=0"]
  s2_tools --> s2_evidence["evidence=False<br/>dry_run=n/a - no API call in trajectory"]
  s2_evidence --> s2_answer["answer<br/>n/a - missing final answer"]
  prompt --> s3_route["Guided<br/>route=n/a - no prompt router decision"]
  s3_route --> s3_tools["tools=0<br/>invalid=0"]
  s3_tools --> s3_evidence["evidence=False<br/>dry_run=n/a - no API call in trajectory"]
  s3_evidence --> s3_answer["answer<br/>n/a - missing final answer"]
  prompt --> s4_route["Optimized Controller<br/>route=n/a - no prompt router decision"]
  s4_route --> s4_tools["tools=1<br/>invalid=0"]
  s4_tools --> s4_evidence["evidence=False<br/>dry_run=n/a - no API call in trajectory"]
  s4_evidence --> s4_answer["answer<br/>Batch file details require live API evidence. Live API verification was not executed because Adobe c"]
  prompt --> s5_route["DETERMINISTIC_ROUTER_SELECTED_METADATA<br/>route=API_ONLY"]
  s5_route --> s5_tools["tools=1<br/>invalid=n/a - no invalid-call metric recorded"]
  s5_tools --> s5_evidence["evidence=False<br/>dry_run=True"]
  s5_evidence --> s5_answer["answer<br/>Batch file details require live API evidence. Live API verification was not executed because Adobe c"]
  prompt --> s6_route["LLM_FREE_AGENT_BASELINE<br/>route=API_ONLY"]
  s6_route --> s6_tools["tools=2<br/>invalid=n/a - no invalid-call metric recorded"]
  s6_tools --> s6_evidence["evidence=True<br/>dry_run=True"]
  s6_evidence --> s6_answer["answer<br/>Batch file details require live API evidence. Live API verification was not executed because Adobe c"]
  prompt --> s7_route["SQL_ONLY_BASELINE<br/>route=API_ONLY"]
  s7_route --> s7_tools["tools=1<br/>invalid=n/a - no invalid-call metric recorded"]
  s7_tools --> s7_evidence["evidence=True<br/>dry_run=n/a - no API call in trajectory"]
  s7_evidence --> s7_answer["answer<br/>Batch file details require live API evidence. API evidence was not requested."]
  prompt --> s8_route["TEMPLATE_FIRST<br/>route=API_ONLY"]
  s8_route --> s8_tools["tools=1<br/>invalid=n/a - no invalid-call metric recorded"]
  s8_tools --> s8_evidence["evidence=False<br/>dry_run=True"]
  s8_evidence --> s8_answer["answer<br/>Batch file details require live API evidence. Live API verification was not executed because Adobe c"]
```

| Variant | Strategy | Route | Context mode | SQL preview | API endpoint | Tool calls | Invalid calls | Endpoint repairs | Evidence available | Dry-run only | Runtime | Tokens | Final answer preview |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- | --- | ---: | ---: | --- |
| SQL_FIRST_API_VERIFY | `LLM_SQL_FIRST_API_VERIFY` | API_ONLY | n/a - no candidate context mode recorded | n/a - no SQL call in trajectory | GET /data/foundation/export/batches/69de8a0e0cc6102b5d11f01e/files | 1 | n/a - no invalid-call metric recorded | n/a - no endpoint-repair metric recorded | False | True | 0.011331833084113896 | 683 | Batch file details require live API evidence. Live API verification was not executed because Adobe credentials are unavailable. |
| SQL_FIRST_API_VERIFY | `SQL_FIRST_API_VERIFY` | API_ONLY | n/a - no candidate context mode recorded | n/a - no SQL call in trajectory | GET /data/foundation/export/batches/69de8a0e0cc6102b5d11f01e/files | 1 | n/a - no invalid-call metric recorded | n/a - no endpoint-repair metric recorded | False | True | 0.009698958019725978 | 723 | Batch file details require live API evidence. Live API verification was not executed because Adobe credentials are unavailable. |
| Raw | `RAW_REAL_LLM_TWO_TOOLS_BASELINE` | n/a - no prompt router decision | n/a - no candidate context mode recorded | n/a - no SQL call in trajectory | n/a - no API call in trajectory | 0 | 0 | 0 | False | n/a - no API call in trajectory | 0.1249 | n/a - estimated_tokens missing | n/a - missing final answer |
| Guided | `GUIDED_REAL_LLM_TWO_TOOLS_BASELINE` | n/a - no prompt router decision | n/a - no candidate context mode recorded | n/a - no SQL call in trajectory | n/a - no API call in trajectory | 0 | 0 | 0 | False | n/a - no API call in trajectory | 0.2616 | n/a - estimated_tokens missing | n/a - missing final answer |
| Optimized Controller | `LLM_CONTROLLER_OPTIMIZED_AGENT` | n/a - no prompt router decision | n/a - no candidate context mode recorded | n/a - no SQL call in trajectory | n/a - no API call in trajectory | 1 | 0 | 0 | False | n/a - no API call in trajectory | 0.1366 | n/a - estimated_tokens missing | Batch file details require live API evidence. Live API verification was not executed because Adobe credentials are unavailable. |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | `DETERMINISTIC_ROUTER_SELECTED_METADATA` | API_ONLY | n/a - no candidate context mode recorded | n/a - no SQL call in trajectory | GET /data/foundation/export/batches/69de8a0e0cc6102b5d11f01e/files | 1 | n/a - no invalid-call metric recorded | n/a - no endpoint-repair metric recorded | False | True | 0.00986512505915016 | 661 | Batch file details require live API evidence. Live API verification was not executed because Adobe credentials are unavailable. |
| LLM_FREE_AGENT_BASELINE | `LLM_FREE_AGENT_BASELINE` | API_ONLY | n/a - no candidate context mode recorded | SELECT "SEGMENTID", "CAMPAIGNID", "LABELSSEGMENT", "LABELSCAMPAIGN" FROM "br_campaign_segment" LIMIT 50 | GET /data/foundation/export/batches/69de8a0e0cc6102b5d11f01e/files | 2 | n/a - no invalid-call metric recorded | n/a - no endpoint-repair metric recorded | True | True | 0.016300915973261 | 1082 | Batch file details require live API evidence. Live API verification was not executed because Adobe credentials are unavailable. |
| SQL_ONLY_BASELINE | `SQL_ONLY_BASELINE` | API_ONLY | n/a - no candidate context mode recorded | SELECT "SEGMENTID", "CAMPAIGNID", "LABELSSEGMENT", "LABELSCAMPAIGN" FROM "br_campaign_segment" LIMIT 50 | n/a - no API call in trajectory | 1 | n/a - no invalid-call metric recorded | n/a - no endpoint-repair metric recorded | True | n/a - no API call in trajectory | 0.010920499917119741 | 831 | Batch file details require live API evidence. API evidence was not requested. |
| TEMPLATE_FIRST | `TEMPLATE_FIRST` | API_ONLY | n/a - no candidate context mode recorded | n/a - no SQL call in trajectory | GET /data/foundation/export/batches/69de8a0e0cc6102b5d11f01e/files | 1 | n/a - no invalid-call metric recorded | n/a - no endpoint-repair metric recorded | False | True | 0.009333709022030234 | 652 | Batch file details require live API evidence. Live API verification was not executed because Adobe credentials are unavailable. |
