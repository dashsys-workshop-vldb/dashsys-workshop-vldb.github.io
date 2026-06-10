# Family Score Report

| Family | Examples | SQL | API | Answer | Correctness | Final | Tools | Runtime | Tokens | Lowest | Next Fix |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| audit | 2 | 0.9500 | 1.0000 | 0.5873 | 0.8562 | 0.8232 | 2.00 | 0.0098 | 958 | example_012, example_014 | Add a concise evidence-grounded answer template. |
| batch | 4 | 1.0000 | 1.0000 | 0.3892 | 0.8168 | 0.7989 | 1.00 | 0.0085 | 639 | example_029, example_030, example_031 | Add a concise evidence-grounded answer template. |
| destination_dataflow | 3 | 0.9667 | 1.0000 | 0.6073 | 0.8689 | 0.8399 | 1.67 | 0.0097 | 977 | example_032, example_004, example_005 | Add a concise evidence-grounded answer template. |
| journey_campaign | 3 | 0.9000 | 1.0000 | 0.6681 | 0.8604 | 0.8283 | 2.00 | 0.0094 | 857 | example_001, example_002, example_000 | Add a concise evidence-grounded answer template. |
| merge_policy | 3 | 1.0000 | 1.0000 | 0.4122 | 0.8237 | 0.8061 | 1.00 | 0.0082 | 602 | example_020, example_019, example_021 | Add a concise evidence-grounded answer template. |
| observability | 2 | 1.0000 | 1.0000 | 0.4140 | 0.8242 | 0.8036 | 1.00 | 0.0100 | 962 | example_033, example_034 | Add a concise evidence-grounded answer template. |
| property_field | 1 | 0.9000 | 1.0000 | 0.7598 | 0.8879 | 0.8701 | 1.00 | 0.0082 | 639 | example_008 | Mostly healthy; monitor efficiency and hidden-query generalization. |
| schema_dataset | 6 | 0.9500 | 0.9207 | 0.6595 | 0.8540 | 0.8198 | 2.00 | 0.0103 | 1108 | example_011, example_007, example_013 | Add a concise evidence-grounded answer template. |
| segment_audience | 7 | 0.9857 | 1.0000 | 0.4547 | 0.8307 | 0.8080 | 1.29 | 0.0088 | 786 | example_025, example_003, example_024 | Add a concise evidence-grounded answer template. |
| tags | 4 | 1.0000 | 1.0000 | 0.4260 | 0.8278 | 0.8067 | 1.25 | 0.0083 | 651 | example_017, example_016, example_018 | Add a concise evidence-grounded answer template. |

## NLP Diagnostics For Lowest Examples
- audit: [{"candidate": "generic_sql_first", "query_id": "example_012", "rewrites": ["important_plurals->singular"], "tables": []}, {"candidate": "generic_sql_first", "query_id": "example_014", "rewrites": [], "tables": []}]
- batch: [{"candidate": "generic_sql_first", "query_id": "example_029", "rewrites": ["important_plurals->singular"], "tables": []}, {"candidate": "generic_sql_first", "query_id": "example_030", "rewrites": [], "tables": []}, {"candidate": "generic_sql_first", "query_id": "example_031", "rewrites": ["important_plurals->singular"], "tables": []}]
- destination_dataflow: [{"candidate": "generic_sql_first", "query_id": "example_032", "rewrites": ["important_plurals->singular"], "tables": []}, {"candidate": "generic_sql_first", "query_id": "example_004", "rewrites": [], "tables": []}, {"candidate": "generic_sql_first", "query_id": "example_005", "rewrites": ["important_plurals->singular"], "tables": []}]
- journey_campaign: [{"candidate": "generic_sql_first", "query_id": "example_001", "rewrites": ["important_plurals->singular"], "tables": []}, {"candidate": "generic_sql_first", "query_id": "example_002", "rewrites": ["important_plurals->singular"], "tables": []}, {"candidate": "generic_sql_first", "query_id": "example_000", "rewrites": [], "tables": []}]
- merge_policy: [{"candidate": "generic_sql_first", "query_id": "example_020", "rewrites": ["important_plurals->singular"], "tables": []}, {"candidate": "generic_sql_first", "query_id": "example_019", "rewrites": ["important_plurals->singular"], "tables": []}, {"candidate": "generic_sql_first", "query_id": "example_021", "rewrites": [], "tables": []}]
- observability: [{"candidate": "generic_sql_first", "query_id": "example_033", "rewrites": [], "tables": []}, {"candidate": "generic_sql_first", "query_id": "example_034", "rewrites": ["\\bbatch\\s+success\\b->batchsuccess"], "tables": []}]
- property_field: [{"candidate": "generic_sql_first", "query_id": "example_008", "rewrites": [], "tables": []}]
- schema_dataset: [{"candidate": "generic_sql_first", "query_id": "example_011", "rewrites": ["important_plurals->singular"], "tables": []}, {"candidate": "generic_sql_first", "query_id": "example_007", "rewrites": ["important_plurals->singular"], "tables": []}, {"candidate": "generic_sql_first", "query_id": "example_013", "rewrites": ["important_plurals->singular"], "tables": []}]
- segment_audience: [{"candidate": "generic_sql_first", "query_id": "example_025", "rewrites": ["\\bsegment\\s+evaluation\\s+jobs?\\b->segment job"], "tables": []}, {"candidate": "generic_sql_first", "query_id": "example_003", "rewrites": ["\\bsegment\\s+audiences?\\b->segments", "important_plurals->singular"], "tables": []}, {"candidate": "generic_sql_first", "query_id": "example_024", "rewrites": ["important_plurals->singular"], "tables": []}]
- tags: [{"candidate": "generic_sql_first", "query_id": "example_017", "rewrites": ["important_plurals->singular"], "tables": []}, {"candidate": "generic_sql_first", "query_id": "example_016", "rewrites": ["important_plurals->singular"], "tables": []}, {"candidate": "generic_sql_first", "query_id": "example_018", "rewrites": [], "tables": []}]
