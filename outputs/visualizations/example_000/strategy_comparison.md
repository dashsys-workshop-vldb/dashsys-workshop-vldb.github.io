# Strategy Comparison: example_000

This view compares deterministic, Raw real LLM, Guided real LLM, and optimized-controller paths when those artifacts exist.

```mermaid
flowchart LR
  prompt["Query<br/>example_000"]
  prompt --> s0_route["SQL_FIRST_API_VERIFY<br/>route=SQL_PLUS_API"]
  s0_route --> s0_tools["tools=2<br/>invalid=n/a - no invalid-call metric recorded"]
  s0_tools --> s0_evidence["sql=yes<br/>live_api=no<br/>dry_run=yes"]
  s0_evidence --> s0_answer["answer<br/>The journey &quot;Birthday Message&quot; has not been published. The database shows a null published"]
  prompt --> s1_route["SQL_FIRST_API_VERIFY<br/>route=SQL_PLUS_API"]
  s1_route --> s1_tools["tools=2<br/>invalid=n/a - no invalid-call metric recorded"]
  s1_tools --> s1_evidence["sql=yes<br/>live_api=no<br/>dry_run=yes"]
  s1_evidence --> s1_answer["answer<br/>The journey &quot;Birthday Message&quot; has not been published. The database shows a null published"]
  prompt --> s2_route["Raw<br/>route=n/a - no prompt router decision"]
  s2_route --> s2_tools["tools=2<br/>invalid=0"]
  s2_tools --> s2_evidence["sql=no<br/>live_api=no<br/>dry_run=yes"]
  s2_evidence --> s2_answer["answer<br/>The executed query did not find evidence for Birthday Message. This is not a hard proof that it does"]
  prompt --> s3_route["Guided<br/>route=n/a - no prompt router decision"]
  s3_route --> s3_tools["tools=2<br/>invalid=0"]
  s3_tools --> s3_evidence["sql=yes<br/>live_api=no<br/>dry_run=yes"]
  s3_evidence --> s3_answer["answer<br/>The journey &quot;Birthday Message&quot; was published on **March 31, 2026**. However, I was unable "]
  prompt --> s4_route["Optimized Controller<br/>route=n/a - no prompt router decision"]
  s4_route --> s4_tools["tools=2<br/>invalid=0"]
  s4_tools --> s4_evidence["sql=n/a<br/>live_api=n/a<br/>dry_run=n/a"]
  s4_evidence --> s4_answer["answer<br/>The journey &quot;Birthday Message&quot; has not been published, as indicated by a null published_ti"]
  prompt --> s5_route["DETERMINISTIC_ROUTER_SELECTED_METADATA<br/>route=SQL_PLUS_API"]
  s5_route --> s5_tools["tools=2<br/>invalid=n/a - no invalid-call metric recorded"]
  s5_tools --> s5_evidence["sql=yes<br/>live_api=no<br/>dry_run=yes"]
  s5_evidence --> s5_answer["answer<br/>The journey &quot;Birthday Message&quot; has not been published. The database shows a null published"]
  prompt --> s6_route["LLM_FREE_AGENT_BASELINE<br/>route=SQL_PLUS_API"]
  s6_route --> s6_tools["tools=2<br/>invalid=n/a - no invalid-call metric recorded"]
  s6_tools --> s6_evidence["sql=no<br/>live_api=no<br/>dry_run=yes"]
  s6_evidence --> s6_answer["answer<br/>The journey &quot;Birthday Message&quot; has not been published. The database shows a null published"]
  prompt --> s7_route["SQL_ONLY_BASELINE<br/>route=SQL_PLUS_API"]
  s7_route --> s7_tools["tools=1<br/>invalid=n/a - no invalid-call metric recorded"]
  s7_tools --> s7_evidence["sql=yes<br/>live_api=n/a<br/>dry_run=n/a"]
  s7_evidence --> s7_answer["answer<br/>The journey &quot;Birthday Message&quot; has not been published. The database shows a null published"]
  prompt --> s8_route["TEMPLATE_FIRST<br/>route=SQL_PLUS_API"]
  s8_route --> s8_tools["tools=2<br/>invalid=n/a - no invalid-call metric recorded"]
  s8_tools --> s8_evidence["sql=yes<br/>live_api=no<br/>dry_run=yes"]
  s8_evidence --> s8_answer["answer<br/>The journey &quot;Birthday Message&quot; has not been published. The database shows a null published"]
```

