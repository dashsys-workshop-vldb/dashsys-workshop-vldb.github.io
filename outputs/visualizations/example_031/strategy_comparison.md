# Strategy Comparison: example_031

This view compares deterministic, Raw real LLM, Guided real LLM, and optimized-controller paths when those artifacts exist.

```mermaid
flowchart LR
  prompt["Query<br/>example_031"]
  prompt --> s0_route["SQL_FIRST_API_VERIFY<br/>route=API_ONLY"]
  s0_route --> s0_tools["tools=1<br/>invalid=n/a - no invalid-call metric recorded"]
  s0_tools --> s0_evidence["sql=n/a<br/>live_api=no<br/>dry_run=yes"]
  s0_evidence --> s0_answer["answer<br/>Batch file details require live API evidence. Live API verification was not executed because Adobe c"]
  prompt --> s1_route["SQL_FIRST_API_VERIFY<br/>route=API_ONLY"]
  s1_route --> s1_tools["tools=1<br/>invalid=n/a - no invalid-call metric recorded"]
  s1_tools --> s1_evidence["sql=n/a<br/>live_api=no<br/>dry_run=yes"]
  s1_evidence --> s1_answer["answer<br/>Batch file details require live API evidence. Live API verification was not executed because Adobe c"]
  prompt --> s2_route["Raw<br/>route=n/a - no prompt router decision"]
  s2_route --> s2_tools["tools=0<br/>invalid=0"]
  s2_tools --> s2_evidence["sql=n/a<br/>live_api=n/a<br/>dry_run=n/a"]
  s2_evidence --> s2_answer["answer<br/>n/a - missing final answer"]
  prompt --> s3_route["Guided<br/>route=n/a - no prompt router decision"]
  s3_route --> s3_tools["tools=0<br/>invalid=0"]
  s3_tools --> s3_evidence["sql=n/a<br/>live_api=n/a<br/>dry_run=n/a"]
  s3_evidence --> s3_answer["answer<br/>n/a - missing final answer"]
  prompt --> s4_route["Optimized Controller<br/>route=n/a - no prompt router decision"]
  s4_route --> s4_tools["tools=1<br/>invalid=0"]
  s4_tools --> s4_evidence["sql=n/a<br/>live_api=n/a<br/>dry_run=n/a"]
  s4_evidence --> s4_answer["answer<br/>Batch file details require live API evidence. Live API verification was not executed because Adobe c"]
  prompt --> s5_route["DETERMINISTIC_ROUTER_SELECTED_METADATA<br/>route=API_ONLY"]
  s5_route --> s5_tools["tools=1<br/>invalid=n/a - no invalid-call metric recorded"]
  s5_tools --> s5_evidence["sql=n/a<br/>live_api=no<br/>dry_run=yes"]
  s5_evidence --> s5_answer["answer<br/>Batch file details require live API evidence. Live API verification was not executed because Adobe c"]
  prompt --> s6_route["LLM_FREE_AGENT_BASELINE<br/>route=API_ONLY"]
  s6_route --> s6_tools["tools=2<br/>invalid=n/a - no invalid-call metric recorded"]
  s6_tools --> s6_evidence["sql=yes<br/>live_api=no<br/>dry_run=yes"]
  s6_evidence --> s6_answer["answer<br/>Batch file details require live API evidence. Live API verification was not executed because Adobe c"]
  prompt --> s7_route["SQL_ONLY_BASELINE<br/>route=API_ONLY"]
  s7_route --> s7_tools["tools=1<br/>invalid=n/a - no invalid-call metric recorded"]
  s7_tools --> s7_evidence["sql=yes<br/>live_api=n/a<br/>dry_run=n/a"]
  s7_evidence --> s7_answer["answer<br/>Batch file details require live API evidence. API evidence was not requested."]
  prompt --> s8_route["TEMPLATE_FIRST<br/>route=API_ONLY"]
  s8_route --> s8_tools["tools=1<br/>invalid=n/a - no invalid-call metric recorded"]
  s8_tools --> s8_evidence["sql=n/a<br/>live_api=no<br/>dry_run=yes"]
  s8_evidence --> s8_answer["answer<br/>Batch file details require live API evidence. Live API verification was not executed because Adobe c"]
```

