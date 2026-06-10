# Robustness Dropout Evaluation

- Strategy: `SQL_FIRST_API_VERIFY`
- High-risk modes: none
- Medium-risk modes: drop_one_join_hint, drop_api_fallback_templates

| Mode | Correctness | Final | Tools | Tokens | Delta Correctness | Delta Final | Risk |
|---|---:|---:|---:|---:|---:|---:|---|
| baseline | 0.8399 | 0.8146 | 1.46 | 858.4 | 0.0000 | 0.0000 | low |
| drop_fast_paths | 0.8399 | 0.8146 | 1.46 | 860.4 | 0.0000 | 0.0000 | low |
| drop_gold_patterns | 0.8399 | 0.8146 | 1.46 | 860.4 | 0.0000 | 0.0000 | low |
| drop_one_join_hint | 0.8399 | 0.8145 | 1.46 | 861.4 | 0.0000 | -0.0001 | medium |
| drop_context_cards | 0.8399 | 0.8146 | 1.46 | 860.4 | 0.0000 | 0.0000 | low |
| drop_api_fallback_templates | 0.8399 | 0.8145 | 1.46 | 862.4 | 0.0000 | -0.0001 | medium |