| Variant | Strategy | Route | Context mode | Endpoint family | Ranking changed? | SQL preview | API endpoint | Tool calls | Invalid calls | Endpoint repairs | SQL evidence | Live API evidence | Overall evidence | Dry-run only | Runtime | Tokens | Final answer preview |
| --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- | --- | ---: | ---: | --- |
| SQL_FIRST_API_VERIFY | `LLM_SQL_FIRST_API_VERIFY` | SQL_PLUS_API | candidate | journey_list | True | SELECT "NAME" AS campaign_name, "LASTDEPLOYEDTIME" AS published_time FROM "dim_campaign" LIMIT 50 | GET /ajo/journey | 2 | n/a - no invalid-call metric recorded | n/a - no endpoint-repair metric recorded | True | False | True | True | 0.01375787507276982 |
| SQL_FIRST_API_VERIFY | `SQL_FIRST_API_VERIFY` | SQL_PLUS_API | candidate | journey_list | True | SELECT "NAME" AS campaign_name, "LASTDEPLOYEDTIME" AS published_time FROM "dim_campaign" LIMIT 50 | GET /ajo/journey | 2 | n/a - no invalid-call metric recorded | n/a - no endpoint-repair metric recorded | True | False | True | True | 0.012068375013768673 |
| Raw | `RAW_REAL_LLM_TWO_TOOLS_BASELINE` | n/a - no prompt router decision | candidate | journey_list | True | SELECT UPDATEDTIME FROM dim_campaign WHERE CAMPAIGNID IN (SELECT CAMPAIGNID FROM br_campaign_segment WHERE LABELSSEGMENT = 'Birthday Message') | GET /ajo/journey | 2 | 0 | 0 | False | False | False | True | 10.1537 |
| Guided | `GUIDED_REAL_LLM_TWO_TOOLS_BASELINE` | n/a - no prompt router decision | candidate | journey_list | True | SELECT UPDATEDTIME FROM dim_campaign WHERE NAME = 'Birthday Message' | GET /ajo/journey | 2 | 0 | 1 | True | False | True | True | 3.7744 |
| Optimized Controller | `LLM_CONTROLLER_OPTIMIZED_AGENT` | n/a - no prompt router decision | candidate | journey_list | True | n/a - no SQL call in trajectory | n/a - no API call in trajectory | 2 | 0 | 0 | n/a - no SQL call in trajectory | n/a - no API call in trajectory | False | n/a - no API call in trajectory | 1.3962 |
| DETERMINISTIC_ROUTER_SELECTED_METADATA | `DETERMINISTIC_ROUTER_SELECTED_METADATA` | SQL_PLUS_API | candidate | journey_list | True | SELECT "NAME" AS campaign_name, "LASTDEPLOYEDTIME" AS published_time FROM "dim_campaign" LIMIT 50 | GET /ajo/journey | 2 | n/a - no invalid-call metric recorded | n/a - no endpoint-repair metric recorded | True | False | True | True | 0.011692957952618599 |
| LLM_FREE_AGENT_BASELINE | `LLM_FREE_AGENT_BASELINE` | SQL_PLUS_API | candidate | journey_list | True | SELECT "IMSORGID", "LASTDEPLOYEDTIME", "STATE", "SANDBOXNAME", "NAME", "SANDBOXID", "STATUS", "CAMPAIGNID" FROM "dim_campaign" WHERE LOWER(CAST("SANDBOXNAME" AS VARCHAR)) LIKE LOWER('%Birthday Message%') AND LOWER(CAST("STATUS" AS VARCHAR)) LIKE LOWER('%published%') LIMIT 50 | GET /ajo/journey | 2 | n/a - no invalid-call metric recorded | n/a - no endpoint-repair metric recorded | False | False | False | True | 0.02012654091231525 |
| SQL_ONLY_BASELINE | `SQL_ONLY_BASELINE` | SQL_PLUS_API | candidate | journey_list | True | SELECT "NAME" AS campaign_name, "LASTDEPLOYEDTIME" AS published_time FROM "dim_campaign" LIMIT 50 | n/a - no API call in trajectory | 1 | n/a - no invalid-call metric recorded | n/a - no endpoint-repair metric recorded | True | n/a - no API call in trajectory | True | n/a - no API call in trajectory | 0.02018624998163432 |
| TEMPLATE_FIRST | `TEMPLATE_FIRST` | SQL_PLUS_API | candidate | journey_list | True | SELECT "NAME" AS campaign_name, "LASTDEPLOYEDTIME" AS published_time FROM "dim_campaign" LIMIT 50 | GET /ajo/journey | 2 | n/a - no invalid-call metric recorded | n/a - no endpoint-repair metric recorded | True | False | True | True | 0.012513165944255888 |
