# Minimal Organizer 35 Progressive Check

- Command: `python3 scripts/run_dev_eval.py --strict --strategies SQL_FIRST_API_VERIFY,ROBUST_GENERALIZED_HARNESS_CANDIDATE`
- Real AgentExecutor execution: `true`
- Promotion judgment: `not_run`

## Strategy Summary

| Strategy | Final | Correctness | SQL | API | Answer | Tool Calls | Runtime |
|---|---:|---:|---:|---:|---:|---:|---:|
| `SQL_FIRST_API_VERIFY` | 0.6578 | 0.685 | 0.9333 | 0.9791 | 0.3207 | 1.4571 | 0.6981 |
| `ROBUST_GENERALIZED_HARNESS_CANDIDATE` | 0.5339 | 0.5635 | 0.9333 | 0.8553 | 0.1543 | 1.4286 | 1.4749 |

## Safety Counts
- API_REQUIRED underuse-like rows: `0`
- No-tool false-positive-like rows: `0`
- Validation failures baseline/candidate: `{'SQL_FIRST_API_VERIFY': 1, 'ROBUST_GENERALIZED_HARNESS_CANDIDATE': 1}`
- Helped/hurt/neutral: `{'helped': 2, 'hurt': 33, 'neutral': 0}`
- Severe regression rows: `19`

## Severe Regression Rows
- `example_000` delta `-0.1348`: final `0.6893` -> `0.5545`, answer `0.5044` -> `0.19`, API `None` -> `None`
- `example_004` delta `-0.1662`: final `0.6741` -> `0.5079`, answer `0.4513` -> `0.078`, API `None` -> `None`
- `example_005` delta `-0.1527`: final `0.8387` -> `0.686`, answer `0.5882` -> `0.0959`, API `1.0` -> `1.0`
- `example_006` delta `-0.1289`: final `0.7336` -> `0.6047`, answer `0.4935` -> `0.0797`, API `0.7337` -> `0.7337`
- `example_007` delta `-0.113`: final `0.6239` -> `0.5109`, answer `0.3776` -> `0.0172`, API `0.6175` -> `0.6175`
- `example_010` delta `-0.1388`: final `0.7898` -> `0.651`, answer `0.5456` -> `0.0997`, API `1.0` -> `1.0`
- `example_011` delta `-0.1401`: final `0.7892` -> `0.6491`, answer `0.5396` -> `0.0907`, API `1.0` -> `1.0`
- `example_015` delta `-0.1507`: final `0.5549` -> `0.4042`, answer `0.1509` -> `0.0152`, API `1.0` -> `0.83`
- `example_016` delta `-0.1233`: final `0.556` -> `0.4327`, answer `0.1485` -> `0.0738`, API `1.0` -> `0.83`
- `example_017` delta `-0.1964`: final `0.623` -> `0.4266`, answer `0.3168` -> `0.3278`, API `1.0` -> `0.5637`
- `example_018` delta `-0.4111`: final `0.7544` -> `0.3433`, answer `0.5507` -> `0.1073`, API `1.0` -> `0.6175`
- `example_020` delta `-0.114`: final `0.644` -> `0.53`, answer `0.323` -> `0.2655`, API `1.0` -> `0.83`
- `example_026` delta `-0.1788`: final `0.6613` -> `0.4825`, answer `0.368` -> `0.0187`, API `1.0` -> `1.0`
- `example_028` delta `-0.1198`: final `0.5283` -> `0.4085`, answer `0.0989` -> `0.0252`, API `1.0` -> `0.83`
- `example_029` delta `-0.1684`: final `0.5786` -> `0.4102`, answer `0.1944` -> `0.0281`, API `1.0` -> `0.83`
- `example_030` delta `-0.3155`: final `0.7333` -> `0.4178`, answer `0.505` -> `0.2589`, API `1.0` -> `0.6175`
- `example_031` delta `-0.2873`: final `0.6688` -> `0.3815`, answer `0.3833` -> `0.1867`, API `1.0` -> `0.6175`
- `example_032` delta `-0.2722`: final `0.6669` -> `0.3947`, answer `0.38` -> `0.213`, API `1.0` -> `0.6175`
- `example_034` delta `-0.4876`: final `0.5515` -> `0.0639`, answer `0.1472` -> `0.0154`, API `1.0` -> `0.15`

## Interpretation
Minimal check only. Candidate remained safe against no-tool/API-underuse in this strict run but regressed final/answer score materially versus SQL_FIRST_API_VERIFY.
