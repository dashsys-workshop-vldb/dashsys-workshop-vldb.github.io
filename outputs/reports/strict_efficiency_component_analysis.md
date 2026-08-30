# Strict Efficiency Component Analysis

Diagnostic-only decomposition of the remaining strict non-regression gap.

- Current strict score: `0.6567`
- Non-regression reference: `0.6553`
- Score gap vs reference: `0.0014`
- Correctness delta vs baseline: `0.0045`
- Avg token overhead vs baseline: `-35.4857`
- Avg runtime overhead vs baseline: `1.025`
- Primary efficiency source: `live_api_network_latency`

## Safest Candidates

- `live_get_session_reuse` for `live_api_network_latency` (`34` rows)
- `evidencebus_projection_for_answer_context` for `evidencebus_payload_tokens` (`1` rows)

## Top Token Rows

- `example_018` tokens `874` delta `196.0` source `live_api_network_latency`
- `example_031` tokens `901` delta `184.0` source `live_api_network_latency`
- `example_017` tokens `1002` delta `119.0` source `live_api_network_latency`
- `example_003` tokens `1681` delta `110.0` source `live_api_network_latency`
- `example_032` tokens `839` delta `91.0` source `live_api_network_latency`
- `example_015` tokens `504` delta `16.0` source `live_api_network_latency`
- `example_005` tokens `1333` delta `14.0` source `live_api_network_latency`
- `example_016` tokens `568` delta `13.0` source `live_api_network_latency`
- `example_034` tokens `898` delta `13.0` source `live_api_network_latency`
- `example_022` tokens `640` delta `2.0` source `live_api_network_latency`
