# Workflow Decision Audit

- Status: `complete`
- Total SQL_FIRST_API_VERIFY public/dev rows: `35`
- Methodology rule: Do not reject serious candidates after one failed trial; run 3-5 controlled variants before final evidence-backed decisions.

## Bottleneck Distribution

- `answer_shape_weak`: `1`
- `no_clear_bottleneck`: `1`
- `unnecessary_dry_run_api`: `33`

## Highest-Priority Candidates

- `Dry-run wording/API optional skip isolated trial` from `unnecessary_dry_run_api` affecting `33` rows
- `Answer-only rewrite with invariant hashes` from `answer_shape_weak` affecting `1` rows

## Per-Query Audit

- `example_000`: route=`SQL_THEN_API/JOURNEY_CAMPAIGN` answer=`0.4875` final=`0.6905` bottleneck=`unnecessary_dry_run_api`
- `example_001`: route=`SQL_THEN_API/JOURNEY_CAMPAIGN` answer=`0.545` final=`0.7909` bottleneck=`unnecessary_dry_run_api`
- `example_002`: route=`SQL_ONLY/JOURNEY_CAMPAIGN` answer=`0.4427` final=`0.7615` bottleneck=`unnecessary_dry_run_api`
- `example_003`: route=`SQL_ONLY/SEGMENT_AUDIENCE` answer=`0.3559` final=`0.7161` bottleneck=`unnecessary_dry_run_api`
- `example_004`: route=`SQL_THEN_API/DESTINATION_DATAFLOW` answer=`0.4492` final=`0.6746` bottleneck=`unnecessary_dry_run_api`
- `example_005`: route=`SQL_THEN_API/DESTINATION_DATAFLOW` answer=`0.8314` final=`0.9134` bottleneck=`no_clear_bottleneck`
- `example_006`: route=`SQL_THEN_API/DATASET_SCHEMA` answer=`0.4725` final=`0.7279` bottleneck=`unnecessary_dry_run_api`
- `example_007`: route=`SQL_ONLY/DATASET_SCHEMA` answer=`0.4857` final=`0.656` bottleneck=`unnecessary_dry_run_api`
- `example_008`: route=`SQL_ONLY/PROPERTY_FIELD` answer=`0.482` final=`0.703` bottleneck=`answer_shape_weak`
- `example_009`: route=`SQL_ONLY/SEGMENT_AUDIENCE` answer=`0.5246` final=`0.7582` bottleneck=`unnecessary_dry_run_api`
- `example_010`: route=`SQL_ONLY/SEGMENT_AUDIENCE` answer=`0.5456` final=`0.7904` bottleneck=`unnecessary_dry_run_api`
- `example_011`: route=`SQL_ONLY/DATASET_SCHEMA` answer=`0.3915` final=`0.7462` bottleneck=`unnecessary_dry_run_api`
- `example_012`: route=`SQL_THEN_API/SEGMENT_AUDIENCE` answer=`0.2124` final=`0.7293` bottleneck=`unnecessary_dry_run_api`
- `example_013`: route=`SQL_ONLY/DATASET_SCHEMA` answer=`0.1695` final=`0.7167` bottleneck=`unnecessary_dry_run_api`
- `example_014`: route=`SQL_ONLY/UNKNOWN` answer=`0.4589` final=`0.7661` bottleneck=`unnecessary_dry_run_api`
- `example_015`: route=`API_ONLY/COUNT_AGGREGATION` answer=`0.3681` final=`0.6674` bottleneck=`unnecessary_dry_run_api`
- `example_016`: route=`API_ONLY/UNKNOWN` answer=`0.3598` final=`0.6627` bottleneck=`unnecessary_dry_run_api`
- `example_017`: route=`API_ONLY/UNKNOWN` answer=`0.1246` final=`0.5299` bottleneck=`unnecessary_dry_run_api`
- `example_018`: route=`API_ONLY/UNKNOWN` answer=`0.3685` final=`0.6661` bottleneck=`unnecessary_dry_run_api`
- `example_019`: route=`API_ONLY/UNKNOWN` answer=`0.1049` final=`0.5351` bottleneck=`unnecessary_dry_run_api`
- `example_020`: route=`API_ONLY/COUNT_AGGREGATION` answer=`0.1079` final=`0.5371` bottleneck=`unnecessary_dry_run_api`
- `example_021`: route=`API_ONLY/SEGMENT_AUDIENCE` answer=`0.117` final=`0.54` bottleneck=`unnecessary_dry_run_api`
- `example_022`: route=`API_ONLY/SEGMENT_AUDIENCE` answer=`0.1178` final=`0.541` bottleneck=`unnecessary_dry_run_api`
- `example_023`: route=`API_ONLY/SEGMENT_AUDIENCE` answer=`0.1166` final=`0.5406` bottleneck=`unnecessary_dry_run_api`
- `example_024`: route=`API_ONLY/SEGMENT_AUDIENCE` answer=`0.1092` final=`0.5366` bottleneck=`unnecessary_dry_run_api`
- `example_025`: route=`API_ONLY/SEGMENT_AUDIENCE` answer=`0.1075` final=`0.536` bottleneck=`unnecessary_dry_run_api`
- `example_026`: route=`API_ONLY/SEGMENT_AUDIENCE` answer=`0.1186` final=`0.5412` bottleneck=`unnecessary_dry_run_api`
- `example_027`: route=`API_ONLY/SEGMENT_AUDIENCE` answer=`0.2415` final=`0.6022` bottleneck=`unnecessary_dry_run_api`
- `example_028`: route=`API_ONLY/UNKNOWN` answer=`0.107` final=`0.5357` bottleneck=`unnecessary_dry_run_api`
- `example_029`: route=`API_ONLY/COUNT_AGGREGATION` answer=`0.1141` final=`0.5393` bottleneck=`unnecessary_dry_run_api`
- `example_030`: route=`API_ONLY/UNKNOWN` answer=`0.2802` final=`0.6218` bottleneck=`unnecessary_dry_run_api`
- `example_031`: route=`API_ONLY/UNKNOWN` answer=`0.3449` final=`0.6539` bottleneck=`unnecessary_dry_run_api`
- `example_032`: route=`API_ONLY/STATUS_MONITORING` answer=`0.381` final=`0.6717` bottleneck=`unnecessary_dry_run_api`
- `example_033`: route=`API_ONLY/DATASET_SCHEMA` answer=`0.3878` final=`0.6727` bottleneck=`unnecessary_dry_run_api`
- `example_034`: route=`API_ONLY/COUNT_AGGREGATION` answer=`0.3645` final=`0.6623` bottleneck=`unnecessary_dry_run_api`
