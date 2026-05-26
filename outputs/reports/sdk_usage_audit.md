# SDK Usage Audit

This audit checks that LLM/model calls use the shared SDK-based LLM client abstraction.

- Runtime LLM direct HTTP hits: `0`
- Source code hits: `14`
- Generated output hits: `4`
- Documentation hits: `11`
- Runtime hits: `8`
- All LLM calls SDK-based: `True`

## Classification Counts

- `documentation_only`: `11`
- `generated_output_stale_copy`: `4`
- `sdk_client_allowed`: `8`
- `test_fixture_allowed`: `17`

## Remaining Allowed Exceptions

- SDK client configuration constants for provider base URLs.
- Documentation examples that describe SDK-only rules.
- Test fixtures that assert direct LLM HTTP is not used.
- Generated output/source copies are reported separately and are not runtime code.

The Adobe REST API path is out of scope for the LLM SDK rule and remains unchanged.
