# Historical Answer Grounding Evidence Table

| Mode | Local rows | Local empty finals | Local fallback used | Repro answer | Repro final | Repro fallback used |
|---|---:|---:|---:|---:|---:|---:|
| `ROBUST_ABLATION_ANSWER_GROUNDING_ONLY` | 35 | 35 | 0 | 0.2182 | 0.6178 | 35 |
| `ROBUST_ABLATION_LLM_ANSWER_WITH_VERIFIER` | 35 | 35 | 0 | 0.2182 | 0.6179 | 35 |

Interpretation: local historical trajectories show empty final answers selected as verifier-accepted LLM output; isolated old-commit rerun did not reproduce the high score.
