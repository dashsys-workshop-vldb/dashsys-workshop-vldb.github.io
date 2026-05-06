# Risk-Efficiency Shadow Evaluation

This report simulates diagnostic-module skipping for low/medium risk rows only. It does not change packaged execution.

- Packaged execution changed: False
- Measured accuracy improvement claimed: False
- Measured efficiency improvement claimed: False
- No behavior-changing flags were enabled in this pass.
- Rows: 7
- Avg token delta: -264.0
- Avg runtime delta: -0.025

| Query ID | Risk | Skipped modules | Current score | Replay score | Token delta | Runtime delta | Answer changed? |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `example_000` | low | value_retrieval, shadow_repair, repair_safety_verifier, schema_context_voting | 0.6903 | 0.6903 | -264 | -0.025 | False |
| `example_001` | medium | value_retrieval, shadow_repair, repair_safety_verifier, schema_context_voting | 0.7902 | 0.7902 | -264 | -0.025 | False |
| `example_002` | low | value_retrieval, shadow_repair, repair_safety_verifier, schema_context_voting | 0.761 | 0.761 | -264 | -0.025 | False |
| `example_008` | medium | value_retrieval, shadow_repair, repair_safety_verifier, schema_context_voting | 0.7027 | 0.7027 | -264 | -0.025 | False |
| `example_014` | medium | value_retrieval, shadow_repair, repair_safety_verifier, schema_context_voting | 0.7654 | 0.7654 | -264 | -0.025 | False |
| `example_020` | medium | value_retrieval, shadow_repair, repair_safety_verifier, schema_context_voting | 0.5369 | 0.5369 | -264 | -0.025 | False |
| `example_033` | medium | value_retrieval, shadow_repair, repair_safety_verifier, schema_context_voting | 0.672 | 0.672 | -264 | -0.025 | False |
