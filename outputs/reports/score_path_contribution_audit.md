# Score Path Contribution Audit

Diagnostic-only map from the full project dataflow and current score reports to the code paths that can affect strict score.

- Packaged strategy: `SQL_FIRST_API_VERIFY`
- Strict score: `0.6553`
- Live success count: `0`
- Official score claim: `False`
- Runtime behavior changed: `False`

## Practical Conclusion

Use the SVG as a map, but keep score work on the direct runtime path. Before Adobe access is fixed, the realistic score trial surface is answer synthesis, SQL evidence usage, and dry-run wording. Live API score gains remain externally blocked.

## Score Focus Now

- answer synthesis
- SQL evidence usage
- dry-run wording

## Blocked By Adobe Access

- live Adobe API evidence
- API-only rows that need sandbox/permission access
- full live strict eval and live generated-prompt diagnostics

## Do Not Touch For Score Now

- visualization/reporting aesthetics
- Context7 reports
- Playwright reports
- generated prompt labels as promotion evidence
- LLM controller / semantic router / broad answer rewrite promotion

## Direct Score Path Components

| Component | Score relevance | Reason |
| --- | --- | --- |
| `router` | `only_change_with_strict_evidence` | These can change score but carry regression risk; generated-prompt labels alone are not enough. |
| `intent/domain detection` | `only_change_with_strict_evidence` | These can change score but carry regression risk; generated-prompt labels alone are not enough. |
| `SQL_FIRST_API_VERIFY` | `protect_do_not_weaken` | This component affects strict score or final submission artifacts. |
| `SQL/API plan` | `only_change_with_strict_evidence` | These can change score but carry regression risk; generated-prompt labels alone are not enough. |
| `SQL validation/execution` | `only_change_with_strict_evidence` | These can change score but carry regression risk; generated-prompt labels alone are not enough. |
| `API evidence state` | `partly_blocked_by_adobe_access` | Dry-run wording is testable now, but usable live API evidence waits for external access. |
| `EvidenceBus` | `can_improve_now` | Reports show answer/evidence usage gaps that can be tested without live Adobe API access. |
| `answer slots` | `can_improve_now` | Reports show answer/evidence usage gaps that can be tested without live Adobe API access. |
| `answer synthesis` | `can_improve_now` | Reports show answer/evidence usage gaps that can be tested without live Adobe API access. |
| `verifier` | `can_improve_now` | Reports show answer/evidence usage gaps that can be tested without live Adobe API access. |
| `eval output` | `protect_do_not_weaken` | This component affects strict score or final submission artifacts. |
| `final submission trajectory` | `protect_do_not_weaken` | This component affects strict score or final submission artifacts. |