| Variant | Strategy | Route | Context mode | Endpoint family | Ranking changed? | SQL preview | API endpoint | Tool calls | Invalid calls | Endpoint repairs | SQL evidence | Live API evidence | Overall evidence | Dry-run only | Runtime | Tokens | Final answer preview |
| --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- | --- | ---: | ---: | --- |
| SQL_FIRST_API_VERIFY | `LLM_SQL_FIRST_API_VERIFY` | API_ONLY | candidate | batch_files | True | n/a - no SQL call in trajectory | GET /data/foundation/export/batches/69de8a0e0cc6102b5d11f01e/files | 1 | n/a - no invalid-call metric recorded | n/a - no endpoint-repair metric recorded | n/a - no SQL call in trajectory | False | False | True | 0.011331833084113896 |
| SQL_FIRST_API_VERIFY | `SQL_FIRST_API_VERIFY` | API_ONLY | candidate | batch_files | True | n/a - no SQL call in trajectory | GET /data/foundation/export/batches/69de8a0e0cc6102b5d11f01e/files | 1 | n/a - no invalid-call metric recorded | n/a - no endpoint-repair metric recorded | n/a - no SQL call in trajectory | False | False | True | 0.010196209070272744 |
| Raw | `RAW_REAL_LLM_TWO_TOOLS_BASELINE` | n/a - no prompt router decision | candidate | batch_files | True | n/a - no SQL call in trajectory | n/a - no API call in trajectory | 0 | 0 | 0 | n/a - no SQL call in trajectory | n/a - no API call in trajectory | False | n/a - no API call in trajectory | 0.1249 |
| Guided | `GUIDED_REAL_LLM_TWO_TOOLS_BASELINE` | n/a - no prompt router decision | candidate | batch_files | True | n/a - no SQL call in trajectory | n/a - no API call in trajectory | 0 | 0 | 0 | n/a - no SQL call in trajectory | n/a - no API call in trajectory | False | n/a - no API call in trajectory | 0.2616 |
| Optimized Controller | `LLM_CONTROLLER_OPTIMIZED_AGENT` | n/a - no prompt router decision | candidate | batch_files | True | n/a - no SQL call in trajectory | n/a - no API call in trajectory | 1 | 0 | 0 | n/a - no SQL call in trajectory | n/a - no API call in trajectory | False | n/a - no API call in trajectory | 0.1366 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | `DETERMINISTIC_ROUTER_SELECTED_METADATA` | API_ONLY | candidate | batch_files | True | n/a - no SQL call in trajectory | GET /data/foundation/export/batches/69de8a0e0cc6102b5d11f01e/files | 1 | n/a - no invalid-call metric recorded | n/a - no endpoint-repair metric recorded | n/a - no SQL call in trajectory | False | False | True | 0.010171332978643477 |
| LLM_FREE_AGENT_BASELINE | `LLM_FREE_AGENT_BASELINE` | API_ONLY | candidate | batch_files | True | SELECT "SEGMENTID", "CAMPAIGNID", "LABELSSEGMENT", "LABELSCAMPAIGN" FROM "br_campaign_segment" LIMIT 50 | GET /data/foundation/export/batches/69de8a0e0cc6102b5d11f01e/files | 2 | n/a - no invalid-call metric recorded | n/a - no endpoint-repair metric recorded | True | False | True | True | 0.019631833070889115 |
| SQL_ONLY_BASELINE | `SQL_ONLY_BASELINE` | API_ONLY | candidate | batch_files | True | SELECT "SEGMENTID", "CAMPAIGNID", "LABELSSEGMENT", "LABELSCAMPAIGN" FROM "br_campaign_segment" LIMIT 50 | n/a - no API call in trajectory | 1 | n/a - no invalid-call metric recorded | n/a - no endpoint-repair metric recorded | True | n/a - no API call in trajectory | True | n/a - no API call in trajectory | 0.01211945794057101 |
| TEMPLATE_FIRST | `TEMPLATE_FIRST` | API_ONLY | candidate | batch_files | True | n/a - no SQL call in trajectory | GET /data/foundation/export/batches/69de8a0e0cc6102b5d11f01e/files | 1 | n/a - no invalid-call metric recorded | n/a - no endpoint-repair metric recorded | n/a - no SQL call in trajectory | False | False | True | 0.010183708975091577 |
