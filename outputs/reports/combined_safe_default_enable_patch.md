# Combined Safe Default Enable Patch

- Enable-phase candidate default: `COMBINED_SAFE_DETERMINISTIC_PROMOTION_CANDIDATE`.
- Final status: reverted after final gate failure.
- Current default strategy: `SQL_FIRST_API_VERIFY`.
- LLM advisor included: `false`.
- Broad semantic router promoted: `false`.
- Final submission schema changed: `false`.

Rollback instructions remain: set `PACKAGED_DEFAULT_STRATEGY` to `SQL_FIRST_API_VERIFY`, regenerate packaged outputs, rerun readiness and strict eval.
