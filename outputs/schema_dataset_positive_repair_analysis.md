# Schema/Dataset Positive Repair Analysis

- Positive schema/dataset rows: 1
- Catalog alias gap candidates: 1
- Repair enabled: False

| Query ID | Score delta | Failed checks | Failure classification | Generalizable rule candidate |
| --- | ---: | --- | --- | --- |
| `example_007` | 0.1148 | api_validation | catalog_alias_gap_or_real_endpoint_risk | Only consider schema/dataset endpoint alias repair when the target path is already present in endpoint catalog or explicit alias map. |
