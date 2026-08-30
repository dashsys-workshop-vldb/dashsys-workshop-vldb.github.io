# Weak Model SQL External Technique Mapping

Diagnostic-only mapping for weak-model SQL correctness work. Packaged `SQL_FIRST_API_VERIFY` remains unchanged.

| Pattern | Implemented | DashAgent Mapping | Expected Impact | Risk |
| --- | --- | --- | --- | --- |
| Vanna-style schema/context retrieval | yes | `dashagent/weak_sql_schema_retriever.py` retrieves tables, roles, value links, timestamp candidates, and join candidates. | Better table/column/filter grounding. | Low: bounded advisory context plus validators. |
| SQLGlot AST validation/canonicalization | yes | Existing `SQLValidator`/AST summary still validates compiled SQL. | Blocks invalid or unsafe SQL. | Low: validators unchanged. |
| SQLCoder-style schema-aware prompt | yes | Weak model fills semantic slots; compiler receives role-aware schema context and skeleton families. | Reduces raw SQL guessing. | Low: no gold/public SQL examples. |
| DIN-SQL decomposition | partial | Flow decomposes slot filling, retrieval, compilation, validation, repair, execution, and grounding. | Reduces compound weak-model errors. | Low while shadow-only. |
| CHESS schema selector/unit tester | yes | `dashagent/weak_sql_unit_tester.py` checks intent, table, columns, filters, joins, aggregation, timestamp semantics, and broad queries. | Rejects valid-but-wrong SQL before execution. | Medium if too strict; mitigated by repair and shadow-only evaluation. |
| SQL repair/revision loop | yes | Enhanced compiler uses one bounded repair round from semantic unit-test feedback. | Recovers wrong table/filter/timestamp choices. | Low: no raw SQL execution before validation. |
| Dynamic SQL skeleton retrieval | yes | `dashagent/weak_sql_skeleton_retriever.py` returns generic role-based SQL shapes. | Improves count/list/date/status/relationship shape selection. | Low: skeletons contain no query IDs or gold answers. |

All implemented pieces are restricted to weak-model scaffold diagnostics and do not promote or alter packaged runtime behavior.
