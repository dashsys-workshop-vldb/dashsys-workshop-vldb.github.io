# Final Gate Strict Drift Secret Scan

- Scanned files: `419`
- Real secret hits: `0`
- Fixture false-positive hits: `3`
- OK: `true`
- Values printed: `false`
- Exclusions: `.env files`, env backups, venvs, archives/zips, binary data

## Fixture False Positives
- `outputs/source_code/tests/test_live_adobe_api_readiness.py` pattern=`api_key_assignment` count=`2` classification=`synthetic_test_fixture_false_positive`
- `outputs/source_code/tests/test_llm_client.py` pattern=`api_key_assignment` count=`1` classification=`synthetic_test_fixture_false_positive`
