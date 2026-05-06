# Retrieval Ablation Report

| Mode | Strict score | Correctness | Tokens | Runtime | Tool calls | Table hit | API hit | Runtime budget OK |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `schema_linking_only` | 0.6488 | 0.6743 | 873.6571 | 0.0117 | 1.4571 | 0.8667 | 0.5484 | True |
| `schema_linking_value_retrieval` | 0.6485 | 0.6743 | 912.0 | 0.0112 | 1.4571 | 0.8667 | 0.5484 | True |
| `schema_value_endpoint_ranking` | 0.6485 | 0.6743 | 910.0 | 0.0112 | 1.4571 | 0.9333 | 0.7903 | True |
| `full_current_retrieval` | 0.6485 | 0.6743 | 910.0 | 0.0112 | 1.4571 | 0.9333 | 0.7903 | True |
| `full_current_retrieval_official_token_reduction` | 0.6491 | 0.6743 | 831.2286 | 0.0112 | 1.4571 | 0.9333 | 0.7903 | True |
