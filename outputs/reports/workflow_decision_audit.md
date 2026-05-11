# Workflow Decision Audit

- Status: `complete`
- Total SQL_FIRST_API_VERIFY public/dev rows: `35`
- Methodology rule: Do not reject serious candidates after one failed trial; run 3-5 controlled variants before final evidence-backed decisions.

## Bottleneck Distribution

- `answer_shape_weak`: `1`
- `answer_uses_dry_run_poorly`: `5`
- `api_only_needs_live_credentials`: `20`
- `api_optional_dry_run_noise`: `1`
- `api_required_but_credentials_missing`: `8`

## Highest-Priority Candidates

- `Live Adobe API readiness / response parser / EvidenceBus API evidence pipeline` from `api_only_needs_live_credentials` affecting `20` rows
- `Live Adobe API readiness / response parser / EvidenceBus API evidence pipeline` from `api_required_but_credentials_missing` affecting `8` rows
- `Dry-run fallback wording polish after live readiness` from `answer_uses_dry_run_poorly` affecting `5` rows
- `Live Adobe API readiness first; dry-run wording remains fallback polish` from `api_optional_dry_run_noise` affecting `1` rows
- `Answer-only rewrite with invariant hashes` from `answer_shape_weak` affecting `1` rows

## Per-Query Audit

- `example_000`: route=`SQL_THEN_API/JOURNEY_CAMPAIGN` answer=`0.4875` final=`0.6905` bottleneck=`answer_uses_dry_run_poorly`
- `example_001`: route=`SQL_THEN_API/JOURNEY_CAMPAIGN` answer=`0.545` final=`0.7909` bottleneck=`answer_uses_dry_run_poorly`
- `example_002`: route=`SQL_ONLY/JOURNEY_CAMPAIGN` answer=`0.4427` final=`0.7615` bottleneck=`answer_uses_dry_run_poorly`
- `example_003`: route=`SQL_ONLY/SEGMENT_AUDIENCE` answer=`0.3559` final=`0.7161` bottleneck=`answer_uses_dry_run_poorly`
- `example_004`: route=`SQL_THEN_API/DESTINATION_DATAFLOW` answer=`0.4492` final=`0.6746` bottleneck=`answer_uses_dry_run_poorly`
- `example_005`: route=`SQL_THEN_API/DESTINATION_DATAFLOW` answer=`0.8314` final=`0.9134` bottleneck=`api_optional_dry_run_noise`
- `example_006`: route=`SQL_THEN_API/DATASET_SCHEMA` answer=`0.4725` final=`0.7279` bottleneck=`api_required_but_credentials_missing`
- `example_007`: route=`SQL_ONLY/DATASET_SCHEMA` answer=`0.4857` final=`0.6559` bottleneck=`api_required_but_credentials_missing`
- `example_008`: route=`SQL_ONLY/PROPERTY_FIELD` answer=`0.482` final=`0.703` bottleneck=`answer_shape_weak`
- `example_009`: route=`SQL_ONLY/SEGMENT_AUDIENCE` answer=`0.5246` final=`0.7582` bottleneck=`api_required_but_credentials_missing`
- `example_010`: route=`SQL_ONLY/SEGMENT_AUDIENCE` answer=`0.5456` final=`0.7904` bottleneck=`api_required_but_credentials_missing`
- `example_011`: route=`SQL_ONLY/DATASET_SCHEMA` answer=`0.3915` final=`0.7461` bottleneck=`api_required_but_credentials_missing`
- `example_012`: route=`SQL_THEN_API/SEGMENT_AUDIENCE` answer=`0.2124` final=`0.7293` bottleneck=`api_required_but_credentials_missing`
- `example_013`: route=`SQL_ONLY/DATASET_SCHEMA` answer=`0.1695` final=`0.7167` bottleneck=`api_required_but_credentials_missing`
- `example_014`: route=`SQL_ONLY/UNKNOWN` answer=`0.4589` final=`0.766` bottleneck=`api_required_but_credentials_missing`
- `example_015`: route=`API_ONLY/COUNT_AGGREGATION` answer=`0.3681` final=`0.6674` bottleneck=`api_only_needs_live_credentials`
- `example_016`: route=`API_ONLY/UNKNOWN` answer=`0.3598` final=`0.6627` bottleneck=`api_only_needs_live_credentials`
- `example_017`: route=`API_ONLY/UNKNOWN` answer=`0.1246` final=`0.5298` bottleneck=`api_only_needs_live_credentials`
- `example_018`: route=`API_ONLY/UNKNOWN` answer=`0.3685` final=`0.6661` bottleneck=`api_only_needs_live_credentials`
- `example_019`: route=`API_ONLY/UNKNOWN` answer=`0.1049` final=`0.5351` bottleneck=`api_only_needs_live_credentials`
- `example_020`: route=`API_ONLY/COUNT_AGGREGATION` answer=`0.1079` final=`0.5371` bottleneck=`api_only_needs_live_credentials`
- `example_021`: route=`API_ONLY/SEGMENT_AUDIENCE` answer=`0.117` final=`0.54` bottleneck=`api_only_needs_live_credentials`
- `example_022`: route=`API_ONLY/SEGMENT_AUDIENCE` answer=`0.1178` final=`0.541` bottleneck=`api_only_needs_live_credentials`
- `example_023`: route=`API_ONLY/SEGMENT_AUDIENCE` answer=`0.1166` final=`0.5406` bottleneck=`api_only_needs_live_credentials`
- `example_024`: route=`API_ONLY/SEGMENT_AUDIENCE` answer=`0.1092` final=`0.5366` bottleneck=`api_only_needs_live_credentials`
- `example_025`: route=`API_ONLY/SEGMENT_AUDIENCE` answer=`0.1075` final=`0.5359` bottleneck=`api_only_needs_live_credentials`
- `example_026`: route=`API_ONLY/SEGMENT_AUDIENCE` answer=`0.1186` final=`0.5412` bottleneck=`api_only_needs_live_credentials`
- `example_027`: route=`API_ONLY/SEGMENT_AUDIENCE` answer=`0.2415` final=`0.6022` bottleneck=`api_only_needs_live_credentials`
- `example_028`: route=`API_ONLY/UNKNOWN` answer=`0.107` final=`0.5357` bottleneck=`api_only_needs_live_credentials`
- `example_029`: route=`API_ONLY/COUNT_AGGREGATION` answer=`0.1141` final=`0.5393` bottleneck=`api_only_needs_live_credentials`
- `example_030`: route=`API_ONLY/UNKNOWN` answer=`0.2802` final=`0.6218` bottleneck=`api_only_needs_live_credentials`
- `example_031`: route=`API_ONLY/UNKNOWN` answer=`0.3449` final=`0.6539` bottleneck=`api_only_needs_live_credentials`
- `example_032`: route=`API_ONLY/STATUS_MONITORING` answer=`0.381` final=`0.6717` bottleneck=`api_only_needs_live_credentials`
- `example_033`: route=`API_ONLY/DATASET_SCHEMA` answer=`0.3878` final=`0.6727` bottleneck=`api_only_needs_live_credentials`
- `example_034`: route=`API_ONLY/COUNT_AGGREGATION` answer=`0.3645` final=`0.6623` bottleneck=`api_only_needs_live_credentials`
