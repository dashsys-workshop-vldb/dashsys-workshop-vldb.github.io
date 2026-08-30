# Threshold Tuning Report

- Strategy: `SQL_FIRST_API_VERIFY`
- Grid size: 6
- Best run: `run_02`
- Recommendation: Keep current defaults; tuning did not show a stable all-metric improvement.

| Run | Correctness | Final | Tools | Tokens | Runtime | Params |
|---|---:|---:|---:|---:|---:|---|
| run_01 | 0.8399 | 0.8146 | 1.46 | 857.6 | 0.0043 | {"api_skip_confidence_threshold": 0.0, "fast_path_confidence_threshold": 0.0, "max_gold_patterns": 1, "max_join_hints": 4, "max_preview_chars": 600, "relevance_top_k_apis": 3, "relevance_top_k_tables": 6} |
| run_02 | 0.8399 | 0.8146 | 1.46 | 857.0 | 0.0015 | {"api_skip_confidence_threshold": 0.1, "fast_path_confidence_threshold": 0.2, "max_gold_patterns": 2, "max_join_hints": 4, "max_preview_chars": 800, "relevance_top_k_apis": 4, "relevance_top_k_tables": 6} |
| run_03 | 0.8399 | 0.8146 | 1.46 | 857.3 | 0.0016 | {"api_skip_confidence_threshold": 0.1, "fast_path_confidence_threshold": 0.0, "max_gold_patterns": 1, "max_join_hints": 6, "max_preview_chars": 800, "relevance_top_k_apis": 3, "relevance_top_k_tables": 8} |
| run_04 | 0.8399 | 0.8146 | 1.46 | 857.3 | 0.0016 | {"api_skip_confidence_threshold": 0.2, "fast_path_confidence_threshold": 0.2, "max_gold_patterns": 2, "max_join_hints": 6, "max_preview_chars": 1000, "relevance_top_k_apis": 4, "relevance_top_k_tables": 8} |
| run_05 | 0.8399 | 0.8146 | 1.46 | 858.0 | 0.0016 | {"api_skip_confidence_threshold": 0.2, "fast_path_confidence_threshold": 0.4, "max_gold_patterns": 1, "max_join_hints": 8, "max_preview_chars": 600, "relevance_top_k_apis": 3, "relevance_top_k_tables": 10} |
| run_06 | 0.8399 | 0.8146 | 1.46 | 857.4 | 0.0017 | {"api_skip_confidence_threshold": 0.0, "fast_path_confidence_threshold": 0.0, "max_gold_patterns": 2, "max_join_hints": 8, "max_preview_chars": 1000, "relevance_top_k_apis": 4, "relevance_top_k_tables": 8} |

## Leave-One-Family-Out Final Scores
- audit: 0.8141
- batch: 0.8167
- destination_dataflow: 0.8123
- journey_campaign: 0.8133
- merge_policy: 0.8155
- observability: 0.8152
- property_field: 0.8129
- schema_dataset: 0.8135
- segment_audience: 0.8163
- tags: 0.8162
