# Failure Analysis

Rows are sorted from lowest final score to highest.

| Rank | Query ID | Strategy | Final | SQL | API | Answer | Category | Recommended Fix |
|---:|---|---|---:|---:|---:|---:|---|---|
| 1 | example_008 | LLM_FREE_AGENT_BASELINE | 0.3261 | 0.0000 | 1.0000 | 0.2545 | SQL_COLUMN_MISMATCH | Align the selected projection/aliases with the requested fields and known gold-style columns. |
| 2 | example_007 | LLM_FREE_AGENT_BASELINE | 0.3579 | 0.0000 | 0.7760 | 0.5319 | SQL_COLUMN_MISMATCH | Align the selected projection/aliases with the requested fields and known gold-style columns. |
| 3 | example_005 | LLM_FREE_AGENT_BASELINE | 0.3706 | 0.0000 | 1.0000 | 0.3463 | SQL_COLUMN_MISMATCH | Align the selected projection/aliases with the requested fields and known gold-style columns. |
| 4 | example_014 | LLM_FREE_AGENT_BASELINE | 0.3709 | 0.0000 | 1.0000 | 0.3545 | SQL_COLUMN_MISMATCH | Align the selected projection/aliases with the requested fields and known gold-style columns. |
| 5 | example_003 | LLM_FREE_AGENT_BASELINE | 0.3766 | 0.0000 | 1.0000 | 0.4187 | SQL_COLUMN_MISMATCH | Align the selected projection/aliases with the requested fields and known gold-style columns. |
| 6 | example_013 | LLM_FREE_AGENT_BASELINE | 0.3911 | 0.0000 | 1.0000 | 0.4237 | SQL_COLUMN_MISMATCH | Align the selected projection/aliases with the requested fields and known gold-style columns. |
| 7 | example_006 | LLM_FREE_AGENT_BASELINE | 0.3960 | 0.0000 | 0.7480 | 0.6780 | SQL_COLUMN_MISMATCH | Align the selected projection/aliases with the requested fields and known gold-style columns. |
| 8 | example_012 | LLM_FREE_AGENT_BASELINE | 0.4021 | 0.0000 | 1.0000 | 0.4533 | SQL_COLUMN_MISMATCH | Align the selected projection/aliases with the requested fields and known gold-style columns. |
| 9 | example_009 | LLM_FREE_AGENT_BASELINE | 0.4031 | 0.0000 | 1.0000 | 0.4606 | SQL_JOIN_MISMATCH | Add or adjust a schema-validated SQL join template for this relationship pattern. |
| 10 | example_001 | LLM_FREE_AGENT_BASELINE | 0.4056 | 0.0000 | 1.0000 | 0.4559 | SQL_COLUMN_MISMATCH | Align the selected projection/aliases with the requested fields and known gold-style columns. |
| 11 | example_011 | LLM_FREE_AGENT_BASELINE | 0.4209 | 0.0000 | 1.0000 | 0.5070 | SQL_COLUMN_MISMATCH | Align the selected projection/aliases with the requested fields and known gold-style columns. |
| 12 | example_011 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.4503 | 0.9000 | 0.0000 | 0.3590 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 13 | example_011 | SQL_ONLY_BASELINE | 0.4503 | 0.9000 | 0.0000 | 0.3590 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 14 | example_002 | LLM_FREE_AGENT_BASELINE | 0.4662 | 0.0000 | 1.0000 | 0.6654 | SQL_COLUMN_MISMATCH | Align the selected projection/aliases with the requested fields and known gold-style columns. |
| 15 | example_019 | SQL_ONLY_BASELINE | 0.4816 | 1.0000 | 0.0000 | 0.3361 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 16 | example_030 | SQL_ONLY_BASELINE | 0.4826 | 1.0000 | 0.0000 | 0.3408 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 17 | example_028 | SQL_ONLY_BASELINE | 0.4845 | 1.0000 | 0.0000 | 0.3466 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 18 | example_015 | SQL_ONLY_BASELINE | 0.4848 | 1.0000 | 0.0000 | 0.3353 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 19 | example_031 | SQL_ONLY_BASELINE | 0.4886 | 1.0000 | 0.0000 | 0.3611 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 20 | example_033 | SQL_ONLY_BASELINE | 0.4916 | 1.0000 | 0.0000 | 0.3716 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 21 | example_016 | SQL_ONLY_BASELINE | 0.4933 | 1.0000 | 0.0000 | 0.3750 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 22 | example_021 | SQL_ONLY_BASELINE | 0.4945 | 1.0000 | 0.0000 | 0.3780 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 23 | example_024 | SQL_ONLY_BASELINE | 0.4950 | 1.0000 | 0.0000 | 0.3858 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 24 | example_025 | SQL_ONLY_BASELINE | 0.5012 | 1.0000 | 0.0000 | 0.4067 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 25 | example_020 | SQL_ONLY_BASELINE | 0.5017 | 1.0000 | 0.0000 | 0.3919 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 26 | example_018 | SQL_ONLY_BASELINE | 0.5020 | 1.0000 | 0.0000 | 0.3993 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 27 | example_023 | SQL_ONLY_BASELINE | 0.5042 | 1.0000 | 0.0000 | 0.4163 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 28 | example_000 | LLM_FREE_AGENT_BASELINE | 0.5047 | 0.0000 | 1.0000 | 0.7922 | SQL_COLUMN_MISMATCH | Align the selected projection/aliases with the requested fields and known gold-style columns. |
| 29 | example_012 | SQL_ONLY_BASELINE | 0.5048 | 1.0000 | 0.0000 | 0.4163 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 30 | example_029 | SQL_ONLY_BASELINE | 0.5077 | 1.0000 | 0.0000 | 0.4156 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 31 | example_026 | SQL_ONLY_BASELINE | 0.5091 | 1.0000 | 0.0000 | 0.4218 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 32 | example_034 | SQL_ONLY_BASELINE | 0.5121 | 1.0000 | 0.0000 | 0.4283 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 33 | example_013 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.5156 | 1.0000 | 0.0000 | 0.4549 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 34 | example_017 | SQL_ONLY_BASELINE | 0.5156 | 1.0000 | 0.0000 | 0.4450 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 35 | example_013 | SQL_ONLY_BASELINE | 0.5157 | 1.0000 | 0.0000 | 0.4549 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 36 | example_022 | SQL_ONLY_BASELINE | 0.5177 | 1.0000 | 0.0000 | 0.4497 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 37 | example_027 | SQL_ONLY_BASELINE | 0.5193 | 1.0000 | 0.0000 | 0.4586 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 38 | example_032 | SQL_ONLY_BASELINE | 0.5198 | 1.0000 | 0.0000 | 0.4600 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 39 | example_001 | SQL_ONLY_BASELINE | 0.5217 | 0.9000 | 0.0000 | 0.6011 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 40 | example_003 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.5259 | 0.9000 | 0.0000 | 0.6245 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 41 | example_003 | SQL_ONLY_BASELINE | 0.5260 | 0.9000 | 0.0000 | 0.6245 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 42 | example_002 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.5354 | 0.9000 | 0.0000 | 0.6419 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 43 | example_002 | SQL_ONLY_BASELINE | 0.5354 | 0.9000 | 0.0000 | 0.6419 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 44 | example_010 | LLM_FREE_AGENT_BASELINE | 0.5585 | 0.0000 | 1.0000 | 0.9694 | SQL_COLUMN_MISMATCH | Align the selected projection/aliases with the requested fields and known gold-style columns. |
| 45 | example_014 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.5611 | 0.9000 | 0.0000 | 0.7283 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 46 | example_014 | SQL_ONLY_BASELINE | 0.5612 | 0.9000 | 0.0000 | 0.7283 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 47 | example_005 | SQL_ONLY_BASELINE | 0.5793 | 1.0000 | 0.0000 | 0.6677 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 48 | example_007 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.5894 | 0.9000 | 0.0000 | 0.8333 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 49 | example_007 | SQL_ONLY_BASELINE | 0.5894 | 0.9000 | 0.0000 | 0.8333 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 50 | example_006 | SQL_ONLY_BASELINE | 0.6264 | 1.0000 | 0.0000 | 0.8204 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 51 | example_010 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.6364 | 0.9000 | 0.0000 | 0.9825 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 52 | example_010 | SQL_ONLY_BASELINE | 0.6365 | 0.9000 | 0.0000 | 0.9825 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 53 | example_021 | LLM_FREE_AGENT_BASELINE | 0.7009 | 1.0000 | 0.7200 | 0.4408 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 54 | example_017 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.7281 | 1.0000 | 0.7000 | 0.4532 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 55 | example_032 | LLM_FREE_AGENT_BASELINE | 0.7465 | 1.0000 | 1.0000 | 0.2736 | ANSWER_WRONG_FACT | Audit answer template field selection and avoid summarizing the wrong row/value. |
| 56 | example_021 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.7629 | 1.0000 | 0.8304 | 0.4408 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 57 | example_029 | LLM_FREE_AGENT_BASELINE | 0.7805 | 1.0000 | 1.0000 | 0.3725 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 58 | example_030 | LLM_FREE_AGENT_BASELINE | 0.7805 | 1.0000 | 1.0000 | 0.3823 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 59 | example_029 | TEMPLATE_FIRST | 0.7806 | 1.0000 | 1.0000 | 0.3725 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 60 | example_025 | LLM_FREE_AGENT_BASELINE | 0.7819 | 1.0000 | 1.0000 | 0.3912 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 61 | example_033 | TEMPLATE_FIRST | 0.7825 | 1.0000 | 1.0000 | 0.3951 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 62 | example_011 | SQL_FIRST_API_VERIFY | 0.7829 | 0.9000 | 1.0000 | 0.5141 | DRY_RUN_ONLY | Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations. |
| 63 | example_011 | TEMPLATE_FIRST | 0.7829 | 0.9000 | 1.0000 | 0.5141 | DRY_RUN_ONLY | Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations. |
| 64 | example_033 | LLM_FREE_AGENT_BASELINE | 0.7832 | 1.0000 | 1.0000 | 0.3951 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 65 | example_031 | LLM_FREE_AGENT_BASELINE | 0.7852 | 1.0000 | 1.0000 | 0.3985 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 66 | example_024 | LLM_FREE_AGENT_BASELINE | 0.7859 | 1.0000 | 1.0000 | 0.4050 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 67 | example_028 | LLM_FREE_AGENT_BASELINE | 0.7873 | 1.0000 | 1.0000 | 0.4037 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 68 | example_019 | LLM_FREE_AGENT_BASELINE | 0.7874 | 1.0000 | 1.0000 | 0.4029 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 69 | example_020 | LLM_FREE_AGENT_BASELINE | 0.7878 | 1.0000 | 1.0000 | 0.3929 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 70 | example_020 | TEMPLATE_FIRST | 0.7879 | 1.0000 | 1.0000 | 0.3929 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 71 | example_017 | LLM_FREE_AGENT_BASELINE | 0.7894 | 1.0000 | 1.0000 | 0.4532 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 72 | example_001 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.7913 | 0.9000 | 1.0000 | 0.5468 | DRY_RUN_ONLY | Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations. |
| 73 | example_001 | TEMPLATE_FIRST | 0.7914 | 0.9000 | 1.0000 | 0.5468 | DRY_RUN_ONLY | Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations. |
| 74 | example_016 | LLM_FREE_AGENT_BASELINE | 0.7915 | 1.0000 | 1.0000 | 0.4161 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 75 | example_001 | SQL_FIRST_API_VERIFY | 0.7915 | 0.9000 | 1.0000 | 0.5468 | DRY_RUN_ONLY | Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations. |
| 76 | example_018 | LLM_FREE_AGENT_BASELINE | 0.7934 | 1.0000 | 1.0000 | 0.4195 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 77 | example_029 | SQL_FIRST_API_VERIFY | 0.7941 | 1.0000 | 1.0000 | 0.3725 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 78 | example_029 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.7944 | 1.0000 | 1.0000 | 0.3725 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 79 | example_013 | TEMPLATE_FIRST | 0.7946 | 1.0000 | 1.0000 | 0.4324 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 80 | example_015 | LLM_FREE_AGENT_BASELINE | 0.7947 | 1.0000 | 1.0000 | 0.4154 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 81 | example_027 | LLM_FREE_AGENT_BASELINE | 0.7947 | 1.0000 | 1.0000 | 0.4241 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 82 | example_007 | TEMPLATE_FIRST | 0.7948 | 0.9000 | 0.7760 | 0.7902 | API_PATH_MISMATCH | Add endpoint selection rules or endpoint catalog coverage for this query family. |
| 83 | example_027 | TEMPLATE_FIRST | 0.7948 | 1.0000 | 1.0000 | 0.4241 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 84 | example_007 | SQL_FIRST_API_VERIFY | 0.7949 | 0.9000 | 0.7760 | 0.7902 | API_PATH_MISMATCH | Add endpoint selection rules or endpoint catalog coverage for this query family. |
| 85 | example_015 | TEMPLATE_FIRST | 0.7949 | 1.0000 | 1.0000 | 0.4154 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 86 | example_013 | SQL_FIRST_API_VERIFY | 0.7956 | 1.0000 | 1.0000 | 0.4324 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 87 | example_030 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.7965 | 1.0000 | 1.0000 | 0.3823 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 88 | example_030 | TEMPLATE_FIRST | 0.7966 | 1.0000 | 1.0000 | 0.3823 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 89 | example_034 | LLM_FREE_AGENT_BASELINE | 0.7967 | 1.0000 | 1.0000 | 0.4329 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 90 | example_030 | SQL_FIRST_API_VERIFY | 0.7967 | 1.0000 | 1.0000 | 0.3823 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 91 | example_034 | TEMPLATE_FIRST | 0.7968 | 1.0000 | 1.0000 | 0.4329 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 92 | example_033 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.7972 | 1.0000 | 1.0000 | 0.3951 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 93 | example_023 | LLM_FREE_AGENT_BASELINE | 0.7972 | 1.0000 | 1.0000 | 0.4419 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 94 | example_033 | SQL_FIRST_API_VERIFY | 0.7973 | 1.0000 | 1.0000 | 0.3951 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 95 | example_026 | LLM_FREE_AGENT_BASELINE | 0.7976 | 1.0000 | 1.0000 | 0.4308 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 96 | example_026 | TEMPLATE_FIRST | 0.7977 | 1.0000 | 1.0000 | 0.4308 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 97 | example_021 | TEMPLATE_FIRST | 0.7992 | 1.0000 | 1.0000 | 0.4408 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 98 | example_025 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.7996 | 1.0000 | 1.0000 | 0.3912 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 99 | example_025 | SQL_FIRST_API_VERIFY | 0.7996 | 1.0000 | 1.0000 | 0.3912 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 100 | example_025 | TEMPLATE_FIRST | 0.7997 | 1.0000 | 1.0000 | 0.3912 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 101 | example_020 | SQL_FIRST_API_VERIFY | 0.8011 | 1.0000 | 1.0000 | 0.3929 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 102 | example_031 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.8012 | 1.0000 | 1.0000 | 0.3985 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 103 | example_031 | TEMPLATE_FIRST | 0.8013 | 1.0000 | 1.0000 | 0.3985 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 104 | example_020 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.8014 | 1.0000 | 1.0000 | 0.3929 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 105 | example_022 | LLM_FREE_AGENT_BASELINE | 0.8014 | 1.0000 | 1.0000 | 0.4425 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 106 | example_031 | SQL_FIRST_API_VERIFY | 0.8014 | 1.0000 | 1.0000 | 0.3985 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 107 | example_022 | TEMPLATE_FIRST | 0.8015 | 1.0000 | 1.0000 | 0.4425 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 108 | example_012 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.8027 | 1.0000 | 1.0000 | 0.4574 | ANSWER_WRONG_FACT | Audit answer template field selection and avoid summarizing the wrong row/value. |
| 109 | example_012 | SQL_FIRST_API_VERIFY | 0.8028 | 1.0000 | 1.0000 | 0.4574 | ANSWER_WRONG_FACT | Audit answer template field selection and avoid summarizing the wrong row/value. |
| 110 | example_012 | TEMPLATE_FIRST | 0.8028 | 1.0000 | 1.0000 | 0.4574 | ANSWER_WRONG_FACT | Audit answer template field selection and avoid summarizing the wrong row/value. |
| 111 | example_028 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.8033 | 1.0000 | 1.0000 | 0.4037 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 112 | example_019 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.8034 | 1.0000 | 1.0000 | 0.4029 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 113 | example_028 | TEMPLATE_FIRST | 0.8034 | 1.0000 | 1.0000 | 0.4037 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 114 | example_003 | SQL_FIRST_API_VERIFY | 0.8035 | 0.9000 | 1.0000 | 0.6473 | DRY_RUN_ONLY | Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations. |
| 115 | example_019 | SQL_FIRST_API_VERIFY | 0.8035 | 1.0000 | 1.0000 | 0.4029 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 116 | example_024 | SQL_FIRST_API_VERIFY | 0.8035 | 1.0000 | 1.0000 | 0.4050 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 117 | example_028 | SQL_FIRST_API_VERIFY | 0.8035 | 1.0000 | 1.0000 | 0.4037 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 118 | example_017 | TEMPLATE_FIRST | 0.8035 | 1.0000 | 1.0000 | 0.4532 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 119 | example_019 | TEMPLATE_FIRST | 0.8035 | 1.0000 | 1.0000 | 0.4029 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 120 | example_024 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.8036 | 1.0000 | 1.0000 | 0.4050 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 121 | example_017 | SQL_FIRST_API_VERIFY | 0.8036 | 1.0000 | 1.0000 | 0.4532 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 122 | example_024 | TEMPLATE_FIRST | 0.8036 | 1.0000 | 1.0000 | 0.4050 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 123 | example_003 | TEMPLATE_FIRST | 0.8037 | 0.9000 | 1.0000 | 0.6473 | DRY_RUN_ONLY | Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations. |
| 124 | example_006 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.8074 | 1.0000 | 0.7480 | 0.7234 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 125 | example_006 | SQL_FIRST_API_VERIFY | 0.8074 | 1.0000 | 0.7480 | 0.7234 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 126 | example_016 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.8075 | 1.0000 | 1.0000 | 0.4161 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 127 | example_018 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.8075 | 1.0000 | 1.0000 | 0.4195 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 128 | example_006 | TEMPLATE_FIRST | 0.8075 | 1.0000 | 0.7480 | 0.7234 | API_CALL_COUNT_MISMATCH | Emit the expected sequence of API calls or intentionally document why a call is skipped. |
| 129 | example_016 | TEMPLATE_FIRST | 0.8076 | 1.0000 | 1.0000 | 0.4161 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 130 | example_018 | TEMPLATE_FIRST | 0.8076 | 1.0000 | 1.0000 | 0.4195 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 131 | example_016 | SQL_FIRST_API_VERIFY | 0.8077 | 1.0000 | 1.0000 | 0.4161 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 132 | example_018 | SQL_FIRST_API_VERIFY | 0.8077 | 1.0000 | 1.0000 | 0.4195 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 133 | example_015 | SQL_FIRST_API_VERIFY | 0.8080 | 1.0000 | 1.0000 | 0.4154 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 134 | example_015 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.8083 | 1.0000 | 1.0000 | 0.4154 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 135 | example_027 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.8087 | 1.0000 | 1.0000 | 0.4241 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 136 | example_027 | SQL_FIRST_API_VERIFY | 0.8087 | 1.0000 | 1.0000 | 0.4241 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 137 | example_034 | SQL_FIRST_API_VERIFY | 0.8100 | 1.0000 | 1.0000 | 0.4329 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 138 | example_034 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.8103 | 1.0000 | 1.0000 | 0.4329 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 139 | example_026 | SQL_FIRST_API_VERIFY | 0.8111 | 1.0000 | 1.0000 | 0.4308 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 140 | example_026 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.8112 | 1.0000 | 1.0000 | 0.4308 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 141 | example_021 | SQL_FIRST_API_VERIFY | 0.8138 | 1.0000 | 1.0000 | 0.4408 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 142 | example_023 | SQL_FIRST_API_VERIFY | 0.8148 | 1.0000 | 1.0000 | 0.4419 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 143 | example_022 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.8149 | 1.0000 | 1.0000 | 0.4425 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 144 | example_023 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.8149 | 1.0000 | 1.0000 | 0.4419 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 145 | example_022 | SQL_FIRST_API_VERIFY | 0.8149 | 1.0000 | 1.0000 | 0.4425 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 146 | example_023 | TEMPLATE_FIRST | 0.8149 | 1.0000 | 1.0000 | 0.4419 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 147 | example_009 | SQL_FIRST_API_VERIFY | 0.8163 | 1.0000 | 1.0000 | 0.5144 | DRY_RUN_ONLY | Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations. |
| 148 | example_009 | TEMPLATE_FIRST | 0.8164 | 1.0000 | 1.0000 | 0.5144 | DRY_RUN_ONLY | Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations. |
| 149 | example_032 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.8217 | 1.0000 | 1.0000 | 0.4686 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 150 | example_032 | SQL_FIRST_API_VERIFY | 0.8218 | 1.0000 | 1.0000 | 0.4686 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 151 | example_032 | TEMPLATE_FIRST | 0.8218 | 1.0000 | 1.0000 | 0.4686 | ANSWER_TOO_GENERIC | Add a query-family answer template that names concrete SQL/API evidence. |
| 152 | example_002 | SQL_FIRST_API_VERIFY | 0.8283 | 0.9000 | 1.0000 | 0.6654 | DRY_RUN_ONLY | Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations. |
| 153 | example_002 | TEMPLATE_FIRST | 0.8284 | 0.9000 | 1.0000 | 0.6654 | DRY_RUN_ONLY | Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations. |
| 154 | example_004 | SQL_FIRST_API_VERIFY | 0.8349 | 0.9000 | 1.0000 | 0.6904 | DRY_RUN_ONLY | Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations. |
| 155 | example_009 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.8351 | 1.0000 | 1.0000 | 0.5296 | UNKNOWN | Inspect trajectory manually and add a targeted deterministic rule only if it generalizes. |
| 156 | example_004 | LLM_FREE_AGENT_BASELINE | 0.8352 | 0.9000 | 1.0000 | 0.6904 | DRY_RUN_ONLY | Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations. |
| 157 | example_009 | SQL_ONLY_BASELINE | 0.8352 | 1.0000 | 1.0000 | 0.5296 | UNKNOWN | Inspect trajectory manually and add a targeted deterministic rule only if it generalizes. |
| 158 | example_004 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.8353 | 0.9000 | 1.0000 | 0.6904 | DRY_RUN_ONLY | Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations. |
| 159 | example_004 | TEMPLATE_FIRST | 0.8353 | 0.9000 | 1.0000 | 0.6904 | DRY_RUN_ONLY | Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations. |
| 160 | example_014 | SQL_FIRST_API_VERIFY | 0.8435 | 0.9000 | 1.0000 | 0.7172 | DRY_RUN_ONLY | Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations. |
| 161 | example_014 | TEMPLATE_FIRST | 0.8435 | 0.9000 | 1.0000 | 0.7172 | DRY_RUN_ONLY | Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations. |
| 162 | example_004 | SQL_ONLY_BASELINE | 0.8486 | 0.9000 | 1.0000 | 0.6867 | UNKNOWN | Inspect trajectory manually and add a targeted deterministic rule only if it generalizes. |
| 163 | example_005 | SQL_FIRST_API_VERIFY | 0.8629 | 1.0000 | 1.0000 | 0.6630 | DRY_RUN_ONLY | Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations. |
| 164 | example_005 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.8631 | 1.0000 | 1.0000 | 0.6630 | DRY_RUN_ONLY | Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations. |
| 165 | example_005 | TEMPLATE_FIRST | 0.8632 | 1.0000 | 1.0000 | 0.6630 | DRY_RUN_ONLY | Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations. |
| 166 | example_000 | SQL_FIRST_API_VERIFY | 0.8650 | 0.9000 | 1.0000 | 0.7922 | DRY_RUN_ONLY | Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations. |
| 167 | example_000 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.8654 | 0.9000 | 1.0000 | 0.7922 | DRY_RUN_ONLY | Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations. |
| 168 | example_000 | TEMPLATE_FIRST | 0.8654 | 0.9000 | 1.0000 | 0.7922 | DRY_RUN_ONLY | Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations. |
| 169 | example_008 | SQL_FIRST_API_VERIFY | 0.8701 | 0.9000 | 1.0000 | 0.7598 | UNKNOWN | Inspect trajectory manually and add a targeted deterministic rule only if it generalizes. |
| 170 | example_008 | DETERMINISTIC_ROUTER_SELECTED_METADATA | 0.8704 | 0.9000 | 1.0000 | 0.7598 | UNKNOWN | Inspect trajectory manually and add a targeted deterministic rule only if it generalizes. |
| 171 | example_008 | SQL_ONLY_BASELINE | 0.8705 | 0.9000 | 1.0000 | 0.7598 | UNKNOWN | Inspect trajectory manually and add a targeted deterministic rule only if it generalizes. |
| 172 | example_008 | TEMPLATE_FIRST | 0.8705 | 0.9000 | 1.0000 | 0.7598 | UNKNOWN | Inspect trajectory manually and add a targeted deterministic rule only if it generalizes. |
| 173 | example_000 | SQL_ONLY_BASELINE | 0.9023 | 0.9000 | 1.0000 | 0.8682 | UNKNOWN | Inspect trajectory manually and add a targeted deterministic rule only if it generalizes. |
| 174 | example_010 | SQL_FIRST_API_VERIFY | 0.9215 | 0.9000 | 1.0000 | 0.9825 | DRY_RUN_ONLY | Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations. |
| 175 | example_010 | TEMPLATE_FIRST | 0.9218 | 0.9000 | 1.0000 | 0.9825 | DRY_RUN_ONLY | Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations. |

## Details

### example_008 / LLM_FREE_AGENT_BASELINE / 0.3261

Query: show me the field for Person: Birthday Today 001

Failure category: `SQL_COLUMN_MISMATCH`

Recommended fix: Align the selected projection/aliases with the requested fields and known gold-style columns.

Generated SQL:
```sql
SELECT "UPDATEDTIME", "PARENTARTIFACTID", "ALTDISPLAYTITLE", "CREATEDTIME", "PROPERTYID", "LABELSPROPERTY", "TYPE" FROM "dim_property" LIMIT 50
```

Gold SQL:
```sql
SELECT DISTINCT aa.property AS property_name, a.name AS segment_name
FROM hkg_br_segment_property aa
JOIN dim_segment a ON aa.segmentid = a.segmentid
WHERE a.name = 'Person: Birthday Today 001'
LIMIT 20
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/ajo/journey",
    "params": {
      "limit": 50,
      "start": 0
    }
  },
  {
    "method": "GET",
    "path": "/data/core/ups/audiences",
    "params": {
      "limit": 50,
      "start": 0
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/datasets?limit=20&filter=name:SG AND name:non loyalty"
]
```

Generated answer: The matching field evidence is: UPDATEDTIME=2026-03-29T00:37:00.000+00:00, PARENTARTIFACTID=None, ALTDISPLAYTITLE=, CREATEDTIME=2026-03-29T00:37:00.000+00:00; UPDATEDTIME=2026-03-29T00:37:00.000+00:00, PARENTARTIFACTID=None, ALTDISPLAYTITLE=, CREATEDTIME=2026-03-29T00:37:00.000+00:00; UPDATEDTIME=2026-03-29T00:37:00.000+00:00, PARENTARTIFACTID=None, ALTDISPLAYTITLE=, CREATEDTIME=2026-03-29T00:37:00.000+00:00; UPDATEDTIME=2026-03-29T00:37:00.000+00:00, PARENTARTIFACTID=None, ALTDISPLAYTITLE=, CREATEDTIME=2026-03-29T00:37:00.000+00:00; UPDATEDTIME=2026-03-29T00:37:00.000+00:00, PARENTARTIFACTID=None, ALTDISPLAYTITLE=, CREATEDTIME=2026-03-29T00:37:00.000+00:00. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: The field for the "Person: Birthday Today 001" segment is the birth date property. This field captures when a person was born and is used to identify individuals celebrating their birthday today.

### example_007 / LLM_FREE_AGENT_BASELINE / 0.3579

Query: List all datasets that use the schema 'hkg_adls_profile_count_history'.

Failure category: `SQL_COLUMN_MISMATCH`

Recommended fix: Align the selected projection/aliases with the requested fields and known gold-style columns.

Generated SQL:
```sql
SELECT COUNT(*) AS count FROM "dim_collection" WHERE LOWER(CAST("NAME" AS VARCHAR)) LIKE LOWER('%hkg_adls_profile_count_history%')
```

Gold SQL:
```sql
SELECT DISTINCT D.collectionid AS collection_id,
       D.name AS collection_name
FROM hkg_br_blueprint_collection AS SD
JOIN dim_collection AS D ON SD.collectionid = D.collectionid
JOIN dim_blueprint AS S ON SD.blueprintid = S.blueprintid
WHERE S.name = 'hkg_adls_profile_count_history'
LIMIT 3
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/catalog/dataSets",
    "params": {
      "filter": "schemaName==\"hkg_adls_profile_count_history\"",
      "limit": "3"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/dataSets?limit=3&filter=schemaName==\"WF HEMI Account Attribute Retail Fiserv Schema\"",
  "GET /data/foundation/schemaregistry/tenant/schemas/{schema_id}"
]
```

Generated answer: Based on the evidence provided, 1 datasets have been ingested using the same schema. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence provided, no datasets use the schema 'hkg_adls_profile_count_history'. The SQL query returned zero results, and the dataset returned from the API does not match this schema.

### example_005 / LLM_FREE_AGENT_BASELINE / 0.3706

Query: Export a list of all destinations in the b2b-prod sandbox, sorted by most recently modified, including all columns associated with each destination, and include the 'modified' column for validation.

Failure category: `SQL_COLUMN_MISMATCH`

Recommended fix: Align the selected projection/aliases with the requested fields and known gold-style columns.

Generated SQL:
```sql
SELECT "DATAFLOWNAME", "UPDATEDTIME", "LABELSTARGET", "STATE", "TARGETID", "CREATEDTIME", "CONNECTIONSPECID", "NAME" FROM "dim_target" WHERE LOWER(CAST("DATAFLOWNAME" AS VARCHAR)) LIKE LOWER('%modified%') LIMIT 50
```

Gold SQL:
```sql
SELECT D.targetId AS target_id,
       D.dataflowName AS dataflow_name,
       D.name AS target_name,
       D.description,
       D.state,
       D.connectionSpecId AS connection_spec_id,
       D.createdTime AS created_time,
       D.updatedTime AS modified,
       D.interval,
       D.frequency
FROM dim_target AS D
ORDER BY D.updatedTime DESC
LIMIT 50
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/flowservice/flows",
    "params": {
      "limit": "50",
      "property": "inheritedAttributes.properties.isDestinationFlow==true",
      "sort": "updatedTime:desc"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/flowservice/flows?limit=50&sort=updatedTime:desc&property=inheritedAttributes.properties.isDestinationFlow==true"
]
```

Generated answer: No destinations were found in the database. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence provided, only one destination was found: "Activate segments to S3 Feed" (amazon-s3 target) with a modification timestamp of 2026-04-14 at 16:15:03 UTC. However, this result is from the "external-benchmarking" sandbox rather than the "b2b-prod" sandbox you requested, and the API response is incomplete, so the full export cannot be validated from the evidence shown.

### example_014 / LLM_FREE_AGENT_BASELINE / 0.3709

Query: Show me all entities created by download

Failure category: `SQL_COLUMN_MISMATCH`

Recommended fix: Align the selected projection/aliases with the requested fields and known gold-style columns.

Generated SQL:
```sql
SELECT "SEGMENTID", "CAMPAIGNID", "LABELSSEGMENT", "LABELSCAMPAIGN" FROM "br_campaign_segment" LIMIT 50
```

Gold SQL:
```sql
SELECT DISTINCT collectionid AS collection_id, name AS collection_name, createdtime AS created_time
FROM dim_collection
WHERE createdby ILIKE '%download%'
LIMIT 20
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/audit/events",
    "params": {
      "limit": "20",
      "property": "action==create"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/audit/events?property=action==create&limit=20"
]
```

Generated answer: Based on the evidence provided, entities created by download are: SEGMENTID=2869d771-1546-4458-a2cd-fb7235a69c94, CAMPAIGNID=9f4ebca4-2fdd-4873-95f5-8d66bab358c6, LABELSSEGMENT=[], LABELSCAMPAIGN=[]; SEGMENTID=8d1eda81-5df9-4d7a-ab48-56d49c4b1c8d, CAMPAIGNID=9f4ebca4-2fdd-4873-95f5-8d66bab358c6, LABELSSEGMENT=[], LABELSCAMPAIGN=[]; SEGMENTID=bd33fef0-c2d1-4e30-bb6a-a46e6b4579a8, CAMPAIGNID=9f4ebca4-2fdd-4873-95f5-8d66bab358c6, LABELSSEGMENT=[], LABELSCAMPAIGN=[]. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence provided, no entities were created by download. The SQL query returned zero results, and the audit log shows only a Segment entity that was created by a user, not by a download process.

### example_003 / LLM_FREE_AGENT_BASELINE / 0.3766

Query: List all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, totalProfiles, createdTime, updatedTime, and used in other audience count for each audience. Remove any row limit from the results.

Failure category: `SQL_COLUMN_MISMATCH`

Recommended fix: Align the selected projection/aliases with the requested fields and known gold-style columns.

Generated SQL:
```sql
SELECT COUNT(*) AS count FROM "dim_target" WHERE LOWER(CAST("DATAFLOWNAME" AS VARCHAR)) LIKE LOWER('%SMS Opt-In%')
```

Gold SQL:
```sql
SELECT 
    a.segmentid AS segment_id,
    a.name AS segment_name,
    a.totalmembers AS total_profiles,
    a.createdTime AS created_time,
    a.updatedTime AS updated_time
FROM dim_segment a
JOIN hkg_br_segment_target ad ON a.segmentid = ad.segmentid
JOIN dim_target d ON ad.targetId = d.targetId
WHERE d.dataflowName = 'SMS Opt-In'
ORDER BY a.name
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/audiences",
    "params": {
      "limit": "5",
      "property": "destinationId==<destination_id>"
    }
  },
  {
    "method": "GET",
    "path": "/data/foundation/flowservice/flows",
    "params": {
      "limit": "5",
      "property": "inheritedAttributes.properties.isDestinationFlow==true"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/audiences?property=destinationId==<destination_id>&limit=5",
  "GET /data/foundation/flowservice/flows?property=inheritedAttributes.properties.isDestinationFlow==true&limit=5"
]
```

Generated answer: Based on the SQL evidence, 1 audience(s) match: unnamed audience mapped to a destination. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence provided, there is no data available to answer this question. The SQL query returned zero rows, the API call to retrieve audiences failed with a 400 error, and the flow service data that was successfully retrieved does not contain information about audiences connected to the SMS Opt-In destination.

### example_013 / LLM_FREE_AGENT_BASELINE / 0.3911

Query: Show recent changes in datasets.

Failure category: `SQL_COLUMN_MISMATCH`

Recommended fix: Align the selected projection/aliases with the requested fields and known gold-style columns.

Generated SQL:
```sql
SELECT "ISIDENTITYENABLED", "ROWCOUNT", "UPDATEDTIME", "NAME", "COLLECTIONID", "CREATEDTIME", "UPDATEDBY", "CREATEDCLIENTID", "LABELSCOLLECTION" FROM "dim_collection" LIMIT 50
```

Gold SQL:
```sql
SELECT DISTINCT D.COLLECTIONID AS collection_id,
       D.NAME AS collection_name,
       D.UPDATEDTIME AS updated_time
FROM DIM_COLLECTION AS D
WHERE D.UPDATEDTIME >= DATEADD(DAY, -90, CURRENT_DATE)
ORDER BY D.UPDATEDTIME DESC
LIMIT 50
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/audit/events",
    "params": {
      "limit": "50",
      "orderBy": "-timestamp",
      "property": "assetType==dataset"
    }
  }
]
```

Gold API:
```json
[
  "GET /audit/events?property=assetType==dataset&orderBy=-timestamp&limit=50"
]
```

Generated answer: Based on the evidence provided, matching datasets are: BR_Namespace_Destination, BR_Segment_Destination, DIM_Destination, profile_dim_date, hkg_adls_profile_count_history, Profile Export For Destination - Merge Policy - 22a941a9-e598-45f8-846b-c9a8889f5035, weRetail: Customer Actions, weRetail: CRM, hkg_adls_segment_profile_history, and Journey Inbound. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: The most recent dataset changes occurred on April 14, 2026, with the latest updates to **hkg_adls_segment_profile_history** (9:08 PM UTC) and **hkg_adls_profile_count_history** (9:08 PM UTC). Several profile and segment snapshots were also updated throughout that day, with the audit log showing a dataset update permission granted on March 29 for the "weRetail: Customer Actions" dataset.

### example_006 / LLM_FREE_AGENT_BASELINE / 0.3960

Query: How many datasets have been ingested using the same schema in the prod sandbox?

Failure category: `SQL_COLUMN_MISMATCH`

Recommended fix: Align the selected projection/aliases with the requested fields and known gold-style columns.

Generated SQL:
```sql
SELECT COUNT(*) AS count FROM "dim_collection"
```

Gold SQL:
```sql
SELECT S.blueprintid AS blueprint_id,
       S.name AS blueprint_name,
       COUNT(DISTINCT DS.collectionid) AS collection_count
FROM dim_collection AS D
JOIN hkg_br_blueprint_collection AS DS ON D.collectionid = DS.collectionid
JOIN dim_blueprint AS S ON DS.blueprintid = S.blueprintid
GROUP BY S.blueprintid,
         S.name
HAVING COUNT(DISTINCT DS.collectionid) > 1
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/catalog/dataSets",
    "params": {
      "limit": "25",
      "property": "schema.name"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/dataSets?limit=25&property=schema.name",
  "GET /data/foundation/schemaregistry/tenant/schemas/{schema_id}"
]
```

Generated answer: Based on the evidence provided, 37 datasets have been ingested using the same schema. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence provided, **2 datasets** have been ingested using the same schema in the prod sandbox. These datasets both use the "Journey Inbound External Segment Profile Schema."

### example_012 / LLM_FREE_AGENT_BASELINE / 0.4021

Query: List all audiences in the sandbox that have been mapped to new destinations in the last 3 months.

Failure category: `SQL_COLUMN_MISMATCH`

Recommended fix: Align the selected projection/aliases with the requested fields and known gold-style columns.

Generated SQL:
```sql
SELECT "DATAFLOWNAME", "UPDATEDTIME", "LABELSTARGET", "STATE", "TARGETID", "CREATEDTIME", "CONNECTIONSPECID", "NAME" FROM "dim_target"
```

Gold SQL:
```sql
SELECT DISTINCT A.segmentid AS segment_id, A.name AS segment_name, D.targetId AS target_id, D.name AS target_name
FROM dim_segment AS A
JOIN hkg_br_segment_target AS AD ON A.segmentid = AD.segmentid
JOIN dim_target AS D ON AD.targetId = D.targetId
WHERE D.createdTime >= DATEADD(MONTH, -3, CURRENT_DATE)
LIMIT 3
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/audit/events",
    "params": {
      "limit": "3",
      "property": "assetType==destination"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/audit/events?property=assetType==destination&limit=3"
]
```

Generated answer: Based on the SQL evidence, 1 audience(s) match: amazon-s3 (updated 2026-04-14) mapped to Activate segments to S3 Feed on 2026-03-29. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence, one audience has been newly mapped to a destination in the last 3 months: **Gender: Male**, which was mapped to Amazon S3 on March 29, 2026. This is confirmed by both the SQL query showing the segment-to-destination mapping and the audit log entry recording the activation creation event.

### example_009 / LLM_FREE_AGENT_BASELINE / 0.4031

Query: Provide more details for the schema 'weRetail: Customer Actions'

Failure category: `SQL_JOIN_MISMATCH`

Recommended fix: Add or adjust a schema-validated SQL join template for this relationship pattern.

Generated SQL:
```sql
SELECT "SEGMENTID", "UPDATEDTIME", "ISACCOUNTSEGMENT", "NAME", "EVALUATIONCOMPLETEDTIME", "LABELSSEGMENT", "LIFECYCLESTATUS", "CREATEDTIME", "TYPE", "MERGEPOLICYID" FROM "dim_segment" WHERE LOWER(CAST("NAME" AS VARCHAR)) LIKE LOWER('%weRetail: Customer Actions%') LIMIT 50
```

Gold SQL:
```sql
SELECT S.BLUEPRINTID AS blueprint_id,
       S.NAME,
       S.CLASS,
       S.ISPROFILEENABLED,
       S.UPDATEDTIME AS updated_time,
       S.REQUIREDFIELDS AS required_fields,
       COUNT(DISTINCT SD.COLLECTIONID) AS collection_count,
       COUNT(DISTINCT SA.PROPERTY) AS property_count
FROM DIM_BLUEPRINT AS S
LEFT JOIN HKG_BR_BLUEPRINT_COLLECTION AS SD ON S.BLUEPRINTID = SD.BLUEPRINTID
LEFT JOIN HKG_BR_BLUEPRINT_PROPERTY AS SA ON S.BLUEPRINTID = SA.BLUEPRINTID
WHERE LOWER(S.NAME) = LOWER('weRetail: Customer Actions')
GROUP BY S.BLUEPRINTID,
         S.NAME,
         S.CLASS,
         S.ISPROFILEENABLED,
         S.UPDATEDTIME,
         S.REQUIREDFIELDS
LIMIT 3
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/schemas",
    "params": {
      "filter": "name==weRetail: Customer Actions",
      "limit": "5"
    }
  }
]
```

Gold API:
```json
[
  "GET /schemas?limit=5&filter=name==weRetail: Customer Actions"
]
```

Generated answer: Based on the evidence provided, no datasets use the schema 'weRetail: Customer Actions'. The SQL query returned zero results, and live API verification was not executed because Adobe credentials are unavailable.

Gold answer: The 'weRetail: Customer Actions' schema is an Experience Event-based schema that tracks customer interactions. It has six properties organized across one collection, with no required fields, and is profile-enabled to allow customer identity tracking. The schema was last updated on March 29, 2026.

### example_001 / LLM_FREE_AGENT_BASELINE / 0.4056

Query: Give me inactive journeys

Failure category: `SQL_COLUMN_MISMATCH`

Recommended fix: Align the selected projection/aliases with the requested fields and known gold-style columns.

Generated SQL:
```sql
SELECT "IMSORGID", "LASTDEPLOYEDTIME", "STATE", "SANDBOXNAME", "NAME", "SANDBOXID", "STATUS", "CAMPAIGNID" FROM "dim_campaign" WHERE LOWER(CAST("STATUS" AS VARCHAR)) LIKE LOWER('%inactive%') LIMIT 50
```

Gold SQL:
```sql
SELECT J.CAMPAIGNID AS campaign_id,
       J.NAME AS campaign_name,
       J.STATE AS campaign_state,
       J.UPDATEDTIME AS updated_time
FROM DIM_CAMPAIGN AS J
WHERE LOWER(J.STATE) NOT IN ('deployed', 'redeployed')
LIMIT 50
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/ajo/journey",
    "params": {
      "filter": "status!=live"
    }
  }
]
```

Gold API:
```json
[
  "GET /ajo/journey?filter=status!=live"
]
```

Generated answer: No inactive journeys were found in the database, and live API verification was not executed because Adobe credentials are unavailable.

Gold answer: There are no active journeys currently. However, there are 2 inactive campaigns: the Birthday Message campaign (last updated March 31) and the Gold Tier Welcome Email campaign (created March 31).

### example_011 / LLM_FREE_AGENT_BASELINE / 0.4209

Query: How many schemas do I have?

Failure category: `SQL_COLUMN_MISMATCH`

Recommended fix: Align the selected projection/aliases with the requested fields and known gold-style columns.

Generated SQL:
```sql
SELECT COUNT(*) AS count FROM "dim_collection"
```

Gold SQL:
```sql
SELECT COUNT(DISTINCT S.blueprintid) AS blueprint_count
FROM dim_blueprint AS S
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/schemas",
    "params": {
      "limit": "25"
    }
  }
]
```

Gold API:
```json
[
  "GET /schemas?limit=25"
]
```

Generated answer: You have 37 schemas. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: You have **74 schemas**. This count comes from your blueprint query, and is confirmed by the API response from Adobe's Schema Registry, which shows your tenant schemas are available.

### example_011 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.4503

Query: How many schemas do I have?

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT COUNT(DISTINCT B."BLUEPRINTID") AS blueprint_count FROM "dim_blueprint" AS B
```

Gold SQL:
```sql
SELECT COUNT(DISTINCT S.blueprintid) AS blueprint_count
FROM dim_blueprint AS S
```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /schemas?limit=25"
]
```

Generated answer: You have 74 schemas. API evidence was not requested.

Gold answer: You have **74 schemas**. This count comes from your blueprint query, and is confirmed by the API response from Adobe's Schema Registry, which shows your tenant schemas are available.

### example_011 / SQL_ONLY_BASELINE / 0.4503

Query: How many schemas do I have?

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT COUNT(DISTINCT B."BLUEPRINTID") AS blueprint_count FROM "dim_blueprint" AS B
```

Gold SQL:
```sql
SELECT COUNT(DISTINCT S.blueprintid) AS blueprint_count
FROM dim_blueprint AS S
```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /schemas?limit=25"
]
```

Generated answer: You have 74 schemas. API evidence was not requested.

Gold answer: You have **74 schemas**. This count comes from your blueprint query, and is confirmed by the API response from Adobe's Schema Registry, which shows your tenant schemas are available.

### example_002 / LLM_FREE_AGENT_BASELINE / 0.4662

Query: List all journeys

Failure category: `SQL_COLUMN_MISMATCH`

Recommended fix: Align the selected projection/aliases with the requested fields and known gold-style columns.

Generated SQL:
```sql
SELECT "UPDATEDTIME", "STARTDATE", "LABELSCAMPAIGN", "IMSORGID", "LASTDEPLOYEDTIME", "STATE", "CAMPAIGNTYPE", "STOPPEDTIME", "FINISHEDTIME", "SEMANTICLABELS", "SANDBOXNAME", "NAME", "SANDBOXID", "STATUS", "CAMPAIGNID", "CAMPAIGNACTIVITYCOUNT" FROM "dim_campaign"
```

Gold SQL:
```sql
SELECT CAMPAIGN.NAME AS CAMPAIGNNAME,
       CAMPAIGN.CAMPAIGNID
FROM DIM_CAMPAIGN AS CAMPAIGN
LIMIT 10
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/ajo/journey",
    "params": {
      "pageSize": "10"
    }
  }
]
```

Gold API:
```json
[
  "GET /ajo/journey?pageSize=10"
]
```

Generated answer: Based on the available evidence, there are 2 journeys found in the database: Birthday Message and Gold Tier Welcome Email. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the available evidence, there are two journeys found in the database: Birthday Message and Gold Tier Welcome Email. However, the Adobe Journey Optimizer API returned no results when queried, suggesting a potential discrepancy between the database records and what the API is currently returning.

### example_019 / SQL_ONLY_BASELINE / 0.4816

Query: List all merge policies in this sandbox.

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT "SEGMENTID", "CAMPAIGNID", "LABELSSEGMENT", "LABELSCAMPAIGN" FROM "br_campaign_segment"
```

Gold SQL:
```sql

```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/core/ups/config/mergePolicies?limit=10"
]
```

Generated answer: Merge policy information requires Adobe API evidence. API evidence was not requested.

Gold answer: The sandbox has at least two merge policies. The primary one is "Default Timebased," which uses timestamp-ordered attribute merging and is set as the default policy for this sandbox. A second merge policy also exists, though the full details are truncated in the response.

### example_030 / SQL_ONLY_BASELINE / 0.4826

Query: Show the details of batch 01KP69BPA5ZKFB7HCDYPE4GN6F.

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT "SEGMENTID", "CAMPAIGNID", "LABELSSEGMENT", "LABELSCAMPAIGN" FROM "br_campaign_segment" LIMIT 50
```

Gold SQL:
```sql

```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/batches/01KP69BPA5ZKFB7HCDYPE4GN6F"
]
```

Generated answer: Batch details require live API evidence. API evidence was not requested.

Gold answer: Batch 01KP69BPA5ZKFB7HCDYPE4GN6F is currently inactive. It's a replay batch created by the Adobe Unified Profile export service for dataset 69c8d6c9b9966265fc8e4ea4, and it appears to have predecessor batches as part of its replay history.

### example_028 / SQL_ONLY_BASELINE / 0.4845

Query: List the most recently created batches.

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT "SEGMENTID", "CAMPAIGNID", "LABELSSEGMENT", "LABELSCAMPAIGN" FROM "br_campaign_segment" LIMIT 50
```

Gold SQL:
```sql

```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/batches?limit=100&orderBy=desc:created"
]
```

Generated answer: Batch details require live API evidence. API evidence was not requested.

Gold answer: Based on the API response, there is one batch currently visible with a processing status. The batch is actively being ingested with some datasets completing successfully while others are still in progress.

### example_015 / SQL_ONLY_BASELINE / 0.4848

Query: How many tags exist in this sandbox?

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT COUNT(*) AS count FROM "br_campaign_segment"
```

Gold SQL:
```sql

```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /unifiedtags/tags?limit=20"
]
```

Generated answer: The tag count cannot be determined from the available evidence. API evidence was not requested.

Gold answer: Based on the evidence shown, there are at least 2 tags visible in the API response: "AI-Generated" and "cool." However, the response appears to be truncated, so the complete tag count from the sandbox cannot be determined from this partial data.

### example_031 / SQL_ONLY_BASELINE / 0.4886

Query: Which files are available for download in batch 69de8a0e0cc6102b5d11f01e?

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT "SEGMENTID", "CAMPAIGNID", "LABELSSEGMENT", "LABELSCAMPAIGN" FROM "br_campaign_segment" LIMIT 50
```

Gold SQL:
```sql

```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/foundation/export/batches/69de8a0e0cc6102b5d11f01e/files"
]
```

Generated answer: Batch file details require live API evidence. API evidence was not requested.

Gold answer: There is one file available for download in batch 69de8a0e0cc6102b5d11f01e (ID: 69de8a0e0cc6102b5d11f01e-DE1), but it is marked as invalid.

### example_033 / SQL_ONLY_BASELINE / 0.4916

Query: What are the daily 'timeseries.ingestion.dataset.recordsuccess.count' values between '2026-03-15' and '2026-03-31'?

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT DISTINCT C."COLLECTIONID" AS collection_id, C."NAME" AS collection_name FROM "hkg_br_blueprint_collection" AS BC JOIN "dim_collection" AS C ON BC."COLLECTIONID" = C."COLLECTIONID" JOIN "dim_blueprint" AS B ON BC."BLUEPRINTID" = B."BLUEPRINTID" WHERE B."NAME" = 'timeseries.ingestion.dataset.recordsuccess.count' LIMIT 50
```

Gold SQL:
```sql

```

Generated API:
```json
[]
```

Gold API:
```json
[
  "POST /data/infrastructure/observability/insights/metrics body={\"start\":\"2026-03-15T00:00:00.000Z\",\"end\":\"2026-03-31T23:59:59.000Z\",\"granularity\":\"day\",\"metrics\":[{\"name\":\"timeseries.ingestion.dataset.recordsuccess.count\",\"filters\":[],\"aggregator\":\"sum\"}]}"
]
```

Generated answer: Values for timeseries.ingestion.dataset.recordsuccess.count between 2026-03-15 and 2026-03-31 require live API evidence. API evidence was not requested.

Gold answer: Between March 15 and March 31, 2026, the record success count was 0 for all days except March 29th (152,120 records) and March 31st (2,701 records). The data shows virtually no ingestion activity for the first two weeks of the period, with a sudden increase near the end of the month.

### example_016 / SQL_ONLY_BASELINE / 0.4933

Query: List all tags in this sandbox.

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT "SEGMENTID", "CAMPAIGNID", "LABELSSEGMENT", "LABELSCAMPAIGN" FROM "br_campaign_segment"
```

Gold SQL:
```sql

```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /unifiedtags/tags?limit=25"
]
```

Generated answer: The requested tag list requires live API evidence. API evidence was not requested.

Gold answer: Based on the API response, the sandbox contains at least two tags: "AI-Generated" and "cool". The response appears to be truncated, so there may be additional tags not shown in the evidence.

### example_021 / SQL_ONLY_BASELINE / 0.4945

Query: Show the default merge policy for schema class '_xdm.context.profile'.

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT DISTINCT C."COLLECTIONID" AS collection_id, C."NAME" AS collection_name FROM "hkg_br_blueprint_collection" AS BC JOIN "dim_collection" AS C ON BC."COLLECTIONID" = C."COLLECTIONID" JOIN "dim_blueprint" AS B ON BC."BLUEPRINTID" = B."BLUEPRINTID" WHERE B."NAME" = '_xdm.context.profile' LIMIT 50
```

Gold SQL:
```sql

```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/core/ups/config/mergePolicies?limit=5"
]
```

Generated answer: The default merge policy requires live Adobe API evidence. API evidence was not requested.

Gold answer: The default merge policy for the schema class '_xdm.context.profile' is called **Default Timebased**. It uses timestamp-ordered attribute merging, where conflicting attributes are resolved by selecting the most recent value, and relies on the Personalized Data Graph for identity resolution.

### example_024 / SQL_ONLY_BASELINE / 0.4950

Query: Which segment definitions were updated most recently?

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT "SEGMENTID", "UPDATEDTIME", "ISACCOUNTSEGMENT", "NAME", "EVALUATIONCOMPLETEDTIME", "LABELSSEGMENT", "LIFECYCLESTATUS", "CREATEDTIME" FROM "dim_segment" LIMIT 50
```

Gold SQL:
```sql

```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/definitions?limit=3&orderBy=updateTime:desc"
]
```

Generated answer: The most recently updated segment definitions require live Adobe API evidence with names, IDs, and update times. API evidence was not requested.

Gold answer: Based on the API response sorted by creation time in descending order, the most recently created segment definition is **"Person: Birthday Today 001"** (ID: 2fdfefe1-04d0-46ce-9fbd-7611e311dd26) in the external-benchmarking sandbox. The response shows 13 total segment definitions across 5 pages, with this one appearing first in the descending creation time sort.

### example_025 / SQL_ONLY_BASELINE / 0.5012

Query: List all segment evaluation jobs.

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT "SEGMENTID", "UPDATEDTIME", "ISACCOUNTSEGMENT", "NAME", "EVALUATIONCOMPLETEDTIME", "LABELSSEGMENT", "LIFECYCLESTATUS", "CREATEDTIME" FROM "dim_segment"
```

Gold SQL:
```sql

```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/jobs?limit=3"
]
```

Generated answer: Segment evaluation job IDs, statuses, sandbox, and segment counts require live Adobe API evidence. API evidence was not requested.

Gold answer: Based on the API response, there is one segment evaluation job with status SUCCEEDED. It ran in the external-benchmarking sandbox and evaluated three segments, completing successfully with ID 63c6f78a-3a81-4bff-bc14-8b818b6774b3.

### example_020 / SQL_ONLY_BASELINE / 0.5017

Query: How many merge policies are configured in this sandbox?

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT COUNT(*) AS count FROM "br_campaign_segment"
```

Gold SQL:
```sql

```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/core/ups/config/mergePolicies?limit=10"
]
```

Generated answer: The merge policy count cannot be determined from the available evidence. API evidence was not requested.

Gold answer: Based on the API response provided, there are at least **2 merge policies** configured in the external-benchmarking sandbox. The response shows a "Default Timebased" policy and a second policy, though the full response appears to be truncated.

### example_018 / SQL_ONLY_BASELINE / 0.5020

Query: Show me the details of the tag named 'cool'.

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT "SEGMENTID", "CAMPAIGNID", "LABELSSEGMENT", "LABELSCAMPAIGN" FROM "br_campaign_segment" WHERE LOWER(CAST("LABELSSEGMENT" AS VARCHAR)) LIKE LOWER('%cool%') LIMIT 50
```

Gold SQL:
```sql

```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /unifiedtags/tags/51175a7f-aa60-4533-bef1-717b3cef7818"
]
```

Generated answer: Details for the tag named 'cool' require live API evidence, including the tag ID, name, category, and Adobe organization. API evidence was not requested.

Gold answer: I notice a discrepancy: the question asks for a tag named 'cool', but the API response shows details for a tag named 'sublist' (ID: 51175a7f-aa60-4533-bef1-717b3cef7818). The tag 'sublist' belongs to the Uncategorized category in the Adobe organization 87891E4066602D250A495F91@AdobeOrg. If you intended to look up a different tag named 'cool', that information isn't in the evidence provided.

### example_023 / SQL_ONLY_BASELINE / 0.5042

Query: List all segment definitions.

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT "SEGMENTID", "UPDATEDTIME", "ISACCOUNTSEGMENT", "NAME", "EVALUATIONCOMPLETEDTIME", "LABELSSEGMENT", "LIFECYCLESTATUS", "CREATEDTIME" FROM "dim_segment"
```

Gold SQL:
```sql

```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/definitions?limit=10"
]
```

Generated answer: The requested segment definition list requires live Adobe API evidence with definition names, IDs, and pagination counts. API evidence was not requested.

Gold answer: There are 13 segment definitions total across 2 pages. The visible segment from the first page is "Person: Birthday Today 001," which targets all profiles whose birthday falls on a specific month/day. The response was paginated with 10 results per page, so additional segment definitions exist on the second page.

### example_000 / LLM_FREE_AGENT_BASELINE / 0.5047

Query: When was the journey 'Birthday Message' published?

Failure category: `SQL_COLUMN_MISMATCH`

Recommended fix: Align the selected projection/aliases with the requested fields and known gold-style columns.

Generated SQL:
```sql
SELECT "IMSORGID", "LASTDEPLOYEDTIME", "STATE", "SANDBOXNAME", "NAME", "SANDBOXID", "STATUS", "CAMPAIGNID" FROM "dim_campaign" WHERE LOWER(CAST("SANDBOXNAME" AS VARCHAR)) LIKE LOWER('%Birthday Message%') AND LOWER(CAST("STATUS" AS VARCHAR)) LIKE LOWER('%published%') LIMIT 50
```

Gold SQL:
```sql
SELECT name AS campaign_name,
       lastdeployedtime AS published_time
FROM dim_campaign
WHERE name IN ('Birthday Message', 'Gold Tier Welcome Email')
LIMIT 50
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/ajo/journey",
    "params": {
      "filter": "name==Birthday Message"
    }
  }
]
```

Gold API:
```json
[
  "GET /ajo/journey?filter=name==Birthday Message"
]
```

Generated answer: The journey "Birthday Message" has not been published. The database shows a null published_time for this journey, and live API verification was not executed because Adobe credentials are unavailable.

Gold answer: The journey "Birthday Message" has not been published. The database shows a null published_time for this journey, and the Adobe AJO API returns no results for it.

### example_012 / SQL_ONLY_BASELINE / 0.5048

Query: List all audiences in the sandbox that have been mapped to new destinations in the last 3 months.

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT DISTINCT A."SEGMENTID" AS segment_id, A."NAME" AS segment_name, D."TARGETID" AS target_id, D."NAME" AS target_name FROM "dim_segment" AS A JOIN "hkg_br_segment_target" AS AD ON A."SEGMENTID" = AD."SEGMENTID" JOIN "dim_target" AS D ON AD."TARGETID" = D."TARGETID" WHERE D."CREATEDTIME" >= DATEADD(MONTH, -3, CURRENT_DATE) LIMIT 3
```

Gold SQL:
```sql
SELECT DISTINCT A.segmentid AS segment_id, A.name AS segment_name, D.targetId AS target_id, D.name AS target_name
FROM dim_segment AS A
JOIN hkg_br_segment_target AS AD ON A.segmentid = AD.segmentid
JOIN dim_target AS D ON AD.targetId = D.targetId
WHERE D.createdTime >= DATEADD(MONTH, -3, CURRENT_DATE)
LIMIT 3
```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/foundation/audit/events?property=assetType==destination&limit=3"
]
```

Generated answer: Based on the SQL evidence, 1 audience(s) match: Gender: Male (ID f6b93428-c021-4058-a1a2-77c277aab564) mapped to amazon-s3. API evidence was not requested.

Gold answer: Based on the evidence, one audience has been newly mapped to a destination in the last 3 months: **Gender: Male**, which was mapped to Amazon S3 on March 29, 2026. This is confirmed by both the SQL query showing the segment-to-destination mapping and the audit log entry recording the activation creation event.

### example_029 / SQL_ONLY_BASELINE / 0.5077

Query: How many batches have status 'success'?

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT COUNT(*) AS count FROM "br_campaign_segment" WHERE LOWER(CAST("LABELSSEGMENT" AS VARCHAR)) LIKE LOWER('%success%')
```

Gold SQL:
```sql

```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/batches?limit=10&status=success"
]
```

Generated answer: The batch count requires live API evidence. API evidence was not requested.

Gold answer: Based on the API response provided, there is **1 batch** with status 'success'.

### example_026 / SQL_ONLY_BASELINE / 0.5091

Query: How many segment jobs are currently processing?

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT COUNT(*) AS count FROM "dim_segment"
```

Gold SQL:
```sql

```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/jobs?limit=20"
]
```

Generated answer: The segment evaluation job count requires live Adobe API evidence. API evidence was not requested.

Gold answer: Based on the API response, **zero segment jobs are currently processing**. The only visible job in the response has a status of "SUCCEEDED," indicating it has already completed.

### example_034 / SQL_ONLY_BASELINE / 0.5121

Query: Show ingestion record counts and batch success counts for the last 90 days.

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT COUNT(*) AS count FROM "br_campaign_segment"
```

Gold SQL:
```sql

```

Generated API:
```json
[]
```

Gold API:
```json
[
  "POST /data/infrastructure/observability/insights/metrics body={\"start\":\"2026-03-01T00:00:00.000Z\",\"end\":\"2026-04-01T23:59:59.000Z\",\"granularity\":\"day\",\"metrics\":[{\"name\":\"timeseries.ingestion.dataset.recordsuccess.count\",\"filters\":[],\"aggregator\":\"sum\"},{\"name\":\"timeseries.ingestion.dataset.batchsuccess.count\",\"filters\":[],\"aggregator\":\"sum\"}]}"
]
```

Generated answer: Values for timeseries.ingestion.dataset.recordsuccess.count and timeseries.ingestion.dataset.batchsuccess.count for the requested time window require live API evidence. API evidence was not requested.

Gold answer: Based on the available data for the last 90 days, ingestion record success counts are minimal, with zero successful records recorded for most dates in March 2026. Only March 31st shows activity with 2,701 successfully ingested records. No batch success count data is included in the metrics response provided.

### example_013 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.5156

Query: Show recent changes in datasets.

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT DISTINCT D."COLLECTIONID" AS collection_id, D."NAME" AS collection_name, D."UPDATEDTIME" AS updated_time FROM "dim_collection" AS D WHERE D."UPDATEDTIME" >= DATEADD(DAY, -90, CURRENT_DATE) ORDER BY D."UPDATEDTIME" DESC LIMIT 50
```

Gold SQL:
```sql
SELECT DISTINCT D.COLLECTIONID AS collection_id,
       D.NAME AS collection_name,
       D.UPDATEDTIME AS updated_time
FROM DIM_COLLECTION AS D
WHERE D.UPDATEDTIME >= DATEADD(DAY, -90, CURRENT_DATE)
ORDER BY D.UPDATEDTIME DESC
LIMIT 50
```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /audit/events?property=assetType==dataset&orderBy=-timestamp&limit=50"
]
```

Generated answer: Based on the evidence provided, matching datasets are: hkg_adls_segment_profile_history, hkg_adls_profile_count_history, Profile-Snapshot-Export-486e2a5e-dc46-4ab6-ad5f-9cdd16db869d, Profile Export For Destination - Merge Policy - 22a941a9-e598-45f8-846b-c9a8889f5035, BR_Segment_Destination, DIM_Destination, BR_Namespace_Destination, Segmentdefinition-Snapshot-Export-3405afd1-7c78-4aff-84e6-d2136ffcea93, weRetail: CRM, and weRetail: Customer Actions. API evidence was not requested.

Gold answer: The most recent dataset changes occurred on April 14, 2026, with the latest updates to **hkg_adls_segment_profile_history** (9:08 PM UTC) and **hkg_adls_profile_count_history** (9:08 PM UTC). Several profile and segment snapshots were also updated throughout that day, with the audit log showing a dataset update permission granted on March 29 for the "weRetail: Customer Actions" dataset.

### example_017 / SQL_ONLY_BASELINE / 0.5156

Query: Which tags belong to the category 'Uncategorized'?

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT "SEGMENTID", "CAMPAIGNID", "LABELSSEGMENT", "LABELSCAMPAIGN" FROM "br_campaign_segment" WHERE LOWER(CAST("LABELSSEGMENT" AS VARCHAR)) LIKE LOWER('%Uncategorized%') LIMIT 50
```

Gold SQL:
```sql

```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /unifiedtags/tagCategory?limit=100",
  "GET /unifiedtags/tags?limit=100&tagCategoryId=Uncategorized-87891E4066602D250A495F91@AdobeOrg"
]
```

Generated answer: Details for the tag named 'Uncategorized' require live API evidence, including the tag ID, name, category, and Adobe organization. API evidence was not requested.

Gold answer: Based on the evidence, the Uncategorized category contains at least the tags "AI-Generated" and "cool." However, the API response is incomplete—the category metadata indicates there are 5 tags total, but only 2 are shown in the truncated evidence.

### example_013 / SQL_ONLY_BASELINE / 0.5157

Query: Show recent changes in datasets.

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT DISTINCT D."COLLECTIONID" AS collection_id, D."NAME" AS collection_name, D."UPDATEDTIME" AS updated_time FROM "dim_collection" AS D WHERE D."UPDATEDTIME" >= DATEADD(DAY, -90, CURRENT_DATE) ORDER BY D."UPDATEDTIME" DESC LIMIT 50
```

Gold SQL:
```sql
SELECT DISTINCT D.COLLECTIONID AS collection_id,
       D.NAME AS collection_name,
       D.UPDATEDTIME AS updated_time
FROM DIM_COLLECTION AS D
WHERE D.UPDATEDTIME >= DATEADD(DAY, -90, CURRENT_DATE)
ORDER BY D.UPDATEDTIME DESC
LIMIT 50
```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /audit/events?property=assetType==dataset&orderBy=-timestamp&limit=50"
]
```

Generated answer: Based on the evidence provided, matching datasets are: hkg_adls_segment_profile_history, hkg_adls_profile_count_history, Profile-Snapshot-Export-486e2a5e-dc46-4ab6-ad5f-9cdd16db869d, Profile Export For Destination - Merge Policy - 22a941a9-e598-45f8-846b-c9a8889f5035, BR_Segment_Destination, DIM_Destination, BR_Namespace_Destination, Segmentdefinition-Snapshot-Export-3405afd1-7c78-4aff-84e6-d2136ffcea93, weRetail: CRM, and weRetail: Customer Actions. API evidence was not requested.

Gold answer: The most recent dataset changes occurred on April 14, 2026, with the latest updates to **hkg_adls_segment_profile_history** (9:08 PM UTC) and **hkg_adls_profile_count_history** (9:08 PM UTC). Several profile and segment snapshots were also updated throughout that day, with the audit log showing a dataset update permission granted on March 29 for the "weRetail: Customer Actions" dataset.

### example_022 / SQL_ONLY_BASELINE / 0.5177

Query: How many segment definitions exist in this sandbox?

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT COUNT(*) AS count FROM "dim_segment"
```

Gold SQL:
```sql

```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/definitions?limit=100"
]
```

Generated answer: Segment definition details require live Adobe API evidence with definition names, IDs, and counts. API evidence was not requested.

Gold answer: Based on the API response, there are **13 segment definitions** in the external-benchmarking sandbox, as indicated by the `totalCount` field in the pagination metadata.

### example_027 / SQL_ONLY_BASELINE / 0.5193

Query: Show all segment jobs with status 'QUEUED'.

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT "SEGMENTID", "NAME", "LIFECYCLESTATUS", "MERGEPOLICYID" FROM "dim_segment" WHERE LOWER(CAST("NAME" AS VARCHAR)) LIKE LOWER('%QUEUED%') LIMIT 50
```

Gold SQL:
```sql

```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/jobs?limit=10"
]
```

Generated answer: Segment evaluation job IDs, statuses, sandbox, and segment counts require live Adobe API evidence. API evidence was not requested.

Gold answer: Based on the API response provided, there are no segment jobs with status 'QUEUED'. The single job returned has a status of 'SUCCEEDED'.

### example_032 / SQL_ONLY_BASELINE / 0.5198

Query: Show failed files for batch 01KP6MNQ3X71RP6MNH6FHWGHVE.

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT "DATAFLOWNAME", "STATE", "TARGETID", "CONNECTIONSPECID", "NAME" FROM "dim_target" WHERE LOWER(CAST("STATE" AS VARCHAR)) LIKE LOWER('%failed%') LIMIT 50
```

Gold SQL:
```sql

```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/foundation/export/batches/01KP6MNQ3X71RP6MNH6FHWGHVE/failed"
]
```

Generated answer: Based on the evidence provided, there are no failed dataflow runs to report. The SQL query returned zero rows, and API evidence was not requested.

Gold answer: There are no failed files for batch 01KP6MNQ3X71RP6MNH6FHWGHVE. The API request returned a 404 status indicating no failures were recorded for this batch.

### example_001 / SQL_ONLY_BASELINE / 0.5217

Query: Give me inactive journeys

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT J."CAMPAIGNID" AS campaign_id, J."NAME" AS campaign_name, J."STATE" AS campaign_state, J."UPDATEDTIME" AS updated_time FROM "dim_campaign" AS J WHERE LOWER(CAST(J."STATE" AS VARCHAR)) NOT IN ('deployed', 'redeployed') LIMIT 50
```

Gold SQL:
```sql
SELECT J.CAMPAIGNID AS campaign_id,
       J.NAME AS campaign_name,
       J.STATE AS campaign_state,
       J.UPDATEDTIME AS updated_time
FROM DIM_CAMPAIGN AS J
WHERE LOWER(J.STATE) NOT IN ('deployed', 'redeployed')
LIMIT 50
```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /ajo/journey?filter=status!=live"
]
```

Generated answer: There are 2 inactive campaigns: Birthday Message (last updated 2026-03-31) and Gold Tier Welcome Email (last updated 2026-03-31). API evidence was not requested.

Gold answer: There are no active journeys currently. However, there are 2 inactive campaigns: the Birthday Message campaign (last updated March 31) and the Gold Tier Welcome Email campaign (created March 31).

### example_003 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.5259

Query: List all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, totalProfiles, createdTime, updatedTime, and used in other audience count for each audience. Remove any row limit from the results.

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT A."SEGMENTID" AS segment_id, A."NAME" AS segment_name, A."TOTALMEMBERS" AS total_profiles, A."CREATEDTIME" AS created_time, A."UPDATEDTIME" AS updated_time FROM "dim_segment" AS A JOIN "hkg_br_segment_target" AS AD ON A."SEGMENTID" = AD."SEGMENTID" JOIN "dim_target" AS D ON AD."TARGETID" = D."TARGETID" WHERE D."DATAFLOWNAME" = 'SMS Opt-In' OR D."NAME" = 'SMS Opt-In' ORDER BY A."NAME"
```

Gold SQL:
```sql
SELECT 
    a.segmentid AS segment_id,
    a.name AS segment_name,
    a.totalmembers AS total_profiles,
    a.createdTime AS created_time,
    a.updatedTime AS updated_time
FROM dim_segment a
JOIN hkg_br_segment_target ad ON a.segmentid = ad.segmentid
JOIN dim_target d ON ad.targetId = d.targetId
WHERE d.dataflowName = 'SMS Opt-In'
ORDER BY a.name
```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/core/ups/audiences?property=destinationId==<destination_id>&limit=5",
  "GET /data/foundation/flowservice/flows?property=inheritedAttributes.properties.isDestinationFlow==true&limit=5"
]
```

Generated answer: Based on the evidence provided, there is no data available to answer this question. The SQL query returned zero rows, and API evidence was not requested.

Gold answer: Based on the evidence provided, there is no data available to answer this question. The SQL query returned zero rows, the API call to retrieve audiences failed with a 400 error, and the flow service data that was successfully retrieved does not contain information about audiences connected to the SMS Opt-In destination.

### example_003 / SQL_ONLY_BASELINE / 0.5260

Query: List all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, totalProfiles, createdTime, updatedTime, and used in other audience count for each audience. Remove any row limit from the results.

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT A."SEGMENTID" AS segment_id, A."NAME" AS segment_name, A."TOTALMEMBERS" AS total_profiles, A."CREATEDTIME" AS created_time, A."UPDATEDTIME" AS updated_time FROM "dim_segment" AS A JOIN "hkg_br_segment_target" AS AD ON A."SEGMENTID" = AD."SEGMENTID" JOIN "dim_target" AS D ON AD."TARGETID" = D."TARGETID" WHERE D."DATAFLOWNAME" = 'SMS Opt-In' OR D."NAME" = 'SMS Opt-In' ORDER BY A."NAME"
```

Gold SQL:
```sql
SELECT 
    a.segmentid AS segment_id,
    a.name AS segment_name,
    a.totalmembers AS total_profiles,
    a.createdTime AS created_time,
    a.updatedTime AS updated_time
FROM dim_segment a
JOIN hkg_br_segment_target ad ON a.segmentid = ad.segmentid
JOIN dim_target d ON ad.targetId = d.targetId
WHERE d.dataflowName = 'SMS Opt-In'
ORDER BY a.name
```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/core/ups/audiences?property=destinationId==<destination_id>&limit=5",
  "GET /data/foundation/flowservice/flows?property=inheritedAttributes.properties.isDestinationFlow==true&limit=5"
]
```

Generated answer: Based on the evidence provided, there is no data available to answer this question. The SQL query returned zero rows, and API evidence was not requested.

Gold answer: Based on the evidence provided, there is no data available to answer this question. The SQL query returned zero rows, the API call to retrieve audiences failed with a 400 error, and the flow service data that was successfully retrieved does not contain information about audiences connected to the SMS Opt-In destination.

### example_002 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.5354

Query: List all journeys

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT CAMPAIGN."NAME" AS CAMPAIGNNAME, CAMPAIGN."CAMPAIGNID" AS CAMPAIGNID FROM "dim_campaign" AS CAMPAIGN
```

Gold SQL:
```sql
SELECT CAMPAIGN.NAME AS CAMPAIGNNAME,
       CAMPAIGN.CAMPAIGNID
FROM DIM_CAMPAIGN AS CAMPAIGN
LIMIT 10
```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /ajo/journey?pageSize=10"
]
```

Generated answer: Based on the available evidence, there are 2 journeys found in the database: Birthday Message and Gold Tier Welcome Email. API evidence was not requested.

Gold answer: Based on the available evidence, there are two journeys found in the database: Birthday Message and Gold Tier Welcome Email. However, the Adobe Journey Optimizer API returned no results when queried, suggesting a potential discrepancy between the database records and what the API is currently returning.

### example_002 / SQL_ONLY_BASELINE / 0.5354

Query: List all journeys

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT CAMPAIGN."NAME" AS CAMPAIGNNAME, CAMPAIGN."CAMPAIGNID" AS CAMPAIGNID FROM "dim_campaign" AS CAMPAIGN
```

Gold SQL:
```sql
SELECT CAMPAIGN.NAME AS CAMPAIGNNAME,
       CAMPAIGN.CAMPAIGNID
FROM DIM_CAMPAIGN AS CAMPAIGN
LIMIT 10
```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /ajo/journey?pageSize=10"
]
```

Generated answer: Based on the available evidence, there are 2 journeys found in the database: Birthday Message and Gold Tier Welcome Email. API evidence was not requested.

Gold answer: Based on the available evidence, there are two journeys found in the database: Birthday Message and Gold Tier Welcome Email. However, the Adobe Journey Optimizer API returned no results when queried, suggesting a potential discrepancy between the database records and what the API is currently returning.

### example_010 / LLM_FREE_AGENT_BASELINE / 0.5585

Query: Count the number of XDM Experience Event schemas that are enabled for profile.

Failure category: `SQL_COLUMN_MISMATCH`

Recommended fix: Align the selected projection/aliases with the requested fields and known gold-style columns.

Generated SQL:
```sql
SELECT COUNT(*) AS count FROM "dim_segment"
```

Gold SQL:
```sql
SELECT COUNT(DISTINCT S.BLUEPRINTID) AS num_experience_event_profile_enabled_blueprints
FROM DIM_BLUEPRINT AS S
WHERE LOWER(S.CLASS) LIKE LOWER('%download%')
  AND S.ISPROFILEENABLED = TRUE
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/schemaregistry/tenant/schemas",
    "params": {
      "filter": "class==ExperienceEvent;isProfileEnabled==true",
      "limit": "25"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/schemaregistry/tenant/schemas?limit=25&filter=class==ExperienceEvent;isProfileEnabled==true"
]
```

Generated answer: Based on the SQL query result, there are 13 XDM Experience Event schemas enabled for profile in your environment.

Gold answer: Based on the SQL query result, there are **0 XDM Experience Event schemas enabled for profile** in your environment.

### example_014 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.5611

Query: Show me all entities created by download

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT DISTINCT C."COLLECTIONID" AS collection_id, C."NAME" AS collection_name, C."CREATEDTIME" AS created_time FROM "dim_collection" AS C WHERE C."CREATEDBY" ILIKE '%download%'
```

Gold SQL:
```sql
SELECT DISTINCT collectionid AS collection_id, name AS collection_name, createdtime AS created_time
FROM dim_collection
WHERE createdby ILIKE '%download%'
LIMIT 20
```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/foundation/audit/events?property=action==create&limit=20"
]
```

Generated answer: Based on the evidence provided, no entities were created by download. The SQL query returned zero rows, and API evidence was not requested.

Gold answer: Based on the evidence provided, no entities were created by download. The SQL query returned zero results, and the audit log shows only a Segment entity that was created by a user, not by a download process.

### example_014 / SQL_ONLY_BASELINE / 0.5612

Query: Show me all entities created by download

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT DISTINCT C."COLLECTIONID" AS collection_id, C."NAME" AS collection_name, C."CREATEDTIME" AS created_time FROM "dim_collection" AS C WHERE C."CREATEDBY" ILIKE '%download%'
```

Gold SQL:
```sql
SELECT DISTINCT collectionid AS collection_id, name AS collection_name, createdtime AS created_time
FROM dim_collection
WHERE createdby ILIKE '%download%'
LIMIT 20
```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/foundation/audit/events?property=action==create&limit=20"
]
```

Generated answer: Based on the evidence provided, no entities were created by download. The SQL query returned zero rows, and API evidence was not requested.

Gold answer: Based on the evidence provided, no entities were created by download. The SQL query returned zero results, and the audit log shows only a Segment entity that was created by a user, not by a download process.

### example_005 / SQL_ONLY_BASELINE / 0.5793

Query: Export a list of all destinations in the b2b-prod sandbox, sorted by most recently modified, including all columns associated with each destination, and include the 'modified' column for validation.

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT D."TARGETID" AS target_id, D."DATAFLOWNAME" AS dataflow_name, D."NAME" AS target_name, D."DESCRIPTION", D."STATE", D."CONNECTIONSPECID" AS connection_spec_id, D."CREATEDTIME" AS created_time, D."UPDATEDTIME" AS modified, D."INTERVAL", D."FREQUENCY" FROM "dim_target" AS D ORDER BY D."UPDATEDTIME" DESC LIMIT 50
```

Gold SQL:
```sql
SELECT D.targetId AS target_id,
       D.dataflowName AS dataflow_name,
       D.name AS target_name,
       D.description,
       D.state,
       D.connectionSpecId AS connection_spec_id,
       D.createdTime AS created_time,
       D.updatedTime AS modified,
       D.interval,
       D.frequency
FROM dim_target AS D
ORDER BY D.updatedTime DESC
LIMIT 50
```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/foundation/flowservice/flows?limit=50&sort=updatedTime:desc&property=inheritedAttributes.properties.isDestinationFlow==true"
]
```

Generated answer: Based on the evidence provided, 1 destination was found. The most recent is "Activate segments to S3 Feed" (amazon-s3 target) with a modification timestamp of 2026-04-14 16:15:03.000 UTC. Live API evidence is needed to validate the requested sandbox. API evidence was not requested.

Gold answer: Based on the evidence provided, only one destination was found: "Activate segments to S3 Feed" (amazon-s3 target) with a modification timestamp of 2026-04-14 at 16:15:03 UTC. However, this result is from the "external-benchmarking" sandbox rather than the "b2b-prod" sandbox you requested, and the API response is incomplete, so the full export cannot be validated from the evidence shown.

### example_007 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.5894

Query: List all datasets that use the schema 'hkg_adls_profile_count_history'.

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT DISTINCT C."COLLECTIONID" AS collection_id, C."NAME" AS collection_name FROM "hkg_br_blueprint_collection" AS BC JOIN "dim_collection" AS C ON BC."COLLECTIONID" = C."COLLECTIONID" JOIN "dim_blueprint" AS B ON BC."BLUEPRINTID" = B."BLUEPRINTID" WHERE B."NAME" = 'hkg_adls_profile_count_history'
```

Gold SQL:
```sql
SELECT DISTINCT D.collectionid AS collection_id,
       D.name AS collection_name
FROM hkg_br_blueprint_collection AS SD
JOIN dim_collection AS D ON SD.collectionid = D.collectionid
JOIN dim_blueprint AS S ON SD.blueprintid = S.blueprintid
WHERE S.name = 'hkg_adls_profile_count_history'
LIMIT 3
```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/dataSets?limit=3&filter=schemaName==\"WF HEMI Account Attribute Retail Fiserv Schema\"",
  "GET /data/foundation/schemaregistry/tenant/schemas/{schema_id}"
]
```

Generated answer: Based on the evidence provided, no datasets use the schema 'hkg_adls_profile_count_history'. The SQL query returned zero results, and API evidence was not requested.

Gold answer: Based on the evidence provided, no datasets use the schema 'hkg_adls_profile_count_history'. The SQL query returned zero results, and the dataset returned from the API does not match this schema.

### example_007 / SQL_ONLY_BASELINE / 0.5894

Query: List all datasets that use the schema 'hkg_adls_profile_count_history'.

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT DISTINCT C."COLLECTIONID" AS collection_id, C."NAME" AS collection_name FROM "hkg_br_blueprint_collection" AS BC JOIN "dim_collection" AS C ON BC."COLLECTIONID" = C."COLLECTIONID" JOIN "dim_blueprint" AS B ON BC."BLUEPRINTID" = B."BLUEPRINTID" WHERE B."NAME" = 'hkg_adls_profile_count_history'
```

Gold SQL:
```sql
SELECT DISTINCT D.collectionid AS collection_id,
       D.name AS collection_name
FROM hkg_br_blueprint_collection AS SD
JOIN dim_collection AS D ON SD.collectionid = D.collectionid
JOIN dim_blueprint AS S ON SD.blueprintid = S.blueprintid
WHERE S.name = 'hkg_adls_profile_count_history'
LIMIT 3
```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/dataSets?limit=3&filter=schemaName==\"WF HEMI Account Attribute Retail Fiserv Schema\"",
  "GET /data/foundation/schemaregistry/tenant/schemas/{schema_id}"
]
```

Generated answer: Based on the evidence provided, no datasets use the schema 'hkg_adls_profile_count_history'. The SQL query returned zero results, and API evidence was not requested.

Gold answer: Based on the evidence provided, no datasets use the schema 'hkg_adls_profile_count_history'. The SQL query returned zero results, and the dataset returned from the API does not match this schema.

### example_006 / SQL_ONLY_BASELINE / 0.6264

Query: How many datasets have been ingested using the same schema in the prod sandbox?

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT S."BLUEPRINTID" AS blueprint_id, S."NAME" AS blueprint_name, COUNT(DISTINCT DS."COLLECTIONID") AS collection_count FROM "dim_collection" AS D JOIN "hkg_br_blueprint_collection" AS DS ON D."COLLECTIONID" = DS."COLLECTIONID" JOIN "dim_blueprint" AS S ON DS."BLUEPRINTID" = S."BLUEPRINTID" GROUP BY S."BLUEPRINTID", S."NAME" HAVING COUNT(DISTINCT DS."COLLECTIONID") > 1
```

Gold SQL:
```sql
SELECT S.blueprintid AS blueprint_id,
       S.name AS blueprint_name,
       COUNT(DISTINCT DS.collectionid) AS collection_count
FROM dim_collection AS D
JOIN hkg_br_blueprint_collection AS DS ON D.collectionid = DS.collectionid
JOIN dim_blueprint AS S ON DS.blueprintid = S.blueprintid
GROUP BY S.blueprintid,
         S.name
HAVING COUNT(DISTINCT DS.collectionid) > 1
```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/dataSets?limit=25&property=schema.name",
  "GET /data/foundation/schemaregistry/tenant/schemas/{schema_id}"
]
```

Generated answer: Based on the evidence provided, 2 datasets have been ingested using the same schema. These datasets use "Journey Inbound External Segment Profile Schema". API evidence was not requested.

Gold answer: Based on the evidence provided, **2 datasets** have been ingested using the same schema in the prod sandbox. These datasets both use the "Journey Inbound External Segment Profile Schema."

### example_010 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.6364

Query: Count the number of XDM Experience Event schemas that are enabled for profile.

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT COUNT(DISTINCT B."BLUEPRINTID") AS num_experience_event_profile_enabled_blueprints FROM "dim_blueprint" AS B WHERE LOWER(B."CLASS") LIKE LOWER('%download%') AND B."ISPROFILEENABLED" = TRUE
```

Gold SQL:
```sql
SELECT COUNT(DISTINCT S.BLUEPRINTID) AS num_experience_event_profile_enabled_blueprints
FROM DIM_BLUEPRINT AS S
WHERE LOWER(S.CLASS) LIKE LOWER('%download%')
  AND S.ISPROFILEENABLED = TRUE
```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/foundation/schemaregistry/tenant/schemas?limit=25&filter=class==ExperienceEvent;isProfileEnabled==true"
]
```

Generated answer: Based on the SQL query result, there are 0 XDM Experience Event schemas enabled for profile in your environment.

Gold answer: Based on the SQL query result, there are **0 XDM Experience Event schemas enabled for profile** in your environment.

### example_010 / SQL_ONLY_BASELINE / 0.6365

Query: Count the number of XDM Experience Event schemas that are enabled for profile.

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT COUNT(DISTINCT B."BLUEPRINTID") AS num_experience_event_profile_enabled_blueprints FROM "dim_blueprint" AS B WHERE LOWER(B."CLASS") LIKE LOWER('%download%') AND B."ISPROFILEENABLED" = TRUE
```

Gold SQL:
```sql
SELECT COUNT(DISTINCT S.BLUEPRINTID) AS num_experience_event_profile_enabled_blueprints
FROM DIM_BLUEPRINT AS S
WHERE LOWER(S.CLASS) LIKE LOWER('%download%')
  AND S.ISPROFILEENABLED = TRUE
```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/foundation/schemaregistry/tenant/schemas?limit=25&filter=class==ExperienceEvent;isProfileEnabled==true"
]
```

Generated answer: Based on the SQL query result, there are 0 XDM Experience Event schemas enabled for profile in your environment.

Gold answer: Based on the SQL query result, there are **0 XDM Experience Event schemas enabled for profile** in your environment.

### example_021 / LLM_FREE_AGENT_BASELINE / 0.7009

Query: Show the default merge policy for schema class '_xdm.context.profile'.

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT "SEGMENTID", "UPDATEDTIME", "ISACCOUNTSEGMENT", "NAME", "EVALUATIONCOMPLETEDTIME", "LABELSSEGMENT", "LIFECYCLESTATUS", "CREATEDTIME", "TYPE", "MERGEPOLICYID" FROM "dim_segment" WHERE LOWER(CAST("NAME" AS VARCHAR)) LIKE LOWER('%_xdm.context.profile%') LIMIT 50
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/schemas",
    "params": {
      "filter": "name==_xdm.context.profile",
      "limit": "5"
    }
  },
  {
    "method": "GET",
    "path": "/data/core/ups/config/mergePolicies",
    "params": {
      "limit": "5"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/config/mergePolicies?limit=5"
]
```

Generated answer: The default merge policy requires live Adobe API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: The default merge policy for the schema class '_xdm.context.profile' is called **Default Timebased**. It uses timestamp-ordered attribute merging, where conflicting attributes are resolved by selecting the most recent value, and relies on the Personalized Data Graph for identity resolution.

### example_017 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.7281

Query: Which tags belong to the category 'Uncategorized'?

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/unifiedtags/tagCategory",
    "params": {
      "limit": "100"
    }
  }
]
```

Gold API:
```json
[
  "GET /unifiedtags/tagCategory?limit=100",
  "GET /unifiedtags/tags?limit=100&tagCategoryId=Uncategorized-87891E4066602D250A495F91@AdobeOrg"
]
```

Generated answer: Details for the tag named 'Uncategorized' require live API evidence, including the tag ID, name, category, and Adobe organization. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence, the Uncategorized category contains at least the tags "AI-Generated" and "cool." However, the API response is incomplete—the category metadata indicates there are 5 tags total, but only 2 are shown in the truncated evidence.

### example_032 / LLM_FREE_AGENT_BASELINE / 0.7465

Query: Show failed files for batch 01KP6MNQ3X71RP6MNH6FHWGHVE.

Failure category: `ANSWER_WRONG_FACT`

Recommended fix: Audit answer template field selection and avoid summarizing the wrong row/value.

Generated SQL:
```sql
SELECT "SEGMENTID", "CAMPAIGNID" FROM "br_campaign_segment" LIMIT 50
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/export/batches/01KP6MNQ3X71RP6MNH6FHWGHVE/failed",
    "params": {}
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/export/batches/01KP6MNQ3X71RP6MNH6FHWGHVE/failed"
]
```

Generated answer: Based on the available evidence, failed dataflow identifiers are: SEGMENTID=2869d771-1546-4458-a2cd-fb7235a69c94, CAMPAIGNID=9f4ebca4-2fdd-4873-95f5-8d66bab358c6; SEGMENTID=8d1eda81-5df9-4d7a-ab48-56d49c4b1c8d, CAMPAIGNID=9f4ebca4-2fdd-4873-95f5-8d66bab358c6; SEGMENTID=bd33fef0-c2d1-4e30-bb6a-a46e6b4579a8, CAMPAIGNID=9f4ebca4-2fdd-4873-95f5-8d66bab358c6. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: There are no failed files for batch 01KP6MNQ3X71RP6MNH6FHWGHVE. The API request returned a 404 status indicating no failures were recorded for this batch.

### example_021 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.7629

Query: Show the default merge policy for schema class '_xdm.context.profile'.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/schemas",
    "params": {
      "filter": "name==_xdm.context.profile",
      "limit": "5"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/config/mergePolicies?limit=5"
]
```

Generated answer: The default merge policy requires live Adobe API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: The default merge policy for the schema class '_xdm.context.profile' is called **Default Timebased**. It uses timestamp-ordered attribute merging, where conflicting attributes are resolved by selecting the most recent value, and relies on the Personalized Data Graph for identity resolution.

### example_029 / LLM_FREE_AGENT_BASELINE / 0.7805

Query: How many batches have status 'success'?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT COUNT(*) AS count FROM "br_campaign_segment" WHERE LOWER(CAST("LABELSSEGMENT" AS VARCHAR)) LIKE LOWER('%success%')
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/catalog/batches",
    "params": {
      "limit": "10",
      "status": "success"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/batches?limit=10&status=success"
]
```

Generated answer: The batch count requires live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response provided, there is **1 batch** with status 'success'.

### example_030 / LLM_FREE_AGENT_BASELINE / 0.7805

Query: Show the details of batch 01KP69BPA5ZKFB7HCDYPE4GN6F.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT "SEGMENTID", "CAMPAIGNID", "LABELSSEGMENT", "LABELSCAMPAIGN" FROM "br_campaign_segment" LIMIT 50
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/catalog/batches/01KP69BPA5ZKFB7HCDYPE4GN6F",
    "params": {}
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/batches/01KP69BPA5ZKFB7HCDYPE4GN6F"
]
```

Generated answer: Batch details require live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Batch 01KP69BPA5ZKFB7HCDYPE4GN6F is currently inactive. It's a replay batch created by the Adobe Unified Profile export service for dataset 69c8d6c9b9966265fc8e4ea4, and it appears to have predecessor batches as part of its replay history.

### example_029 / TEMPLATE_FIRST / 0.7806

Query: How many batches have status 'success'?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT COUNT(*) AS count FROM "br_campaign_segment" WHERE LOWER(CAST("LABELSSEGMENT" AS VARCHAR)) LIKE LOWER('%success%')
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/catalog/batches",
    "params": {
      "limit": "10",
      "status": "success"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/batches?limit=10&status=success"
]
```

Generated answer: The batch count requires live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response provided, there is **1 batch** with status 'success'.

### example_025 / LLM_FREE_AGENT_BASELINE / 0.7819

Query: List all segment evaluation jobs.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT "SEGMENTID", "UPDATEDTIME", "ISACCOUNTSEGMENT", "NAME", "EVALUATIONCOMPLETEDTIME", "LABELSSEGMENT", "LIFECYCLESTATUS", "CREATEDTIME", "TYPE", "MERGEPOLICYID" FROM "dim_segment"
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/segment/jobs",
    "params": {
      "limit": "3"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/jobs?limit=3"
]
```

Generated answer: Segment evaluation job IDs, statuses, sandbox, and segment counts require live Adobe API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response, there is one segment evaluation job with status SUCCEEDED. It ran in the external-benchmarking sandbox and evaluated three segments, completing successfully with ID 63c6f78a-3a81-4bff-bc14-8b818b6774b3.

### example_033 / TEMPLATE_FIRST / 0.7825

Query: What are the daily 'timeseries.ingestion.dataset.recordsuccess.count' values between '2026-03-15' and '2026-03-31'?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT DISTINCT C."COLLECTIONID" AS collection_id, C."NAME" AS collection_name FROM "hkg_br_blueprint_collection" AS BC JOIN "dim_collection" AS C ON BC."COLLECTIONID" = C."COLLECTIONID" JOIN "dim_blueprint" AS B ON BC."BLUEPRINTID" = B."BLUEPRINTID" WHERE B."NAME" = 'timeseries.ingestion.dataset.recordsuccess.count' LIMIT 50
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "POST",
    "path": "/data/infrastructure/observability/insights/metrics",
    "params": {
      "end": "2026-03-31T23:59:59.000Z",
      "granularity": "day",
      "metrics": [
        {
          "aggregator": "sum",
          "filters": [],
          "name": "timeseries.ingestion.dataset.recordsuccess.count"
        }
      ],
      "start": "2026-03-15T00:00:00.000Z"
    }
  }
]
```

Gold API:
```json
[
  "POST /data/infrastructure/observability/insights/metrics body={\"start\":\"2026-03-15T00:00:00.000Z\",\"end\":\"2026-03-31T23:59:59.000Z\",\"granularity\":\"day\",\"metrics\":[{\"name\":\"timeseries.ingestion.dataset.recordsuccess.count\",\"filters\":[],\"aggregator\":\"sum\"}]}"
]
```

Generated answer: Values for timeseries.ingestion.dataset.recordsuccess.count between 2026-03-15 and 2026-03-31 require live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Between March 15 and March 31, 2026, the record success count was 0 for all days except March 29th (152,120 records) and March 31st (2,701 records). The data shows virtually no ingestion activity for the first two weeks of the period, with a sudden increase near the end of the month.

### example_011 / SQL_FIRST_API_VERIFY / 0.7829

Query: How many schemas do I have?

Failure category: `DRY_RUN_ONLY`

Recommended fix: Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations.

Generated SQL:
```sql
SELECT COUNT(DISTINCT B."BLUEPRINTID") AS blueprint_count FROM "dim_blueprint" AS B
```

Gold SQL:
```sql
SELECT COUNT(DISTINCT S.blueprintid) AS blueprint_count
FROM dim_blueprint AS S
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/schemas",
    "params": {
      "limit": "25"
    }
  }
]
```

Gold API:
```json
[
  "GET /schemas?limit=25"
]
```

Generated answer: You have 74 schemas. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: You have **74 schemas**. This count comes from your blueprint query, and is confirmed by the API response from Adobe's Schema Registry, which shows your tenant schemas are available.

### example_011 / TEMPLATE_FIRST / 0.7829

Query: How many schemas do I have?

Failure category: `DRY_RUN_ONLY`

Recommended fix: Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations.

Generated SQL:
```sql
SELECT COUNT(DISTINCT B."BLUEPRINTID") AS blueprint_count FROM "dim_blueprint" AS B
```

Gold SQL:
```sql
SELECT COUNT(DISTINCT S.blueprintid) AS blueprint_count
FROM dim_blueprint AS S
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/schemas",
    "params": {
      "limit": "25"
    }
  }
]
```

Gold API:
```json
[
  "GET /schemas?limit=25"
]
```

Generated answer: You have 74 schemas. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: You have **74 schemas**. This count comes from your blueprint query, and is confirmed by the API response from Adobe's Schema Registry, which shows your tenant schemas are available.

### example_033 / LLM_FREE_AGENT_BASELINE / 0.7832

Query: What are the daily 'timeseries.ingestion.dataset.recordsuccess.count' values between '2026-03-15' and '2026-03-31'?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT COUNT(*) AS count FROM "dim_collection" WHERE LOWER(CAST("NAME" AS VARCHAR)) LIKE LOWER('%timeseries.ingestion.dataset.recordsuccess.count%')
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "POST",
    "path": "/data/infrastructure/observability/insights/metrics",
    "params": {
      "end": "2026-03-31T23:59:59.000Z",
      "granularity": "day",
      "metrics": [
        {
          "aggregator": "sum",
          "filters": [],
          "name": "timeseries.ingestion.dataset.recordsuccess.count"
        }
      ],
      "start": "2026-03-15T00:00:00.000Z"
    }
  }
]
```

Gold API:
```json
[
  "POST /data/infrastructure/observability/insights/metrics body={\"start\":\"2026-03-15T00:00:00.000Z\",\"end\":\"2026-03-31T23:59:59.000Z\",\"granularity\":\"day\",\"metrics\":[{\"name\":\"timeseries.ingestion.dataset.recordsuccess.count\",\"filters\":[],\"aggregator\":\"sum\"}]}"
]
```

Generated answer: Values for timeseries.ingestion.dataset.recordsuccess.count between 2026-03-15 and 2026-03-31 require live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Between March 15 and March 31, 2026, the record success count was 0 for all days except March 29th (152,120 records) and March 31st (2,701 records). The data shows virtually no ingestion activity for the first two weeks of the period, with a sudden increase near the end of the month.

### example_031 / LLM_FREE_AGENT_BASELINE / 0.7852

Query: Which files are available for download in batch 69de8a0e0cc6102b5d11f01e?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT "SEGMENTID", "CAMPAIGNID", "LABELSSEGMENT", "LABELSCAMPAIGN" FROM "br_campaign_segment" LIMIT 50
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/export/batches/69de8a0e0cc6102b5d11f01e/files",
    "params": {}
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/export/batches/69de8a0e0cc6102b5d11f01e/files"
]
```

Generated answer: Batch file details require live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: There is one file available for download in batch 69de8a0e0cc6102b5d11f01e (ID: 69de8a0e0cc6102b5d11f01e-DE1), but it is marked as invalid.

### example_024 / LLM_FREE_AGENT_BASELINE / 0.7859

Query: Which segment definitions were updated most recently?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT "SEGMENTID", "UPDATEDTIME", "ISACCOUNTSEGMENT", "NAME", "EVALUATIONCOMPLETEDTIME", "LABELSSEGMENT", "LIFECYCLESTATUS", "CREATEDTIME", "TYPE", "MERGEPOLICYID" FROM "dim_segment" LIMIT 50
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/segment/definitions",
    "params": {
      "limit": "3",
      "orderBy": "updateTime:desc"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/definitions?limit=3&orderBy=updateTime:desc"
]
```

Generated answer: The most recently updated segment definitions require live Adobe API evidence with names, IDs, and update times. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response sorted by creation time in descending order, the most recently created segment definition is **"Person: Birthday Today 001"** (ID: 2fdfefe1-04d0-46ce-9fbd-7611e311dd26) in the external-benchmarking sandbox. The response shows 13 total segment definitions across 5 pages, with this one appearing first in the descending creation time sort.

### example_028 / LLM_FREE_AGENT_BASELINE / 0.7873

Query: List the most recently created batches.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT "SEGMENTID", "CAMPAIGNID", "LABELSSEGMENT", "LABELSCAMPAIGN" FROM "br_campaign_segment" LIMIT 50
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/catalog/batches",
    "params": {
      "limit": "100",
      "orderBy": "desc:created"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/batches?limit=100&orderBy=desc:created"
]
```

Generated answer: Batch details require live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response, there is one batch currently visible with a processing status. The batch is actively being ingested with some datasets completing successfully while others are still in progress.

### example_019 / LLM_FREE_AGENT_BASELINE / 0.7874

Query: List all merge policies in this sandbox.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT "SEGMENTID", "CAMPAIGNID", "LABELSSEGMENT", "LABELSCAMPAIGN" FROM "br_campaign_segment"
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/config/mergePolicies",
    "params": {
      "limit": "10"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/config/mergePolicies?limit=10"
]
```

Generated answer: Merge policy information requires Adobe API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: The sandbox has at least two merge policies. The primary one is "Default Timebased," which uses timestamp-ordered attribute merging and is set as the default policy for this sandbox. A second merge policy also exists, though the full details are truncated in the response.

### example_020 / LLM_FREE_AGENT_BASELINE / 0.7878

Query: How many merge policies are configured in this sandbox?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT COUNT(*) AS count FROM "br_campaign_segment"
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/config/mergePolicies",
    "params": {
      "limit": "10"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/config/mergePolicies?limit=10"
]
```

Generated answer: The merge policy count cannot be determined from the available evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response provided, there are at least **2 merge policies** configured in the external-benchmarking sandbox. The response shows a "Default Timebased" policy and a second policy, though the full response appears to be truncated.

### example_020 / TEMPLATE_FIRST / 0.7879

Query: How many merge policies are configured in this sandbox?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT COUNT(*) AS count FROM "br_campaign_segment"
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/config/mergePolicies",
    "params": {
      "limit": "10"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/config/mergePolicies?limit=10"
]
```

Generated answer: The merge policy count cannot be determined from the available evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response provided, there are at least **2 merge policies** configured in the external-benchmarking sandbox. The response shows a "Default Timebased" policy and a second policy, though the full response appears to be truncated.

### example_017 / LLM_FREE_AGENT_BASELINE / 0.7894

Query: Which tags belong to the category 'Uncategorized'?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT "SEGMENTID", "CAMPAIGNID", "LABELSSEGMENT", "LABELSCAMPAIGN" FROM "br_campaign_segment" WHERE LOWER(CAST("LABELSSEGMENT" AS VARCHAR)) LIKE LOWER('%Uncategorized%') LIMIT 50
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/unifiedtags/tagCategory",
    "params": {
      "limit": "100"
    }
  },
  {
    "method": "GET",
    "path": "/unifiedtags/tags",
    "params": {
      "limit": "100",
      "tagCategoryId": "Uncategorized-87891E4066602D250A495F91@AdobeOrg"
    }
  }
]
```

Gold API:
```json
[
  "GET /unifiedtags/tagCategory?limit=100",
  "GET /unifiedtags/tags?limit=100&tagCategoryId=Uncategorized-87891E4066602D250A495F91@AdobeOrg"
]
```

Generated answer: Details for the tag named 'Uncategorized' require live API evidence, including the tag ID, name, category, and Adobe organization. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence, the Uncategorized category contains at least the tags "AI-Generated" and "cool." However, the API response is incomplete—the category metadata indicates there are 5 tags total, but only 2 are shown in the truncated evidence.

### example_001 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.7913

Query: Give me inactive journeys

Failure category: `DRY_RUN_ONLY`

Recommended fix: Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations.

Generated SQL:
```sql
SELECT J."CAMPAIGNID" AS campaign_id, J."NAME" AS campaign_name, J."STATE" AS campaign_state, J."UPDATEDTIME" AS updated_time FROM "dim_campaign" AS J WHERE LOWER(CAST(J."STATE" AS VARCHAR)) NOT IN ('deployed', 'redeployed') LIMIT 50
```

Gold SQL:
```sql
SELECT J.CAMPAIGNID AS campaign_id,
       J.NAME AS campaign_name,
       J.STATE AS campaign_state,
       J.UPDATEDTIME AS updated_time
FROM DIM_CAMPAIGN AS J
WHERE LOWER(J.STATE) NOT IN ('deployed', 'redeployed')
LIMIT 50
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/ajo/journey",
    "params": {
      "filter": "status!=live"
    }
  }
]
```

Gold API:
```json
[
  "GET /ajo/journey?filter=status!=live"
]
```

Generated answer: There are 2 inactive campaigns: Birthday Message (last updated 2026-03-31) and Gold Tier Welcome Email (last updated 2026-03-31). Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: There are no active journeys currently. However, there are 2 inactive campaigns: the Birthday Message campaign (last updated March 31) and the Gold Tier Welcome Email campaign (created March 31).

### example_001 / TEMPLATE_FIRST / 0.7914

Query: Give me inactive journeys

Failure category: `DRY_RUN_ONLY`

Recommended fix: Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations.

Generated SQL:
```sql
SELECT J."CAMPAIGNID" AS campaign_id, J."NAME" AS campaign_name, J."STATE" AS campaign_state, J."UPDATEDTIME" AS updated_time FROM "dim_campaign" AS J WHERE LOWER(CAST(J."STATE" AS VARCHAR)) NOT IN ('deployed', 'redeployed') LIMIT 50
```

Gold SQL:
```sql
SELECT J.CAMPAIGNID AS campaign_id,
       J.NAME AS campaign_name,
       J.STATE AS campaign_state,
       J.UPDATEDTIME AS updated_time
FROM DIM_CAMPAIGN AS J
WHERE LOWER(J.STATE) NOT IN ('deployed', 'redeployed')
LIMIT 50
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/ajo/journey",
    "params": {
      "filter": "status!=live"
    }
  }
]
```

Gold API:
```json
[
  "GET /ajo/journey?filter=status!=live"
]
```

Generated answer: There are 2 inactive campaigns: Birthday Message (last updated 2026-03-31) and Gold Tier Welcome Email (last updated 2026-03-31). Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: There are no active journeys currently. However, there are 2 inactive campaigns: the Birthday Message campaign (last updated March 31) and the Gold Tier Welcome Email campaign (created March 31).

### example_016 / LLM_FREE_AGENT_BASELINE / 0.7915

Query: List all tags in this sandbox.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT "SEGMENTID", "CAMPAIGNID", "LABELSSEGMENT", "LABELSCAMPAIGN" FROM "br_campaign_segment"
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/unifiedtags/tags",
    "params": {
      "limit": "25"
    }
  }
]
```

Gold API:
```json
[
  "GET /unifiedtags/tags?limit=25"
]
```

Generated answer: The requested tag list requires live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response, the sandbox contains at least two tags: "AI-Generated" and "cool". The response appears to be truncated, so there may be additional tags not shown in the evidence.

### example_001 / SQL_FIRST_API_VERIFY / 0.7915

Query: Give me inactive journeys

Failure category: `DRY_RUN_ONLY`

Recommended fix: Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations.

Generated SQL:
```sql
SELECT J."CAMPAIGNID" AS campaign_id, J."NAME" AS campaign_name, J."STATE" AS campaign_state, J."UPDATEDTIME" AS updated_time FROM "dim_campaign" AS J WHERE LOWER(CAST(J."STATE" AS VARCHAR)) NOT IN ('deployed', 'redeployed') LIMIT 50
```

Gold SQL:
```sql
SELECT J.CAMPAIGNID AS campaign_id,
       J.NAME AS campaign_name,
       J.STATE AS campaign_state,
       J.UPDATEDTIME AS updated_time
FROM DIM_CAMPAIGN AS J
WHERE LOWER(J.STATE) NOT IN ('deployed', 'redeployed')
LIMIT 50
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/ajo/journey",
    "params": {
      "filter": "status!=live"
    }
  }
]
```

Gold API:
```json
[
  "GET /ajo/journey?filter=status!=live"
]
```

Generated answer: There are 2 inactive campaigns: Birthday Message (last updated 2026-03-31) and Gold Tier Welcome Email (last updated 2026-03-31). Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: There are no active journeys currently. However, there are 2 inactive campaigns: the Birthday Message campaign (last updated March 31) and the Gold Tier Welcome Email campaign (created March 31).

### example_018 / LLM_FREE_AGENT_BASELINE / 0.7934

Query: Show me the details of the tag named 'cool'.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT "SEGMENTID", "CAMPAIGNID", "LABELSSEGMENT", "LABELSCAMPAIGN" FROM "br_campaign_segment" WHERE LOWER(CAST("LABELSSEGMENT" AS VARCHAR)) LIKE LOWER('%cool%') LIMIT 50
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/unifiedtags/tags/51175a7f-aa60-4533-bef1-717b3cef7818",
    "params": {}
  }
]
```

Gold API:
```json
[
  "GET /unifiedtags/tags/51175a7f-aa60-4533-bef1-717b3cef7818"
]
```

Generated answer: Details for the tag named 'cool' require live API evidence, including the tag ID, name, category, and Adobe organization. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: I notice a discrepancy: the question asks for a tag named 'cool', but the API response shows details for a tag named 'sublist' (ID: 51175a7f-aa60-4533-bef1-717b3cef7818). The tag 'sublist' belongs to the Uncategorized category in the Adobe organization 87891E4066602D250A495F91@AdobeOrg. If you intended to look up a different tag named 'cool', that information isn't in the evidence provided.

### example_029 / SQL_FIRST_API_VERIFY / 0.7941

Query: How many batches have status 'success'?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/catalog/batches",
    "params": {
      "limit": "10",
      "status": "success"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/batches?limit=10&status=success"
]
```

Generated answer: The batch count requires live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response provided, there is **1 batch** with status 'success'.

### example_029 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.7944

Query: How many batches have status 'success'?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/catalog/batches",
    "params": {
      "limit": "10",
      "status": "success"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/batches?limit=10&status=success"
]
```

Generated answer: The batch count requires live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response provided, there is **1 batch** with status 'success'.

### example_013 / TEMPLATE_FIRST / 0.7946

Query: Show recent changes in datasets.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT DISTINCT D."COLLECTIONID" AS collection_id, D."NAME" AS collection_name, D."UPDATEDTIME" AS updated_time FROM "dim_collection" AS D WHERE D."UPDATEDTIME" >= DATEADD(DAY, -90, CURRENT_DATE) ORDER BY D."UPDATEDTIME" DESC LIMIT 50
```

Gold SQL:
```sql
SELECT DISTINCT D.COLLECTIONID AS collection_id,
       D.NAME AS collection_name,
       D.UPDATEDTIME AS updated_time
FROM DIM_COLLECTION AS D
WHERE D.UPDATEDTIME >= DATEADD(DAY, -90, CURRENT_DATE)
ORDER BY D.UPDATEDTIME DESC
LIMIT 50
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/audit/events",
    "params": {
      "limit": "50",
      "orderBy": "-timestamp",
      "property": "assetType==dataset"
    }
  }
]
```

Gold API:
```json
[
  "GET /audit/events?property=assetType==dataset&orderBy=-timestamp&limit=50"
]
```

Generated answer: Based on the evidence provided, matching datasets are: hkg_adls_segment_profile_history, hkg_adls_profile_count_history, Profile-Snapshot-Export-486e2a5e-dc46-4ab6-ad5f-9cdd16db869d, Profile Export For Destination - Merge Policy - 22a941a9-e598-45f8-846b-c9a8889f5035, BR_Segment_Destination, DIM_Destination, BR_Namespace_Destination, Segmentdefinition-Snapshot-Export-3405afd1-7c78-4aff-84e6-d2136ffcea93, weRetail: CRM, and weRetail: Customer Actions. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: The most recent dataset changes occurred on April 14, 2026, with the latest updates to **hkg_adls_segment_profile_history** (9:08 PM UTC) and **hkg_adls_profile_count_history** (9:08 PM UTC). Several profile and segment snapshots were also updated throughout that day, with the audit log showing a dataset update permission granted on March 29 for the "weRetail: Customer Actions" dataset.

### example_015 / LLM_FREE_AGENT_BASELINE / 0.7947

Query: How many tags exist in this sandbox?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT COUNT(*) AS count FROM "br_campaign_segment"
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/unifiedtags/tags",
    "params": {
      "limit": "20"
    }
  }
]
```

Gold API:
```json
[
  "GET /unifiedtags/tags?limit=20"
]
```

Generated answer: The tag count cannot be determined from the available evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence shown, there are at least 2 tags visible in the API response: "AI-Generated" and "cool." However, the response appears to be truncated, so the complete tag count from the sandbox cannot be determined from this partial data.

### example_027 / LLM_FREE_AGENT_BASELINE / 0.7947

Query: Show all segment jobs with status 'QUEUED'.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT "SEGMENTID", "NAME", "LIFECYCLESTATUS", "MERGEPOLICYID" FROM "dim_segment" WHERE LOWER(CAST("NAME" AS VARCHAR)) LIKE LOWER('%QUEUED%') LIMIT 50
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/segment/jobs",
    "params": {
      "limit": "10"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/jobs?limit=10"
]
```

Generated answer: Segment evaluation job IDs, statuses, sandbox, and segment counts require live Adobe API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response provided, there are no segment jobs with status 'QUEUED'. The single job returned has a status of 'SUCCEEDED'.

### example_007 / TEMPLATE_FIRST / 0.7948

Query: List all datasets that use the schema 'hkg_adls_profile_count_history'.

Failure category: `API_PATH_MISMATCH`

Recommended fix: Add endpoint selection rules or endpoint catalog coverage for this query family.

Generated SQL:
```sql
SELECT DISTINCT C."COLLECTIONID" AS collection_id, C."NAME" AS collection_name FROM "hkg_br_blueprint_collection" AS BC JOIN "dim_collection" AS C ON BC."COLLECTIONID" = C."COLLECTIONID" JOIN "dim_blueprint" AS B ON BC."BLUEPRINTID" = B."BLUEPRINTID" WHERE B."NAME" = 'hkg_adls_profile_count_history'
```

Gold SQL:
```sql
SELECT DISTINCT D.collectionid AS collection_id,
       D.name AS collection_name
FROM hkg_br_blueprint_collection AS SD
JOIN dim_collection AS D ON SD.collectionid = D.collectionid
JOIN dim_blueprint AS S ON SD.blueprintid = S.blueprintid
WHERE S.name = 'hkg_adls_profile_count_history'
LIMIT 3
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/catalog/dataSets",
    "params": {
      "filter": "schemaName==\"hkg_adls_profile_count_history\"",
      "limit": "3"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/dataSets?limit=3&filter=schemaName==\"WF HEMI Account Attribute Retail Fiserv Schema\"",
  "GET /data/foundation/schemaregistry/tenant/schemas/{schema_id}"
]
```

Generated answer: Based on the evidence provided, no datasets use the schema 'hkg_adls_profile_count_history'. The SQL query returned zero results, and live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence provided, no datasets use the schema 'hkg_adls_profile_count_history'. The SQL query returned zero results, and the dataset returned from the API does not match this schema.

### example_027 / TEMPLATE_FIRST / 0.7948

Query: Show all segment jobs with status 'QUEUED'.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT "SEGMENTID", "NAME", "LIFECYCLESTATUS", "MERGEPOLICYID" FROM "dim_segment" WHERE LOWER(CAST("NAME" AS VARCHAR)) LIKE LOWER('%QUEUED%') LIMIT 50
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/segment/jobs",
    "params": {
      "limit": "10"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/jobs?limit=10"
]
```

Generated answer: Segment evaluation job IDs, statuses, sandbox, and segment counts require live Adobe API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response provided, there are no segment jobs with status 'QUEUED'. The single job returned has a status of 'SUCCEEDED'.

### example_007 / SQL_FIRST_API_VERIFY / 0.7949

Query: List all datasets that use the schema 'hkg_adls_profile_count_history'.

Failure category: `API_PATH_MISMATCH`

Recommended fix: Add endpoint selection rules or endpoint catalog coverage for this query family.

Generated SQL:
```sql
SELECT DISTINCT C."COLLECTIONID" AS collection_id, C."NAME" AS collection_name FROM "hkg_br_blueprint_collection" AS BC JOIN "dim_collection" AS C ON BC."COLLECTIONID" = C."COLLECTIONID" JOIN "dim_blueprint" AS B ON BC."BLUEPRINTID" = B."BLUEPRINTID" WHERE B."NAME" = 'hkg_adls_profile_count_history'
```

Gold SQL:
```sql
SELECT DISTINCT D.collectionid AS collection_id,
       D.name AS collection_name
FROM hkg_br_blueprint_collection AS SD
JOIN dim_collection AS D ON SD.collectionid = D.collectionid
JOIN dim_blueprint AS S ON SD.blueprintid = S.blueprintid
WHERE S.name = 'hkg_adls_profile_count_history'
LIMIT 3
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/catalog/dataSets",
    "params": {
      "filter": "schemaName==\"hkg_adls_profile_count_history\"",
      "limit": "3"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/dataSets?limit=3&filter=schemaName==\"WF HEMI Account Attribute Retail Fiserv Schema\"",
  "GET /data/foundation/schemaregistry/tenant/schemas/{schema_id}"
]
```

Generated answer: Based on the evidence provided, no datasets use the schema 'hkg_adls_profile_count_history'. The SQL query returned zero results, and live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence provided, no datasets use the schema 'hkg_adls_profile_count_history'. The SQL query returned zero results, and the dataset returned from the API does not match this schema.

### example_015 / TEMPLATE_FIRST / 0.7949

Query: How many tags exist in this sandbox?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT COUNT(*) AS count FROM "br_campaign_segment"
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/unifiedtags/tags",
    "params": {
      "limit": "20"
    }
  }
]
```

Gold API:
```json
[
  "GET /unifiedtags/tags?limit=20"
]
```

Generated answer: The tag count cannot be determined from the available evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence shown, there are at least 2 tags visible in the API response: "AI-Generated" and "cool." However, the response appears to be truncated, so the complete tag count from the sandbox cannot be determined from this partial data.

### example_013 / SQL_FIRST_API_VERIFY / 0.7956

Query: Show recent changes in datasets.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT DISTINCT D."COLLECTIONID" AS collection_id, D."NAME" AS collection_name, D."UPDATEDTIME" AS updated_time FROM "dim_collection" AS D WHERE D."UPDATEDTIME" >= DATEADD(DAY, -90, CURRENT_DATE) ORDER BY D."UPDATEDTIME" DESC LIMIT 50
```

Gold SQL:
```sql
SELECT DISTINCT D.COLLECTIONID AS collection_id,
       D.NAME AS collection_name,
       D.UPDATEDTIME AS updated_time
FROM DIM_COLLECTION AS D
WHERE D.UPDATEDTIME >= DATEADD(DAY, -90, CURRENT_DATE)
ORDER BY D.UPDATEDTIME DESC
LIMIT 50
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/audit/events",
    "params": {
      "limit": "50",
      "orderBy": "-timestamp",
      "property": "assetType==dataset"
    }
  }
]
```

Gold API:
```json
[
  "GET /audit/events?property=assetType==dataset&orderBy=-timestamp&limit=50"
]
```

Generated answer: Based on the evidence provided, matching datasets are: hkg_adls_segment_profile_history, hkg_adls_profile_count_history, Profile-Snapshot-Export-486e2a5e-dc46-4ab6-ad5f-9cdd16db869d, Profile Export For Destination - Merge Policy - 22a941a9-e598-45f8-846b-c9a8889f5035, BR_Segment_Destination, DIM_Destination, BR_Namespace_Destination, Segmentdefinition-Snapshot-Export-3405afd1-7c78-4aff-84e6-d2136ffcea93, weRetail: CRM, and weRetail: Customer Actions. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: The most recent dataset changes occurred on April 14, 2026, with the latest updates to **hkg_adls_segment_profile_history** (9:08 PM UTC) and **hkg_adls_profile_count_history** (9:08 PM UTC). Several profile and segment snapshots were also updated throughout that day, with the audit log showing a dataset update permission granted on March 29 for the "weRetail: Customer Actions" dataset.

### example_030 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.7965

Query: Show the details of batch 01KP69BPA5ZKFB7HCDYPE4GN6F.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/catalog/batches/01KP69BPA5ZKFB7HCDYPE4GN6F",
    "params": {}
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/batches/01KP69BPA5ZKFB7HCDYPE4GN6F"
]
```

Generated answer: Batch details require live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Batch 01KP69BPA5ZKFB7HCDYPE4GN6F is currently inactive. It's a replay batch created by the Adobe Unified Profile export service for dataset 69c8d6c9b9966265fc8e4ea4, and it appears to have predecessor batches as part of its replay history.

### example_030 / TEMPLATE_FIRST / 0.7966

Query: Show the details of batch 01KP69BPA5ZKFB7HCDYPE4GN6F.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/catalog/batches/01KP69BPA5ZKFB7HCDYPE4GN6F",
    "params": {}
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/batches/01KP69BPA5ZKFB7HCDYPE4GN6F"
]
```

Generated answer: Batch details require live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Batch 01KP69BPA5ZKFB7HCDYPE4GN6F is currently inactive. It's a replay batch created by the Adobe Unified Profile export service for dataset 69c8d6c9b9966265fc8e4ea4, and it appears to have predecessor batches as part of its replay history.

### example_034 / LLM_FREE_AGENT_BASELINE / 0.7967

Query: Show ingestion record counts and batch success counts for the last 90 days.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT COUNT(*) AS count FROM "br_campaign_segment"
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "POST",
    "path": "/data/infrastructure/observability/insights/metrics",
    "params": {
      "end": "2026-04-01T23:59:59.000Z",
      "granularity": "day",
      "metrics": [
        {
          "aggregator": "sum",
          "filters": [],
          "name": "timeseries.ingestion.dataset.recordsuccess.count"
        },
        {
          "aggregator": "sum",
          "filters": [],
          "name": "timeseries.ingestion.dataset.batchsuccess.count"
        }
      ],
      "start": "2026-03-01T00:00:00.000Z"
    }
  }
]
```

Gold API:
```json
[
  "POST /data/infrastructure/observability/insights/metrics body={\"start\":\"2026-03-01T00:00:00.000Z\",\"end\":\"2026-04-01T23:59:59.000Z\",\"granularity\":\"day\",\"metrics\":[{\"name\":\"timeseries.ingestion.dataset.recordsuccess.count\",\"filters\":[],\"aggregator\":\"sum\"},{\"name\":\"timeseries.ingestion.dataset.batchsuccess.count\",\"filters\":[],\"aggregator\":\"sum\"}]}"
]
```

Generated answer: Values for timeseries.ingestion.dataset.recordsuccess.count and timeseries.ingestion.dataset.batchsuccess.count for the requested time window require live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the available data for the last 90 days, ingestion record success counts are minimal, with zero successful records recorded for most dates in March 2026. Only March 31st shows activity with 2,701 successfully ingested records. No batch success count data is included in the metrics response provided.

### example_030 / SQL_FIRST_API_VERIFY / 0.7967

Query: Show the details of batch 01KP69BPA5ZKFB7HCDYPE4GN6F.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/catalog/batches/01KP69BPA5ZKFB7HCDYPE4GN6F",
    "params": {}
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/batches/01KP69BPA5ZKFB7HCDYPE4GN6F"
]
```

Generated answer: Batch details require live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Batch 01KP69BPA5ZKFB7HCDYPE4GN6F is currently inactive. It's a replay batch created by the Adobe Unified Profile export service for dataset 69c8d6c9b9966265fc8e4ea4, and it appears to have predecessor batches as part of its replay history.

### example_034 / TEMPLATE_FIRST / 0.7968

Query: Show ingestion record counts and batch success counts for the last 90 days.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT COUNT(*) AS count FROM "br_campaign_segment"
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "POST",
    "path": "/data/infrastructure/observability/insights/metrics",
    "params": {
      "end": "2026-04-01T23:59:59.000Z",
      "granularity": "day",
      "metrics": [
        {
          "aggregator": "sum",
          "filters": [],
          "name": "timeseries.ingestion.dataset.recordsuccess.count"
        },
        {
          "aggregator": "sum",
          "filters": [],
          "name": "timeseries.ingestion.dataset.batchsuccess.count"
        }
      ],
      "start": "2026-03-01T00:00:00.000Z"
    }
  }
]
```

Gold API:
```json
[
  "POST /data/infrastructure/observability/insights/metrics body={\"start\":\"2026-03-01T00:00:00.000Z\",\"end\":\"2026-04-01T23:59:59.000Z\",\"granularity\":\"day\",\"metrics\":[{\"name\":\"timeseries.ingestion.dataset.recordsuccess.count\",\"filters\":[],\"aggregator\":\"sum\"},{\"name\":\"timeseries.ingestion.dataset.batchsuccess.count\",\"filters\":[],\"aggregator\":\"sum\"}]}"
]
```

Generated answer: Values for timeseries.ingestion.dataset.recordsuccess.count and timeseries.ingestion.dataset.batchsuccess.count for the requested time window require live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the available data for the last 90 days, ingestion record success counts are minimal, with zero successful records recorded for most dates in March 2026. Only March 31st shows activity with 2,701 successfully ingested records. No batch success count data is included in the metrics response provided.

### example_033 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.7972

Query: What are the daily 'timeseries.ingestion.dataset.recordsuccess.count' values between '2026-03-15' and '2026-03-31'?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "POST",
    "path": "/data/infrastructure/observability/insights/metrics",
    "params": {
      "end": "2026-03-31T23:59:59.000Z",
      "granularity": "day",
      "metrics": [
        {
          "aggregator": "sum",
          "filters": [],
          "name": "timeseries.ingestion.dataset.recordsuccess.count"
        }
      ],
      "start": "2026-03-15T00:00:00.000Z"
    }
  }
]
```

Gold API:
```json
[
  "POST /data/infrastructure/observability/insights/metrics body={\"start\":\"2026-03-15T00:00:00.000Z\",\"end\":\"2026-03-31T23:59:59.000Z\",\"granularity\":\"day\",\"metrics\":[{\"name\":\"timeseries.ingestion.dataset.recordsuccess.count\",\"filters\":[],\"aggregator\":\"sum\"}]}"
]
```

Generated answer: Values for timeseries.ingestion.dataset.recordsuccess.count between 2026-03-15 and 2026-03-31 require live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Between March 15 and March 31, 2026, the record success count was 0 for all days except March 29th (152,120 records) and March 31st (2,701 records). The data shows virtually no ingestion activity for the first two weeks of the period, with a sudden increase near the end of the month.

### example_023 / LLM_FREE_AGENT_BASELINE / 0.7972

Query: List all segment definitions.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT "SEGMENTID", "UPDATEDTIME", "ISACCOUNTSEGMENT", "NAME", "EVALUATIONCOMPLETEDTIME", "LABELSSEGMENT", "LIFECYCLESTATUS", "CREATEDTIME", "TYPE", "MERGEPOLICYID" FROM "dim_segment"
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/segment/definitions",
    "params": {
      "limit": "10"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/definitions?limit=10"
]
```

Generated answer: The requested segment definition list requires live Adobe API evidence with definition names, IDs, and pagination counts. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: There are 13 segment definitions total across 2 pages. The visible segment from the first page is "Person: Birthday Today 001," which targets all profiles whose birthday falls on a specific month/day. The response was paginated with 10 results per page, so additional segment definitions exist on the second page.

### example_033 / SQL_FIRST_API_VERIFY / 0.7973

Query: What are the daily 'timeseries.ingestion.dataset.recordsuccess.count' values between '2026-03-15' and '2026-03-31'?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "POST",
    "path": "/data/infrastructure/observability/insights/metrics",
    "params": {
      "end": "2026-03-31T23:59:59.000Z",
      "granularity": "day",
      "metrics": [
        {
          "aggregator": "sum",
          "filters": [],
          "name": "timeseries.ingestion.dataset.recordsuccess.count"
        }
      ],
      "start": "2026-03-15T00:00:00.000Z"
    }
  }
]
```

Gold API:
```json
[
  "POST /data/infrastructure/observability/insights/metrics body={\"start\":\"2026-03-15T00:00:00.000Z\",\"end\":\"2026-03-31T23:59:59.000Z\",\"granularity\":\"day\",\"metrics\":[{\"name\":\"timeseries.ingestion.dataset.recordsuccess.count\",\"filters\":[],\"aggregator\":\"sum\"}]}"
]
```

Generated answer: Values for timeseries.ingestion.dataset.recordsuccess.count between 2026-03-15 and 2026-03-31 require live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Between March 15 and March 31, 2026, the record success count was 0 for all days except March 29th (152,120 records) and March 31st (2,701 records). The data shows virtually no ingestion activity for the first two weeks of the period, with a sudden increase near the end of the month.

### example_026 / LLM_FREE_AGENT_BASELINE / 0.7976

Query: How many segment jobs are currently processing?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT COUNT(*) AS count FROM "dim_segment"
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/segment/jobs",
    "params": {
      "limit": "20"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/jobs?limit=20"
]
```

Generated answer: The segment evaluation job count requires live Adobe API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response, **zero segment jobs are currently processing**. The only visible job in the response has a status of "SUCCEEDED," indicating it has already completed.

### example_026 / TEMPLATE_FIRST / 0.7977

Query: How many segment jobs are currently processing?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT COUNT(*) AS count FROM "dim_segment"
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/segment/jobs",
    "params": {
      "limit": "20"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/jobs?limit=20"
]
```

Generated answer: The segment evaluation job count requires live Adobe API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response, **zero segment jobs are currently processing**. The only visible job in the response has a status of "SUCCEEDED," indicating it has already completed.

### example_021 / TEMPLATE_FIRST / 0.7992

Query: Show the default merge policy for schema class '_xdm.context.profile'.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT DISTINCT C."COLLECTIONID" AS collection_id, C."NAME" AS collection_name FROM "hkg_br_blueprint_collection" AS BC JOIN "dim_collection" AS C ON BC."COLLECTIONID" = C."COLLECTIONID" JOIN "dim_blueprint" AS B ON BC."BLUEPRINTID" = B."BLUEPRINTID" WHERE B."NAME" = '_xdm.context.profile' LIMIT 50
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/config/mergePolicies",
    "params": {
      "limit": "5"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/config/mergePolicies?limit=5"
]
```

Generated answer: The default merge policy requires live Adobe API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: The default merge policy for the schema class '_xdm.context.profile' is called **Default Timebased**. It uses timestamp-ordered attribute merging, where conflicting attributes are resolved by selecting the most recent value, and relies on the Personalized Data Graph for identity resolution.

### example_025 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.7996

Query: List all segment evaluation jobs.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/segment/jobs",
    "params": {
      "limit": "3"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/jobs?limit=3"
]
```

Generated answer: Segment evaluation job IDs, statuses, sandbox, and segment counts require live Adobe API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response, there is one segment evaluation job with status SUCCEEDED. It ran in the external-benchmarking sandbox and evaluated three segments, completing successfully with ID 63c6f78a-3a81-4bff-bc14-8b818b6774b3.

### example_025 / SQL_FIRST_API_VERIFY / 0.7996

Query: List all segment evaluation jobs.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/segment/jobs",
    "params": {
      "limit": "3"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/jobs?limit=3"
]
```

Generated answer: Segment evaluation job IDs, statuses, sandbox, and segment counts require live Adobe API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response, there is one segment evaluation job with status SUCCEEDED. It ran in the external-benchmarking sandbox and evaluated three segments, completing successfully with ID 63c6f78a-3a81-4bff-bc14-8b818b6774b3.

### example_025 / TEMPLATE_FIRST / 0.7997

Query: List all segment evaluation jobs.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/segment/jobs",
    "params": {
      "limit": "3"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/jobs?limit=3"
]
```

Generated answer: Segment evaluation job IDs, statuses, sandbox, and segment counts require live Adobe API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response, there is one segment evaluation job with status SUCCEEDED. It ran in the external-benchmarking sandbox and evaluated three segments, completing successfully with ID 63c6f78a-3a81-4bff-bc14-8b818b6774b3.

### example_020 / SQL_FIRST_API_VERIFY / 0.8011

Query: How many merge policies are configured in this sandbox?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/config/mergePolicies",
    "params": {
      "limit": "10"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/config/mergePolicies?limit=10"
]
```

Generated answer: The merge policy count cannot be determined from the available evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response provided, there are at least **2 merge policies** configured in the external-benchmarking sandbox. The response shows a "Default Timebased" policy and a second policy, though the full response appears to be truncated.

### example_031 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.8012

Query: Which files are available for download in batch 69de8a0e0cc6102b5d11f01e?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/export/batches/69de8a0e0cc6102b5d11f01e/files",
    "params": {}
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/export/batches/69de8a0e0cc6102b5d11f01e/files"
]
```

Generated answer: Batch file details require live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: There is one file available for download in batch 69de8a0e0cc6102b5d11f01e (ID: 69de8a0e0cc6102b5d11f01e-DE1), but it is marked as invalid.

### example_031 / TEMPLATE_FIRST / 0.8013

Query: Which files are available for download in batch 69de8a0e0cc6102b5d11f01e?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/export/batches/69de8a0e0cc6102b5d11f01e/files",
    "params": {}
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/export/batches/69de8a0e0cc6102b5d11f01e/files"
]
```

Generated answer: Batch file details require live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: There is one file available for download in batch 69de8a0e0cc6102b5d11f01e (ID: 69de8a0e0cc6102b5d11f01e-DE1), but it is marked as invalid.

### example_020 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.8014

Query: How many merge policies are configured in this sandbox?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/config/mergePolicies",
    "params": {
      "limit": "10"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/config/mergePolicies?limit=10"
]
```

Generated answer: The merge policy count cannot be determined from the available evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response provided, there are at least **2 merge policies** configured in the external-benchmarking sandbox. The response shows a "Default Timebased" policy and a second policy, though the full response appears to be truncated.

### example_022 / LLM_FREE_AGENT_BASELINE / 0.8014

Query: How many segment definitions exist in this sandbox?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT COUNT(*) AS count FROM "dim_segment"
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/segment/definitions",
    "params": {
      "limit": "100"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/definitions?limit=100"
]
```

Generated answer: Segment definition details require live Adobe API evidence with definition names, IDs, and counts. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response, there are **13 segment definitions** in the external-benchmarking sandbox, as indicated by the `totalCount` field in the pagination metadata.

### example_031 / SQL_FIRST_API_VERIFY / 0.8014

Query: Which files are available for download in batch 69de8a0e0cc6102b5d11f01e?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/export/batches/69de8a0e0cc6102b5d11f01e/files",
    "params": {}
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/export/batches/69de8a0e0cc6102b5d11f01e/files"
]
```

Generated answer: Batch file details require live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: There is one file available for download in batch 69de8a0e0cc6102b5d11f01e (ID: 69de8a0e0cc6102b5d11f01e-DE1), but it is marked as invalid.

### example_022 / TEMPLATE_FIRST / 0.8015

Query: How many segment definitions exist in this sandbox?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql
SELECT COUNT(*) AS count FROM "dim_segment"
```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/segment/definitions",
    "params": {
      "limit": "100"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/definitions?limit=100"
]
```

Generated answer: Segment definition details require live Adobe API evidence with definition names, IDs, and counts. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response, there are **13 segment definitions** in the external-benchmarking sandbox, as indicated by the `totalCount` field in the pagination metadata.

### example_012 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.8027

Query: List all audiences in the sandbox that have been mapped to new destinations in the last 3 months.

Failure category: `ANSWER_WRONG_FACT`

Recommended fix: Audit answer template field selection and avoid summarizing the wrong row/value.

Generated SQL:
```sql
SELECT DISTINCT A."SEGMENTID" AS segment_id, A."NAME" AS segment_name, D."TARGETID" AS target_id, D."NAME" AS target_name FROM "dim_segment" AS A JOIN "hkg_br_segment_target" AS AD ON A."SEGMENTID" = AD."SEGMENTID" JOIN "dim_target" AS D ON AD."TARGETID" = D."TARGETID" WHERE D."CREATEDTIME" >= DATEADD(MONTH, -3, CURRENT_DATE) LIMIT 3
```

Gold SQL:
```sql
SELECT DISTINCT A.segmentid AS segment_id, A.name AS segment_name, D.targetId AS target_id, D.name AS target_name
FROM dim_segment AS A
JOIN hkg_br_segment_target AS AD ON A.segmentid = AD.segmentid
JOIN dim_target AS D ON AD.targetId = D.targetId
WHERE D.createdTime >= DATEADD(MONTH, -3, CURRENT_DATE)
LIMIT 3
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/audit/events",
    "params": {
      "limit": "3",
      "property": "assetType==destination"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/audit/events?property=assetType==destination&limit=3"
]
```

Generated answer: Based on the SQL evidence, 1 audience(s) match: Gender: Male (ID f6b93428-c021-4058-a1a2-77c277aab564) mapped to amazon-s3. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence, one audience has been newly mapped to a destination in the last 3 months: **Gender: Male**, which was mapped to Amazon S3 on March 29, 2026. This is confirmed by both the SQL query showing the segment-to-destination mapping and the audit log entry recording the activation creation event.

### example_012 / SQL_FIRST_API_VERIFY / 0.8028

Query: List all audiences in the sandbox that have been mapped to new destinations in the last 3 months.

Failure category: `ANSWER_WRONG_FACT`

Recommended fix: Audit answer template field selection and avoid summarizing the wrong row/value.

Generated SQL:
```sql
SELECT DISTINCT A."SEGMENTID" AS segment_id, A."NAME" AS segment_name, D."TARGETID" AS target_id, D."NAME" AS target_name FROM "dim_segment" AS A JOIN "hkg_br_segment_target" AS AD ON A."SEGMENTID" = AD."SEGMENTID" JOIN "dim_target" AS D ON AD."TARGETID" = D."TARGETID" WHERE D."CREATEDTIME" >= DATEADD(MONTH, -3, CURRENT_DATE) LIMIT 3
```

Gold SQL:
```sql
SELECT DISTINCT A.segmentid AS segment_id, A.name AS segment_name, D.targetId AS target_id, D.name AS target_name
FROM dim_segment AS A
JOIN hkg_br_segment_target AS AD ON A.segmentid = AD.segmentid
JOIN dim_target AS D ON AD.targetId = D.targetId
WHERE D.createdTime >= DATEADD(MONTH, -3, CURRENT_DATE)
LIMIT 3
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/audit/events",
    "params": {
      "limit": "3",
      "property": "assetType==destination"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/audit/events?property=assetType==destination&limit=3"
]
```

Generated answer: Based on the SQL evidence, 1 audience(s) match: Gender: Male (ID f6b93428-c021-4058-a1a2-77c277aab564) mapped to amazon-s3. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence, one audience has been newly mapped to a destination in the last 3 months: **Gender: Male**, which was mapped to Amazon S3 on March 29, 2026. This is confirmed by both the SQL query showing the segment-to-destination mapping and the audit log entry recording the activation creation event.

### example_012 / TEMPLATE_FIRST / 0.8028

Query: List all audiences in the sandbox that have been mapped to new destinations in the last 3 months.

Failure category: `ANSWER_WRONG_FACT`

Recommended fix: Audit answer template field selection and avoid summarizing the wrong row/value.

Generated SQL:
```sql
SELECT DISTINCT A."SEGMENTID" AS segment_id, A."NAME" AS segment_name, D."TARGETID" AS target_id, D."NAME" AS target_name FROM "dim_segment" AS A JOIN "hkg_br_segment_target" AS AD ON A."SEGMENTID" = AD."SEGMENTID" JOIN "dim_target" AS D ON AD."TARGETID" = D."TARGETID" WHERE D."CREATEDTIME" >= DATEADD(MONTH, -3, CURRENT_DATE) LIMIT 3
```

Gold SQL:
```sql
SELECT DISTINCT A.segmentid AS segment_id, A.name AS segment_name, D.targetId AS target_id, D.name AS target_name
FROM dim_segment AS A
JOIN hkg_br_segment_target AS AD ON A.segmentid = AD.segmentid
JOIN dim_target AS D ON AD.targetId = D.targetId
WHERE D.createdTime >= DATEADD(MONTH, -3, CURRENT_DATE)
LIMIT 3
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/audit/events",
    "params": {
      "limit": "3",
      "property": "assetType==destination"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/audit/events?property=assetType==destination&limit=3"
]
```

Generated answer: Based on the SQL evidence, 1 audience(s) match: Gender: Male (ID f6b93428-c021-4058-a1a2-77c277aab564) mapped to amazon-s3. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence, one audience has been newly mapped to a destination in the last 3 months: **Gender: Male**, which was mapped to Amazon S3 on March 29, 2026. This is confirmed by both the SQL query showing the segment-to-destination mapping and the audit log entry recording the activation creation event.

### example_028 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.8033

Query: List the most recently created batches.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/catalog/batches",
    "params": {
      "limit": "100",
      "orderBy": "desc:created"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/batches?limit=100&orderBy=desc:created"
]
```

Generated answer: Batch details require live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response, there is one batch currently visible with a processing status. The batch is actively being ingested with some datasets completing successfully while others are still in progress.

### example_019 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.8034

Query: List all merge policies in this sandbox.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/config/mergePolicies",
    "params": {
      "limit": "10"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/config/mergePolicies?limit=10"
]
```

Generated answer: Merge policy information requires Adobe API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: The sandbox has at least two merge policies. The primary one is "Default Timebased," which uses timestamp-ordered attribute merging and is set as the default policy for this sandbox. A second merge policy also exists, though the full details are truncated in the response.

### example_028 / TEMPLATE_FIRST / 0.8034

Query: List the most recently created batches.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/catalog/batches",
    "params": {
      "limit": "100",
      "orderBy": "desc:created"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/batches?limit=100&orderBy=desc:created"
]
```

Generated answer: Batch details require live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response, there is one batch currently visible with a processing status. The batch is actively being ingested with some datasets completing successfully while others are still in progress.

### example_003 / SQL_FIRST_API_VERIFY / 0.8035

Query: List all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, totalProfiles, createdTime, updatedTime, and used in other audience count for each audience. Remove any row limit from the results.

Failure category: `DRY_RUN_ONLY`

Recommended fix: Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations.

Generated SQL:
```sql
SELECT A."SEGMENTID" AS segment_id, A."NAME" AS segment_name, A."TOTALMEMBERS" AS total_profiles, A."CREATEDTIME" AS created_time, A."UPDATEDTIME" AS updated_time FROM "dim_segment" AS A JOIN "hkg_br_segment_target" AS AD ON A."SEGMENTID" = AD."SEGMENTID" JOIN "dim_target" AS D ON AD."TARGETID" = D."TARGETID" WHERE D."DATAFLOWNAME" = 'SMS Opt-In' OR D."NAME" = 'SMS Opt-In' ORDER BY A."NAME"
```

Gold SQL:
```sql
SELECT 
    a.segmentid AS segment_id,
    a.name AS segment_name,
    a.totalmembers AS total_profiles,
    a.createdTime AS created_time,
    a.updatedTime AS updated_time
FROM dim_segment a
JOIN hkg_br_segment_target ad ON a.segmentid = ad.segmentid
JOIN dim_target d ON ad.targetId = d.targetId
WHERE d.dataflowName = 'SMS Opt-In'
ORDER BY a.name
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/audiences",
    "params": {
      "limit": "5",
      "property": "destinationId==<destination_id>"
    }
  },
  {
    "method": "GET",
    "path": "/data/foundation/flowservice/flows",
    "params": {
      "limit": "5",
      "property": "inheritedAttributes.properties.isDestinationFlow==true"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/audiences?property=destinationId==<destination_id>&limit=5",
  "GET /data/foundation/flowservice/flows?property=inheritedAttributes.properties.isDestinationFlow==true&limit=5"
]
```

Generated answer: Based on the evidence provided, there is no data available to answer this question. The SQL query returned zero rows, and live API verification was not executed because Adobe credentials are unavailable, so audience and flow service evidence could not be checked.

Gold answer: Based on the evidence provided, there is no data available to answer this question. The SQL query returned zero rows, the API call to retrieve audiences failed with a 400 error, and the flow service data that was successfully retrieved does not contain information about audiences connected to the SMS Opt-In destination.

### example_019 / SQL_FIRST_API_VERIFY / 0.8035

Query: List all merge policies in this sandbox.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/config/mergePolicies",
    "params": {
      "limit": "10"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/config/mergePolicies?limit=10"
]
```

Generated answer: Merge policy information requires Adobe API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: The sandbox has at least two merge policies. The primary one is "Default Timebased," which uses timestamp-ordered attribute merging and is set as the default policy for this sandbox. A second merge policy also exists, though the full details are truncated in the response.

### example_024 / SQL_FIRST_API_VERIFY / 0.8035

Query: Which segment definitions were updated most recently?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/segment/definitions",
    "params": {
      "limit": "3",
      "orderBy": "updateTime:desc"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/definitions?limit=3&orderBy=updateTime:desc"
]
```

Generated answer: The most recently updated segment definitions require live Adobe API evidence with names, IDs, and update times. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response sorted by creation time in descending order, the most recently created segment definition is **"Person: Birthday Today 001"** (ID: 2fdfefe1-04d0-46ce-9fbd-7611e311dd26) in the external-benchmarking sandbox. The response shows 13 total segment definitions across 5 pages, with this one appearing first in the descending creation time sort.

### example_028 / SQL_FIRST_API_VERIFY / 0.8035

Query: List the most recently created batches.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/catalog/batches",
    "params": {
      "limit": "100",
      "orderBy": "desc:created"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/batches?limit=100&orderBy=desc:created"
]
```

Generated answer: Batch details require live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response, there is one batch currently visible with a processing status. The batch is actively being ingested with some datasets completing successfully while others are still in progress.

### example_017 / TEMPLATE_FIRST / 0.8035

Query: Which tags belong to the category 'Uncategorized'?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/unifiedtags/tagCategory",
    "params": {
      "limit": "100"
    }
  },
  {
    "method": "GET",
    "path": "/unifiedtags/tags",
    "params": {
      "limit": "100",
      "tagCategoryId": "Uncategorized-87891E4066602D250A495F91@AdobeOrg"
    }
  }
]
```

Gold API:
```json
[
  "GET /unifiedtags/tagCategory?limit=100",
  "GET /unifiedtags/tags?limit=100&tagCategoryId=Uncategorized-87891E4066602D250A495F91@AdobeOrg"
]
```

Generated answer: Details for the tag named 'Uncategorized' require live API evidence, including the tag ID, name, category, and Adobe organization. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence, the Uncategorized category contains at least the tags "AI-Generated" and "cool." However, the API response is incomplete—the category metadata indicates there are 5 tags total, but only 2 are shown in the truncated evidence.

### example_019 / TEMPLATE_FIRST / 0.8035

Query: List all merge policies in this sandbox.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/config/mergePolicies",
    "params": {
      "limit": "10"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/config/mergePolicies?limit=10"
]
```

Generated answer: Merge policy information requires Adobe API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: The sandbox has at least two merge policies. The primary one is "Default Timebased," which uses timestamp-ordered attribute merging and is set as the default policy for this sandbox. A second merge policy also exists, though the full details are truncated in the response.

### example_024 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.8036

Query: Which segment definitions were updated most recently?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/segment/definitions",
    "params": {
      "limit": "3",
      "orderBy": "updateTime:desc"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/definitions?limit=3&orderBy=updateTime:desc"
]
```

Generated answer: The most recently updated segment definitions require live Adobe API evidence with names, IDs, and update times. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response sorted by creation time in descending order, the most recently created segment definition is **"Person: Birthday Today 001"** (ID: 2fdfefe1-04d0-46ce-9fbd-7611e311dd26) in the external-benchmarking sandbox. The response shows 13 total segment definitions across 5 pages, with this one appearing first in the descending creation time sort.

### example_017 / SQL_FIRST_API_VERIFY / 0.8036

Query: Which tags belong to the category 'Uncategorized'?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/unifiedtags/tagCategory",
    "params": {
      "limit": "100"
    }
  },
  {
    "method": "GET",
    "path": "/unifiedtags/tags",
    "params": {
      "limit": "100",
      "tagCategoryId": "Uncategorized-87891E4066602D250A495F91@AdobeOrg"
    }
  }
]
```

Gold API:
```json
[
  "GET /unifiedtags/tagCategory?limit=100",
  "GET /unifiedtags/tags?limit=100&tagCategoryId=Uncategorized-87891E4066602D250A495F91@AdobeOrg"
]
```

Generated answer: Details for the tag named 'Uncategorized' require live API evidence, including the tag ID, name, category, and Adobe organization. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence, the Uncategorized category contains at least the tags "AI-Generated" and "cool." However, the API response is incomplete—the category metadata indicates there are 5 tags total, but only 2 are shown in the truncated evidence.

### example_024 / TEMPLATE_FIRST / 0.8036

Query: Which segment definitions were updated most recently?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/segment/definitions",
    "params": {
      "limit": "3",
      "orderBy": "updateTime:desc"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/definitions?limit=3&orderBy=updateTime:desc"
]
```

Generated answer: The most recently updated segment definitions require live Adobe API evidence with names, IDs, and update times. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response sorted by creation time in descending order, the most recently created segment definition is **"Person: Birthday Today 001"** (ID: 2fdfefe1-04d0-46ce-9fbd-7611e311dd26) in the external-benchmarking sandbox. The response shows 13 total segment definitions across 5 pages, with this one appearing first in the descending creation time sort.

### example_003 / TEMPLATE_FIRST / 0.8037

Query: List all segment audiences connected to the destination named 'SMS Opt-In', showing audienceId, name, totalProfiles, createdTime, updatedTime, and used in other audience count for each audience. Remove any row limit from the results.

Failure category: `DRY_RUN_ONLY`

Recommended fix: Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations.

Generated SQL:
```sql
SELECT A."SEGMENTID" AS segment_id, A."NAME" AS segment_name, A."TOTALMEMBERS" AS total_profiles, A."CREATEDTIME" AS created_time, A."UPDATEDTIME" AS updated_time FROM "dim_segment" AS A JOIN "hkg_br_segment_target" AS AD ON A."SEGMENTID" = AD."SEGMENTID" JOIN "dim_target" AS D ON AD."TARGETID" = D."TARGETID" WHERE D."DATAFLOWNAME" = 'SMS Opt-In' OR D."NAME" = 'SMS Opt-In' ORDER BY A."NAME"
```

Gold SQL:
```sql
SELECT 
    a.segmentid AS segment_id,
    a.name AS segment_name,
    a.totalmembers AS total_profiles,
    a.createdTime AS created_time,
    a.updatedTime AS updated_time
FROM dim_segment a
JOIN hkg_br_segment_target ad ON a.segmentid = ad.segmentid
JOIN dim_target d ON ad.targetId = d.targetId
WHERE d.dataflowName = 'SMS Opt-In'
ORDER BY a.name
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/audiences",
    "params": {
      "limit": "5",
      "property": "destinationId==<destination_id>"
    }
  },
  {
    "method": "GET",
    "path": "/data/foundation/flowservice/flows",
    "params": {
      "limit": "5",
      "property": "inheritedAttributes.properties.isDestinationFlow==true"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/audiences?property=destinationId==<destination_id>&limit=5",
  "GET /data/foundation/flowservice/flows?property=inheritedAttributes.properties.isDestinationFlow==true&limit=5"
]
```

Generated answer: Based on the evidence provided, there is no data available to answer this question. The SQL query returned zero rows, and live API verification was not executed because Adobe credentials are unavailable, so audience and flow service evidence could not be checked.

Gold answer: Based on the evidence provided, there is no data available to answer this question. The SQL query returned zero rows, the API call to retrieve audiences failed with a 400 error, and the flow service data that was successfully retrieved does not contain information about audiences connected to the SMS Opt-In destination.

### example_006 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.8074

Query: How many datasets have been ingested using the same schema in the prod sandbox?

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT S."BLUEPRINTID" AS blueprint_id, S."NAME" AS blueprint_name, COUNT(DISTINCT DS."COLLECTIONID") AS collection_count FROM "dim_collection" AS D JOIN "hkg_br_blueprint_collection" AS DS ON D."COLLECTIONID" = DS."COLLECTIONID" JOIN "dim_blueprint" AS S ON DS."BLUEPRINTID" = S."BLUEPRINTID" GROUP BY S."BLUEPRINTID", S."NAME" HAVING COUNT(DISTINCT DS."COLLECTIONID") > 1
```

Gold SQL:
```sql
SELECT S.blueprintid AS blueprint_id,
       S.name AS blueprint_name,
       COUNT(DISTINCT DS.collectionid) AS collection_count
FROM dim_collection AS D
JOIN hkg_br_blueprint_collection AS DS ON D.collectionid = DS.collectionid
JOIN dim_blueprint AS S ON DS.blueprintid = S.blueprintid
GROUP BY S.blueprintid,
         S.name
HAVING COUNT(DISTINCT DS.collectionid) > 1
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/catalog/dataSets",
    "params": {
      "limit": "25",
      "property": "schema.name"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/dataSets?limit=25&property=schema.name",
  "GET /data/foundation/schemaregistry/tenant/schemas/{schema_id}"
]
```

Generated answer: Based on the evidence provided, 2 datasets have been ingested using the same schema. These datasets use "Journey Inbound External Segment Profile Schema". Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence provided, **2 datasets** have been ingested using the same schema in the prod sandbox. These datasets both use the "Journey Inbound External Segment Profile Schema."

### example_006 / SQL_FIRST_API_VERIFY / 0.8074

Query: How many datasets have been ingested using the same schema in the prod sandbox?

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT S."BLUEPRINTID" AS blueprint_id, S."NAME" AS blueprint_name, COUNT(DISTINCT DS."COLLECTIONID") AS collection_count FROM "dim_collection" AS D JOIN "hkg_br_blueprint_collection" AS DS ON D."COLLECTIONID" = DS."COLLECTIONID" JOIN "dim_blueprint" AS S ON DS."BLUEPRINTID" = S."BLUEPRINTID" GROUP BY S."BLUEPRINTID", S."NAME" HAVING COUNT(DISTINCT DS."COLLECTIONID") > 1
```

Gold SQL:
```sql
SELECT S.blueprintid AS blueprint_id,
       S.name AS blueprint_name,
       COUNT(DISTINCT DS.collectionid) AS collection_count
FROM dim_collection AS D
JOIN hkg_br_blueprint_collection AS DS ON D.collectionid = DS.collectionid
JOIN dim_blueprint AS S ON DS.blueprintid = S.blueprintid
GROUP BY S.blueprintid,
         S.name
HAVING COUNT(DISTINCT DS.collectionid) > 1
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/catalog/dataSets",
    "params": {
      "limit": "25",
      "property": "schema.name"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/dataSets?limit=25&property=schema.name",
  "GET /data/foundation/schemaregistry/tenant/schemas/{schema_id}"
]
```

Generated answer: Based on the evidence provided, 2 datasets have been ingested using the same schema. These datasets use "Journey Inbound External Segment Profile Schema". Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence provided, **2 datasets** have been ingested using the same schema in the prod sandbox. These datasets both use the "Journey Inbound External Segment Profile Schema."

### example_016 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.8075

Query: List all tags in this sandbox.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/unifiedtags/tags",
    "params": {
      "limit": "25"
    }
  }
]
```

Gold API:
```json
[
  "GET /unifiedtags/tags?limit=25"
]
```

Generated answer: The requested tag list requires live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response, the sandbox contains at least two tags: "AI-Generated" and "cool". The response appears to be truncated, so there may be additional tags not shown in the evidence.

### example_018 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.8075

Query: Show me the details of the tag named 'cool'.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/unifiedtags/tags/51175a7f-aa60-4533-bef1-717b3cef7818",
    "params": {}
  }
]
```

Gold API:
```json
[
  "GET /unifiedtags/tags/51175a7f-aa60-4533-bef1-717b3cef7818"
]
```

Generated answer: Details for the tag named 'cool' require live API evidence, including the tag ID, name, category, and Adobe organization. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: I notice a discrepancy: the question asks for a tag named 'cool', but the API response shows details for a tag named 'sublist' (ID: 51175a7f-aa60-4533-bef1-717b3cef7818). The tag 'sublist' belongs to the Uncategorized category in the Adobe organization 87891E4066602D250A495F91@AdobeOrg. If you intended to look up a different tag named 'cool', that information isn't in the evidence provided.

### example_006 / TEMPLATE_FIRST / 0.8075

Query: How many datasets have been ingested using the same schema in the prod sandbox?

Failure category: `API_CALL_COUNT_MISMATCH`

Recommended fix: Emit the expected sequence of API calls or intentionally document why a call is skipped.

Generated SQL:
```sql
SELECT S."BLUEPRINTID" AS blueprint_id, S."NAME" AS blueprint_name, COUNT(DISTINCT DS."COLLECTIONID") AS collection_count FROM "dim_collection" AS D JOIN "hkg_br_blueprint_collection" AS DS ON D."COLLECTIONID" = DS."COLLECTIONID" JOIN "dim_blueprint" AS S ON DS."BLUEPRINTID" = S."BLUEPRINTID" GROUP BY S."BLUEPRINTID", S."NAME" HAVING COUNT(DISTINCT DS."COLLECTIONID") > 1
```

Gold SQL:
```sql
SELECT S.blueprintid AS blueprint_id,
       S.name AS blueprint_name,
       COUNT(DISTINCT DS.collectionid) AS collection_count
FROM dim_collection AS D
JOIN hkg_br_blueprint_collection AS DS ON D.collectionid = DS.collectionid
JOIN dim_blueprint AS S ON DS.blueprintid = S.blueprintid
GROUP BY S.blueprintid,
         S.name
HAVING COUNT(DISTINCT DS.collectionid) > 1
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/catalog/dataSets",
    "params": {
      "limit": "25",
      "property": "schema.name"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/dataSets?limit=25&property=schema.name",
  "GET /data/foundation/schemaregistry/tenant/schemas/{schema_id}"
]
```

Generated answer: Based on the evidence provided, 2 datasets have been ingested using the same schema. These datasets use "Journey Inbound External Segment Profile Schema". Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence provided, **2 datasets** have been ingested using the same schema in the prod sandbox. These datasets both use the "Journey Inbound External Segment Profile Schema."

### example_016 / TEMPLATE_FIRST / 0.8076

Query: List all tags in this sandbox.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/unifiedtags/tags",
    "params": {
      "limit": "25"
    }
  }
]
```

Gold API:
```json
[
  "GET /unifiedtags/tags?limit=25"
]
```

Generated answer: The requested tag list requires live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response, the sandbox contains at least two tags: "AI-Generated" and "cool". The response appears to be truncated, so there may be additional tags not shown in the evidence.

### example_018 / TEMPLATE_FIRST / 0.8076

Query: Show me the details of the tag named 'cool'.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/unifiedtags/tags/51175a7f-aa60-4533-bef1-717b3cef7818",
    "params": {}
  }
]
```

Gold API:
```json
[
  "GET /unifiedtags/tags/51175a7f-aa60-4533-bef1-717b3cef7818"
]
```

Generated answer: Details for the tag named 'cool' require live API evidence, including the tag ID, name, category, and Adobe organization. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: I notice a discrepancy: the question asks for a tag named 'cool', but the API response shows details for a tag named 'sublist' (ID: 51175a7f-aa60-4533-bef1-717b3cef7818). The tag 'sublist' belongs to the Uncategorized category in the Adobe organization 87891E4066602D250A495F91@AdobeOrg. If you intended to look up a different tag named 'cool', that information isn't in the evidence provided.

### example_016 / SQL_FIRST_API_VERIFY / 0.8077

Query: List all tags in this sandbox.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/unifiedtags/tags",
    "params": {
      "limit": "25"
    }
  }
]
```

Gold API:
```json
[
  "GET /unifiedtags/tags?limit=25"
]
```

Generated answer: The requested tag list requires live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response, the sandbox contains at least two tags: "AI-Generated" and "cool". The response appears to be truncated, so there may be additional tags not shown in the evidence.

### example_018 / SQL_FIRST_API_VERIFY / 0.8077

Query: Show me the details of the tag named 'cool'.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/unifiedtags/tags/51175a7f-aa60-4533-bef1-717b3cef7818",
    "params": {}
  }
]
```

Gold API:
```json
[
  "GET /unifiedtags/tags/51175a7f-aa60-4533-bef1-717b3cef7818"
]
```

Generated answer: Details for the tag named 'cool' require live API evidence, including the tag ID, name, category, and Adobe organization. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: I notice a discrepancy: the question asks for a tag named 'cool', but the API response shows details for a tag named 'sublist' (ID: 51175a7f-aa60-4533-bef1-717b3cef7818). The tag 'sublist' belongs to the Uncategorized category in the Adobe organization 87891E4066602D250A495F91@AdobeOrg. If you intended to look up a different tag named 'cool', that information isn't in the evidence provided.

### example_015 / SQL_FIRST_API_VERIFY / 0.8080

Query: How many tags exist in this sandbox?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/unifiedtags/tags",
    "params": {
      "limit": "20"
    }
  }
]
```

Gold API:
```json
[
  "GET /unifiedtags/tags?limit=20"
]
```

Generated answer: The tag count cannot be determined from the available evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence shown, there are at least 2 tags visible in the API response: "AI-Generated" and "cool." However, the response appears to be truncated, so the complete tag count from the sandbox cannot be determined from this partial data.

### example_015 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.8083

Query: How many tags exist in this sandbox?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/unifiedtags/tags",
    "params": {
      "limit": "20"
    }
  }
]
```

Gold API:
```json
[
  "GET /unifiedtags/tags?limit=20"
]
```

Generated answer: The tag count cannot be determined from the available evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence shown, there are at least 2 tags visible in the API response: "AI-Generated" and "cool." However, the response appears to be truncated, so the complete tag count from the sandbox cannot be determined from this partial data.

### example_027 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.8087

Query: Show all segment jobs with status 'QUEUED'.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/segment/jobs",
    "params": {
      "limit": "10"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/jobs?limit=10"
]
```

Generated answer: Segment evaluation job IDs, statuses, sandbox, and segment counts require live Adobe API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response provided, there are no segment jobs with status 'QUEUED'. The single job returned has a status of 'SUCCEEDED'.

### example_027 / SQL_FIRST_API_VERIFY / 0.8087

Query: Show all segment jobs with status 'QUEUED'.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/segment/jobs",
    "params": {
      "limit": "10"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/jobs?limit=10"
]
```

Generated answer: Segment evaluation job IDs, statuses, sandbox, and segment counts require live Adobe API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response provided, there are no segment jobs with status 'QUEUED'. The single job returned has a status of 'SUCCEEDED'.

### example_034 / SQL_FIRST_API_VERIFY / 0.8100

Query: Show ingestion record counts and batch success counts for the last 90 days.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "POST",
    "path": "/data/infrastructure/observability/insights/metrics",
    "params": {
      "end": "2026-04-01T23:59:59.000Z",
      "granularity": "day",
      "metrics": [
        {
          "aggregator": "sum",
          "filters": [],
          "name": "timeseries.ingestion.dataset.recordsuccess.count"
        },
        {
          "aggregator": "sum",
          "filters": [],
          "name": "timeseries.ingestion.dataset.batchsuccess.count"
        }
      ],
      "start": "2026-03-01T00:00:00.000Z"
    }
  }
]
```

Gold API:
```json
[
  "POST /data/infrastructure/observability/insights/metrics body={\"start\":\"2026-03-01T00:00:00.000Z\",\"end\":\"2026-04-01T23:59:59.000Z\",\"granularity\":\"day\",\"metrics\":[{\"name\":\"timeseries.ingestion.dataset.recordsuccess.count\",\"filters\":[],\"aggregator\":\"sum\"},{\"name\":\"timeseries.ingestion.dataset.batchsuccess.count\",\"filters\":[],\"aggregator\":\"sum\"}]}"
]
```

Generated answer: Values for timeseries.ingestion.dataset.recordsuccess.count and timeseries.ingestion.dataset.batchsuccess.count for the requested time window require live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the available data for the last 90 days, ingestion record success counts are minimal, with zero successful records recorded for most dates in March 2026. Only March 31st shows activity with 2,701 successfully ingested records. No batch success count data is included in the metrics response provided.

### example_034 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.8103

Query: Show ingestion record counts and batch success counts for the last 90 days.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "POST",
    "path": "/data/infrastructure/observability/insights/metrics",
    "params": {
      "end": "2026-04-01T23:59:59.000Z",
      "granularity": "day",
      "metrics": [
        {
          "aggregator": "sum",
          "filters": [],
          "name": "timeseries.ingestion.dataset.recordsuccess.count"
        },
        {
          "aggregator": "sum",
          "filters": [],
          "name": "timeseries.ingestion.dataset.batchsuccess.count"
        }
      ],
      "start": "2026-03-01T00:00:00.000Z"
    }
  }
]
```

Gold API:
```json
[
  "POST /data/infrastructure/observability/insights/metrics body={\"start\":\"2026-03-01T00:00:00.000Z\",\"end\":\"2026-04-01T23:59:59.000Z\",\"granularity\":\"day\",\"metrics\":[{\"name\":\"timeseries.ingestion.dataset.recordsuccess.count\",\"filters\":[],\"aggregator\":\"sum\"},{\"name\":\"timeseries.ingestion.dataset.batchsuccess.count\",\"filters\":[],\"aggregator\":\"sum\"}]}"
]
```

Generated answer: Values for timeseries.ingestion.dataset.recordsuccess.count and timeseries.ingestion.dataset.batchsuccess.count for the requested time window require live API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the available data for the last 90 days, ingestion record success counts are minimal, with zero successful records recorded for most dates in March 2026. Only March 31st shows activity with 2,701 successfully ingested records. No batch success count data is included in the metrics response provided.

### example_026 / SQL_FIRST_API_VERIFY / 0.8111

Query: How many segment jobs are currently processing?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/segment/jobs",
    "params": {
      "limit": "20"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/jobs?limit=20"
]
```

Generated answer: The segment evaluation job count requires live Adobe API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response, **zero segment jobs are currently processing**. The only visible job in the response has a status of "SUCCEEDED," indicating it has already completed.

### example_026 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.8112

Query: How many segment jobs are currently processing?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/segment/jobs",
    "params": {
      "limit": "20"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/jobs?limit=20"
]
```

Generated answer: The segment evaluation job count requires live Adobe API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response, **zero segment jobs are currently processing**. The only visible job in the response has a status of "SUCCEEDED," indicating it has already completed.

### example_021 / SQL_FIRST_API_VERIFY / 0.8138

Query: Show the default merge policy for schema class '_xdm.context.profile'.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/config/mergePolicies",
    "params": {
      "limit": "5"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/config/mergePolicies?limit=5"
]
```

Generated answer: The default merge policy requires live Adobe API evidence. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: The default merge policy for the schema class '_xdm.context.profile' is called **Default Timebased**. It uses timestamp-ordered attribute merging, where conflicting attributes are resolved by selecting the most recent value, and relies on the Personalized Data Graph for identity resolution.

### example_023 / SQL_FIRST_API_VERIFY / 0.8148

Query: List all segment definitions.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/segment/definitions",
    "params": {
      "limit": "10"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/definitions?limit=10"
]
```

Generated answer: The requested segment definition list requires live Adobe API evidence with definition names, IDs, and pagination counts. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: There are 13 segment definitions total across 2 pages. The visible segment from the first page is "Person: Birthday Today 001," which targets all profiles whose birthday falls on a specific month/day. The response was paginated with 10 results per page, so additional segment definitions exist on the second page.

### example_022 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.8149

Query: How many segment definitions exist in this sandbox?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/segment/definitions",
    "params": {
      "limit": "100"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/definitions?limit=100"
]
```

Generated answer: Segment definition details require live Adobe API evidence with definition names, IDs, and counts. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response, there are **13 segment definitions** in the external-benchmarking sandbox, as indicated by the `totalCount` field in the pagination metadata.

### example_023 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.8149

Query: List all segment definitions.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/segment/definitions",
    "params": {
      "limit": "10"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/definitions?limit=10"
]
```

Generated answer: The requested segment definition list requires live Adobe API evidence with definition names, IDs, and pagination counts. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: There are 13 segment definitions total across 2 pages. The visible segment from the first page is "Person: Birthday Today 001," which targets all profiles whose birthday falls on a specific month/day. The response was paginated with 10 results per page, so additional segment definitions exist on the second page.

### example_022 / SQL_FIRST_API_VERIFY / 0.8149

Query: How many segment definitions exist in this sandbox?

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/segment/definitions",
    "params": {
      "limit": "100"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/definitions?limit=100"
]
```

Generated answer: Segment definition details require live Adobe API evidence with definition names, IDs, and counts. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the API response, there are **13 segment definitions** in the external-benchmarking sandbox, as indicated by the `totalCount` field in the pagination metadata.

### example_023 / TEMPLATE_FIRST / 0.8149

Query: List all segment definitions.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/core/ups/segment/definitions",
    "params": {
      "limit": "10"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/core/ups/segment/definitions?limit=10"
]
```

Generated answer: The requested segment definition list requires live Adobe API evidence with definition names, IDs, and pagination counts. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: There are 13 segment definitions total across 2 pages. The visible segment from the first page is "Person: Birthday Today 001," which targets all profiles whose birthday falls on a specific month/day. The response was paginated with 10 results per page, so additional segment definitions exist on the second page.

### example_009 / SQL_FIRST_API_VERIFY / 0.8163

Query: Provide more details for the schema 'weRetail: Customer Actions'

Failure category: `DRY_RUN_ONLY`

Recommended fix: Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations.

Generated SQL:
```sql
SELECT S."BLUEPRINTID" AS blueprint_id, S."NAME", S."CLASS", S."ISPROFILEENABLED", S."UPDATEDTIME" AS updated_time, S."REQUIREDFIELDS" AS required_fields, COUNT(DISTINCT SD."COLLECTIONID") AS collection_count, COUNT(DISTINCT SA."PROPERTY") AS property_count FROM "dim_blueprint" AS S LEFT JOIN "hkg_br_blueprint_collection" AS SD ON S."BLUEPRINTID" = SD."BLUEPRINTID" LEFT JOIN "hkg_br_blueprint_property" AS SA ON S."BLUEPRINTID" = SA."BLUEPRINTID" WHERE LOWER(S."NAME") = LOWER('weRetail: Customer Actions') GROUP BY S."BLUEPRINTID", S."NAME", S."CLASS", S."ISPROFILEENABLED", S."UPDATEDTIME", S."REQUIREDFIELDS" LIMIT 3
```

Gold SQL:
```sql
SELECT S.BLUEPRINTID AS blueprint_id,
       S.NAME,
       S.CLASS,
       S.ISPROFILEENABLED,
       S.UPDATEDTIME AS updated_time,
       S.REQUIREDFIELDS AS required_fields,
       COUNT(DISTINCT SD.COLLECTIONID) AS collection_count,
       COUNT(DISTINCT SA.PROPERTY) AS property_count
FROM DIM_BLUEPRINT AS S
LEFT JOIN HKG_BR_BLUEPRINT_COLLECTION AS SD ON S.BLUEPRINTID = SD.BLUEPRINTID
LEFT JOIN HKG_BR_BLUEPRINT_PROPERTY AS SA ON S.BLUEPRINTID = SA.BLUEPRINTID
WHERE LOWER(S.NAME) = LOWER('weRetail: Customer Actions')
GROUP BY S.BLUEPRINTID,
         S.NAME,
         S.CLASS,
         S.ISPROFILEENABLED,
         S.UPDATEDTIME,
         S.REQUIREDFIELDS
LIMIT 3
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/schemas",
    "params": {
      "filter": "name==weRetail: Customer Actions",
      "limit": "5"
    }
  }
]
```

Gold API:
```json
[
  "GET /schemas?limit=5&filter=name==weRetail: Customer Actions"
]
```

Generated answer: The 'weRetail: Customer Actions' schema has class https://ns.adobe.com/xdm/context/experienceevent, has 6 properties, across 1 collection(s), and was last updated on 2026-03-29. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: The 'weRetail: Customer Actions' schema is an Experience Event-based schema that tracks customer interactions. It has six properties organized across one collection, with no required fields, and is profile-enabled to allow customer identity tracking. The schema was last updated on March 29, 2026.

### example_009 / TEMPLATE_FIRST / 0.8164

Query: Provide more details for the schema 'weRetail: Customer Actions'

Failure category: `DRY_RUN_ONLY`

Recommended fix: Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations.

Generated SQL:
```sql
SELECT S."BLUEPRINTID" AS blueprint_id, S."NAME", S."CLASS", S."ISPROFILEENABLED", S."UPDATEDTIME" AS updated_time, S."REQUIREDFIELDS" AS required_fields, COUNT(DISTINCT SD."COLLECTIONID") AS collection_count, COUNT(DISTINCT SA."PROPERTY") AS property_count FROM "dim_blueprint" AS S LEFT JOIN "hkg_br_blueprint_collection" AS SD ON S."BLUEPRINTID" = SD."BLUEPRINTID" LEFT JOIN "hkg_br_blueprint_property" AS SA ON S."BLUEPRINTID" = SA."BLUEPRINTID" WHERE LOWER(S."NAME") = LOWER('weRetail: Customer Actions') GROUP BY S."BLUEPRINTID", S."NAME", S."CLASS", S."ISPROFILEENABLED", S."UPDATEDTIME", S."REQUIREDFIELDS" LIMIT 3
```

Gold SQL:
```sql
SELECT S.BLUEPRINTID AS blueprint_id,
       S.NAME,
       S.CLASS,
       S.ISPROFILEENABLED,
       S.UPDATEDTIME AS updated_time,
       S.REQUIREDFIELDS AS required_fields,
       COUNT(DISTINCT SD.COLLECTIONID) AS collection_count,
       COUNT(DISTINCT SA.PROPERTY) AS property_count
FROM DIM_BLUEPRINT AS S
LEFT JOIN HKG_BR_BLUEPRINT_COLLECTION AS SD ON S.BLUEPRINTID = SD.BLUEPRINTID
LEFT JOIN HKG_BR_BLUEPRINT_PROPERTY AS SA ON S.BLUEPRINTID = SA.BLUEPRINTID
WHERE LOWER(S.NAME) = LOWER('weRetail: Customer Actions')
GROUP BY S.BLUEPRINTID,
         S.NAME,
         S.CLASS,
         S.ISPROFILEENABLED,
         S.UPDATEDTIME,
         S.REQUIREDFIELDS
LIMIT 3
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/schemas",
    "params": {
      "filter": "name==weRetail: Customer Actions",
      "limit": "5"
    }
  }
]
```

Gold API:
```json
[
  "GET /schemas?limit=5&filter=name==weRetail: Customer Actions"
]
```

Generated answer: The 'weRetail: Customer Actions' schema has class https://ns.adobe.com/xdm/context/experienceevent, has 6 properties, across 1 collection(s), and was last updated on 2026-03-29. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: The 'weRetail: Customer Actions' schema is an Experience Event-based schema that tracks customer interactions. It has six properties organized across one collection, with no required fields, and is profile-enabled to allow customer identity tracking. The schema was last updated on March 29, 2026.

### example_032 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.8217

Query: Show failed files for batch 01KP6MNQ3X71RP6MNH6FHWGHVE.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/export/batches/01KP6MNQ3X71RP6MNH6FHWGHVE/failed",
    "params": {}
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/export/batches/01KP6MNQ3X71RP6MNH6FHWGHVE/failed"
]
```

Generated answer: Based on the evidence provided, there are no failed dataflow runs to report. The SQL query returned zero rows, and live API verification was not executed because Adobe credentials are unavailable.

Gold answer: There are no failed files for batch 01KP6MNQ3X71RP6MNH6FHWGHVE. The API request returned a 404 status indicating no failures were recorded for this batch.

### example_032 / SQL_FIRST_API_VERIFY / 0.8218

Query: Show failed files for batch 01KP6MNQ3X71RP6MNH6FHWGHVE.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/export/batches/01KP6MNQ3X71RP6MNH6FHWGHVE/failed",
    "params": {}
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/export/batches/01KP6MNQ3X71RP6MNH6FHWGHVE/failed"
]
```

Generated answer: Based on the evidence provided, there are no failed dataflow runs to report. The SQL query returned zero rows, and live API verification was not executed because Adobe credentials are unavailable.

Gold answer: There are no failed files for batch 01KP6MNQ3X71RP6MNH6FHWGHVE. The API request returned a 404 status indicating no failures were recorded for this batch.

### example_032 / TEMPLATE_FIRST / 0.8218

Query: Show failed files for batch 01KP6MNQ3X71RP6MNH6FHWGHVE.

Failure category: `ANSWER_TOO_GENERIC`

Recommended fix: Add a query-family answer template that names concrete SQL/API evidence.

Generated SQL:
```sql

```

Gold SQL:
```sql

```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/export/batches/01KP6MNQ3X71RP6MNH6FHWGHVE/failed",
    "params": {}
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/export/batches/01KP6MNQ3X71RP6MNH6FHWGHVE/failed"
]
```

Generated answer: Based on the evidence provided, there are no failed dataflow runs to report. The SQL query returned zero rows, and live API verification was not executed because Adobe credentials are unavailable.

Gold answer: There are no failed files for batch 01KP6MNQ3X71RP6MNH6FHWGHVE. The API request returned a 404 status indicating no failures were recorded for this batch.

### example_002 / SQL_FIRST_API_VERIFY / 0.8283

Query: List all journeys

Failure category: `DRY_RUN_ONLY`

Recommended fix: Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations.

Generated SQL:
```sql
SELECT CAMPAIGN."NAME" AS CAMPAIGNNAME, CAMPAIGN."CAMPAIGNID" AS CAMPAIGNID FROM "dim_campaign" AS CAMPAIGN
```

Gold SQL:
```sql
SELECT CAMPAIGN.NAME AS CAMPAIGNNAME,
       CAMPAIGN.CAMPAIGNID
FROM DIM_CAMPAIGN AS CAMPAIGN
LIMIT 10
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/ajo/journey",
    "params": {
      "pageSize": "10"
    }
  }
]
```

Gold API:
```json
[
  "GET /ajo/journey?pageSize=10"
]
```

Generated answer: Based on the available evidence, there are 2 journeys found in the database: Birthday Message and Gold Tier Welcome Email. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the available evidence, there are two journeys found in the database: Birthday Message and Gold Tier Welcome Email. However, the Adobe Journey Optimizer API returned no results when queried, suggesting a potential discrepancy between the database records and what the API is currently returning.

### example_002 / TEMPLATE_FIRST / 0.8284

Query: List all journeys

Failure category: `DRY_RUN_ONLY`

Recommended fix: Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations.

Generated SQL:
```sql
SELECT CAMPAIGN."NAME" AS CAMPAIGNNAME, CAMPAIGN."CAMPAIGNID" AS CAMPAIGNID FROM "dim_campaign" AS CAMPAIGN
```

Gold SQL:
```sql
SELECT CAMPAIGN.NAME AS CAMPAIGNNAME,
       CAMPAIGN.CAMPAIGNID
FROM DIM_CAMPAIGN AS CAMPAIGN
LIMIT 10
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/ajo/journey",
    "params": {
      "pageSize": "10"
    }
  }
]
```

Gold API:
```json
[
  "GET /ajo/journey?pageSize=10"
]
```

Generated answer: Based on the available evidence, there are 2 journeys found in the database: Birthday Message and Gold Tier Welcome Email. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the available evidence, there are two journeys found in the database: Birthday Message and Gold Tier Welcome Email. However, the Adobe Journey Optimizer API returned no results when queried, suggesting a potential discrepancy between the database records and what the API is currently returning.

### example_004 / SQL_FIRST_API_VERIFY / 0.8349

Query: Show me the IDs of failed dataflow runs

Failure category: `DRY_RUN_ONLY`

Recommended fix: Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations.

Generated SQL:
```sql
SELECT "DATAFLOWNAME", "STATE", "TARGETID", "CONNECTIONSPECID", "NAME" FROM "dim_target" WHERE LOWER(CAST("STATE" AS VARCHAR)) LIKE LOWER('%failed%') LIMIT 50
```

Gold SQL:
```sql
SELECT DISTINCT S.DATAFLOWID AS dataflow_id
FROM DIM_CONNECTOR AS S
WHERE S.STATE ILIKE '%loyalty%'
LIMIT 50
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/flowservice/flows",
    "params": {
      "filter": "state eq 'failed'",
      "limit": "50"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/flowservice/flows?filter=state eq 'failed'&limit=50"
]
```

Generated answer: Based on the evidence provided, there are no failed dataflow runs to report. The SQL query returned zero rows, and live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence provided, there are **no failed dataflow runs** to report. The SQL query returned zero rows, indicating no failed runs are recorded in the database. The API response shows available flows but doesn't contain run status information.

### example_009 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.8351

Query: Provide more details for the schema 'weRetail: Customer Actions'

Failure category: `UNKNOWN`

Recommended fix: Inspect trajectory manually and add a targeted deterministic rule only if it generalizes.

Generated SQL:
```sql
SELECT S."BLUEPRINTID" AS blueprint_id, S."NAME", S."CLASS", S."ISPROFILEENABLED", S."UPDATEDTIME" AS updated_time, S."REQUIREDFIELDS" AS required_fields, COUNT(DISTINCT SD."COLLECTIONID") AS collection_count, COUNT(DISTINCT SA."PROPERTY") AS property_count FROM "dim_blueprint" AS S LEFT JOIN "hkg_br_blueprint_collection" AS SD ON S."BLUEPRINTID" = SD."BLUEPRINTID" LEFT JOIN "hkg_br_blueprint_property" AS SA ON S."BLUEPRINTID" = SA."BLUEPRINTID" WHERE LOWER(S."NAME") = LOWER('weRetail: Customer Actions') GROUP BY S."BLUEPRINTID", S."NAME", S."CLASS", S."ISPROFILEENABLED", S."UPDATEDTIME", S."REQUIREDFIELDS" LIMIT 3
```

Gold SQL:
```sql
SELECT S.BLUEPRINTID AS blueprint_id,
       S.NAME,
       S.CLASS,
       S.ISPROFILEENABLED,
       S.UPDATEDTIME AS updated_time,
       S.REQUIREDFIELDS AS required_fields,
       COUNT(DISTINCT SD.COLLECTIONID) AS collection_count,
       COUNT(DISTINCT SA.PROPERTY) AS property_count
FROM DIM_BLUEPRINT AS S
LEFT JOIN HKG_BR_BLUEPRINT_COLLECTION AS SD ON S.BLUEPRINTID = SD.BLUEPRINTID
LEFT JOIN HKG_BR_BLUEPRINT_PROPERTY AS SA ON S.BLUEPRINTID = SA.BLUEPRINTID
WHERE LOWER(S.NAME) = LOWER('weRetail: Customer Actions')
GROUP BY S.BLUEPRINTID,
         S.NAME,
         S.CLASS,
         S.ISPROFILEENABLED,
         S.UPDATEDTIME,
         S.REQUIREDFIELDS
LIMIT 3
```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /schemas?limit=5&filter=name==weRetail: Customer Actions"
]
```

Generated answer: The 'weRetail: Customer Actions' schema has class https://ns.adobe.com/xdm/context/experienceevent, has 6 properties, across 1 collection(s), and was last updated on 2026-03-29. API evidence was not requested.

Gold answer: The 'weRetail: Customer Actions' schema is an Experience Event-based schema that tracks customer interactions. It has six properties organized across one collection, with no required fields, and is profile-enabled to allow customer identity tracking. The schema was last updated on March 29, 2026.

### example_004 / LLM_FREE_AGENT_BASELINE / 0.8352

Query: Show me the IDs of failed dataflow runs

Failure category: `DRY_RUN_ONLY`

Recommended fix: Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations.

Generated SQL:
```sql
SELECT "DATAFLOWNAME", "STATE", "TARGETID", "CONNECTIONSPECID", "NAME" FROM "dim_target" WHERE LOWER(CAST("STATE" AS VARCHAR)) LIKE LOWER('%failed%') LIMIT 50
```

Gold SQL:
```sql
SELECT DISTINCT S.DATAFLOWID AS dataflow_id
FROM DIM_CONNECTOR AS S
WHERE S.STATE ILIKE '%loyalty%'
LIMIT 50
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/flowservice/flows",
    "params": {
      "filter": "state eq 'failed'",
      "limit": "50"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/flowservice/flows?filter=state eq 'failed'&limit=50"
]
```

Generated answer: Based on the evidence provided, there are no failed dataflow runs to report. The SQL query returned zero rows, and live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence provided, there are **no failed dataflow runs** to report. The SQL query returned zero rows, indicating no failed runs are recorded in the database. The API response shows available flows but doesn't contain run status information.

### example_009 / SQL_ONLY_BASELINE / 0.8352

Query: Provide more details for the schema 'weRetail: Customer Actions'

Failure category: `UNKNOWN`

Recommended fix: Inspect trajectory manually and add a targeted deterministic rule only if it generalizes.

Generated SQL:
```sql
SELECT S."BLUEPRINTID" AS blueprint_id, S."NAME", S."CLASS", S."ISPROFILEENABLED", S."UPDATEDTIME" AS updated_time, S."REQUIREDFIELDS" AS required_fields, COUNT(DISTINCT SD."COLLECTIONID") AS collection_count, COUNT(DISTINCT SA."PROPERTY") AS property_count FROM "dim_blueprint" AS S LEFT JOIN "hkg_br_blueprint_collection" AS SD ON S."BLUEPRINTID" = SD."BLUEPRINTID" LEFT JOIN "hkg_br_blueprint_property" AS SA ON S."BLUEPRINTID" = SA."BLUEPRINTID" WHERE LOWER(S."NAME") = LOWER('weRetail: Customer Actions') GROUP BY S."BLUEPRINTID", S."NAME", S."CLASS", S."ISPROFILEENABLED", S."UPDATEDTIME", S."REQUIREDFIELDS" LIMIT 3
```

Gold SQL:
```sql
SELECT S.BLUEPRINTID AS blueprint_id,
       S.NAME,
       S.CLASS,
       S.ISPROFILEENABLED,
       S.UPDATEDTIME AS updated_time,
       S.REQUIREDFIELDS AS required_fields,
       COUNT(DISTINCT SD.COLLECTIONID) AS collection_count,
       COUNT(DISTINCT SA.PROPERTY) AS property_count
FROM DIM_BLUEPRINT AS S
LEFT JOIN HKG_BR_BLUEPRINT_COLLECTION AS SD ON S.BLUEPRINTID = SD.BLUEPRINTID
LEFT JOIN HKG_BR_BLUEPRINT_PROPERTY AS SA ON S.BLUEPRINTID = SA.BLUEPRINTID
WHERE LOWER(S.NAME) = LOWER('weRetail: Customer Actions')
GROUP BY S.BLUEPRINTID,
         S.NAME,
         S.CLASS,
         S.ISPROFILEENABLED,
         S.UPDATEDTIME,
         S.REQUIREDFIELDS
LIMIT 3
```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /schemas?limit=5&filter=name==weRetail: Customer Actions"
]
```

Generated answer: The 'weRetail: Customer Actions' schema has class https://ns.adobe.com/xdm/context/experienceevent, has 6 properties, across 1 collection(s), and was last updated on 2026-03-29. API evidence was not requested.

Gold answer: The 'weRetail: Customer Actions' schema is an Experience Event-based schema that tracks customer interactions. It has six properties organized across one collection, with no required fields, and is profile-enabled to allow customer identity tracking. The schema was last updated on March 29, 2026.

### example_004 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.8353

Query: Show me the IDs of failed dataflow runs

Failure category: `DRY_RUN_ONLY`

Recommended fix: Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations.

Generated SQL:
```sql
SELECT "DATAFLOWNAME", "STATE", "TARGETID", "CONNECTIONSPECID", "NAME" FROM "dim_target" WHERE LOWER(CAST("STATE" AS VARCHAR)) LIKE LOWER('%failed%') LIMIT 50
```

Gold SQL:
```sql
SELECT DISTINCT S.DATAFLOWID AS dataflow_id
FROM DIM_CONNECTOR AS S
WHERE S.STATE ILIKE '%loyalty%'
LIMIT 50
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/flowservice/flows",
    "params": {
      "filter": "state eq 'failed'",
      "limit": "50"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/flowservice/flows?filter=state eq 'failed'&limit=50"
]
```

Generated answer: Based on the evidence provided, there are no failed dataflow runs to report. The SQL query returned zero rows, and live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence provided, there are **no failed dataflow runs** to report. The SQL query returned zero rows, indicating no failed runs are recorded in the database. The API response shows available flows but doesn't contain run status information.

### example_004 / TEMPLATE_FIRST / 0.8353

Query: Show me the IDs of failed dataflow runs

Failure category: `DRY_RUN_ONLY`

Recommended fix: Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations.

Generated SQL:
```sql
SELECT "DATAFLOWNAME", "STATE", "TARGETID", "CONNECTIONSPECID", "NAME" FROM "dim_target" WHERE LOWER(CAST("STATE" AS VARCHAR)) LIKE LOWER('%failed%') LIMIT 50
```

Gold SQL:
```sql
SELECT DISTINCT S.DATAFLOWID AS dataflow_id
FROM DIM_CONNECTOR AS S
WHERE S.STATE ILIKE '%loyalty%'
LIMIT 50
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/flowservice/flows",
    "params": {
      "filter": "state eq 'failed'",
      "limit": "50"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/flowservice/flows?filter=state eq 'failed'&limit=50"
]
```

Generated answer: Based on the evidence provided, there are no failed dataflow runs to report. The SQL query returned zero rows, and live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence provided, there are **no failed dataflow runs** to report. The SQL query returned zero rows, indicating no failed runs are recorded in the database. The API response shows available flows but doesn't contain run status information.

### example_014 / SQL_FIRST_API_VERIFY / 0.8435

Query: Show me all entities created by download

Failure category: `DRY_RUN_ONLY`

Recommended fix: Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations.

Generated SQL:
```sql
SELECT DISTINCT C."COLLECTIONID" AS collection_id, C."NAME" AS collection_name, C."CREATEDTIME" AS created_time FROM "dim_collection" AS C WHERE C."CREATEDBY" ILIKE '%download%'
```

Gold SQL:
```sql
SELECT DISTINCT collectionid AS collection_id, name AS collection_name, createdtime AS created_time
FROM dim_collection
WHERE createdby ILIKE '%download%'
LIMIT 20
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/audit/events",
    "params": {
      "limit": "20",
      "property": "action==create"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/audit/events?property=action==create&limit=20"
]
```

Generated answer: Based on the evidence provided, no entities were created by download. The SQL query returned zero rows, and live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence provided, no entities were created by download. The SQL query returned zero results, and the audit log shows only a Segment entity that was created by a user, not by a download process.

### example_014 / TEMPLATE_FIRST / 0.8435

Query: Show me all entities created by download

Failure category: `DRY_RUN_ONLY`

Recommended fix: Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations.

Generated SQL:
```sql
SELECT DISTINCT C."COLLECTIONID" AS collection_id, C."NAME" AS collection_name, C."CREATEDTIME" AS created_time FROM "dim_collection" AS C WHERE C."CREATEDBY" ILIKE '%download%'
```

Gold SQL:
```sql
SELECT DISTINCT collectionid AS collection_id, name AS collection_name, createdtime AS created_time
FROM dim_collection
WHERE createdby ILIKE '%download%'
LIMIT 20
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/audit/events",
    "params": {
      "limit": "20",
      "property": "action==create"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/audit/events?property=action==create&limit=20"
]
```

Generated answer: Based on the evidence provided, no entities were created by download. The SQL query returned zero rows, and live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence provided, no entities were created by download. The SQL query returned zero results, and the audit log shows only a Segment entity that was created by a user, not by a download process.

### example_004 / SQL_ONLY_BASELINE / 0.8486

Query: Show me the IDs of failed dataflow runs

Failure category: `UNKNOWN`

Recommended fix: Inspect trajectory manually and add a targeted deterministic rule only if it generalizes.

Generated SQL:
```sql
SELECT "DATAFLOWNAME", "STATE", "TARGETID", "CONNECTIONSPECID", "NAME" FROM "dim_target" WHERE LOWER(CAST("STATE" AS VARCHAR)) LIKE LOWER('%failed%') LIMIT 50
```

Gold SQL:
```sql
SELECT DISTINCT S.DATAFLOWID AS dataflow_id
FROM DIM_CONNECTOR AS S
WHERE S.STATE ILIKE '%loyalty%'
LIMIT 50
```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/foundation/flowservice/flows?filter=state eq 'failed'&limit=50"
]
```

Generated answer: Based on the evidence provided, there are no failed dataflow runs to report. The SQL query returned zero rows, and API evidence was not requested.

Gold answer: Based on the evidence provided, there are **no failed dataflow runs** to report. The SQL query returned zero rows, indicating no failed runs are recorded in the database. The API response shows available flows but doesn't contain run status information.

### example_005 / SQL_FIRST_API_VERIFY / 0.8629

Query: Export a list of all destinations in the b2b-prod sandbox, sorted by most recently modified, including all columns associated with each destination, and include the 'modified' column for validation.

Failure category: `DRY_RUN_ONLY`

Recommended fix: Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations.

Generated SQL:
```sql
SELECT D."TARGETID" AS target_id, D."DATAFLOWNAME" AS dataflow_name, D."NAME" AS target_name, D."DESCRIPTION", D."STATE", D."CONNECTIONSPECID" AS connection_spec_id, D."CREATEDTIME" AS created_time, D."UPDATEDTIME" AS modified, D."INTERVAL", D."FREQUENCY" FROM "dim_target" AS D ORDER BY D."UPDATEDTIME" DESC LIMIT 50
```

Gold SQL:
```sql
SELECT D.targetId AS target_id,
       D.dataflowName AS dataflow_name,
       D.name AS target_name,
       D.description,
       D.state,
       D.connectionSpecId AS connection_spec_id,
       D.createdTime AS created_time,
       D.updatedTime AS modified,
       D.interval,
       D.frequency
FROM dim_target AS D
ORDER BY D.updatedTime DESC
LIMIT 50
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/flowservice/flows",
    "params": {
      "limit": "50",
      "property": "inheritedAttributes.properties.isDestinationFlow==true",
      "sort": "updatedTime:desc"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/flowservice/flows?limit=50&sort=updatedTime:desc&property=inheritedAttributes.properties.isDestinationFlow==true"
]
```

Generated answer: Based on the evidence provided, 1 destination was found. The most recent is "Activate segments to S3 Feed" (amazon-s3 target) with a modification timestamp of 2026-04-14 16:15:03.000 UTC. Live API evidence is needed to validate the requested sandbox. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence provided, only one destination was found: "Activate segments to S3 Feed" (amazon-s3 target) with a modification timestamp of 2026-04-14 at 16:15:03 UTC. However, this result is from the "external-benchmarking" sandbox rather than the "b2b-prod" sandbox you requested, and the API response is incomplete, so the full export cannot be validated from the evidence shown.

### example_005 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.8631

Query: Export a list of all destinations in the b2b-prod sandbox, sorted by most recently modified, including all columns associated with each destination, and include the 'modified' column for validation.

Failure category: `DRY_RUN_ONLY`

Recommended fix: Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations.

Generated SQL:
```sql
SELECT D."TARGETID" AS target_id, D."DATAFLOWNAME" AS dataflow_name, D."NAME" AS target_name, D."DESCRIPTION", D."STATE", D."CONNECTIONSPECID" AS connection_spec_id, D."CREATEDTIME" AS created_time, D."UPDATEDTIME" AS modified, D."INTERVAL", D."FREQUENCY" FROM "dim_target" AS D ORDER BY D."UPDATEDTIME" DESC LIMIT 50
```

Gold SQL:
```sql
SELECT D.targetId AS target_id,
       D.dataflowName AS dataflow_name,
       D.name AS target_name,
       D.description,
       D.state,
       D.connectionSpecId AS connection_spec_id,
       D.createdTime AS created_time,
       D.updatedTime AS modified,
       D.interval,
       D.frequency
FROM dim_target AS D
ORDER BY D.updatedTime DESC
LIMIT 50
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/flowservice/flows",
    "params": {
      "limit": "50",
      "property": "inheritedAttributes.properties.isDestinationFlow==true",
      "sort": "updatedTime:desc"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/flowservice/flows?limit=50&sort=updatedTime:desc&property=inheritedAttributes.properties.isDestinationFlow==true"
]
```

Generated answer: Based on the evidence provided, 1 destination was found. The most recent is "Activate segments to S3 Feed" (amazon-s3 target) with a modification timestamp of 2026-04-14 16:15:03.000 UTC. Live API evidence is needed to validate the requested sandbox. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence provided, only one destination was found: "Activate segments to S3 Feed" (amazon-s3 target) with a modification timestamp of 2026-04-14 at 16:15:03 UTC. However, this result is from the "external-benchmarking" sandbox rather than the "b2b-prod" sandbox you requested, and the API response is incomplete, so the full export cannot be validated from the evidence shown.

### example_005 / TEMPLATE_FIRST / 0.8632

Query: Export a list of all destinations in the b2b-prod sandbox, sorted by most recently modified, including all columns associated with each destination, and include the 'modified' column for validation.

Failure category: `DRY_RUN_ONLY`

Recommended fix: Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations.

Generated SQL:
```sql
SELECT D."TARGETID" AS target_id, D."DATAFLOWNAME" AS dataflow_name, D."NAME" AS target_name, D."DESCRIPTION", D."STATE", D."CONNECTIONSPECID" AS connection_spec_id, D."CREATEDTIME" AS created_time, D."UPDATEDTIME" AS modified, D."INTERVAL", D."FREQUENCY" FROM "dim_target" AS D ORDER BY D."UPDATEDTIME" DESC LIMIT 50
```

Gold SQL:
```sql
SELECT D.targetId AS target_id,
       D.dataflowName AS dataflow_name,
       D.name AS target_name,
       D.description,
       D.state,
       D.connectionSpecId AS connection_spec_id,
       D.createdTime AS created_time,
       D.updatedTime AS modified,
       D.interval,
       D.frequency
FROM dim_target AS D
ORDER BY D.updatedTime DESC
LIMIT 50
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/flowservice/flows",
    "params": {
      "limit": "50",
      "property": "inheritedAttributes.properties.isDestinationFlow==true",
      "sort": "updatedTime:desc"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/flowservice/flows?limit=50&sort=updatedTime:desc&property=inheritedAttributes.properties.isDestinationFlow==true"
]
```

Generated answer: Based on the evidence provided, 1 destination was found. The most recent is "Activate segments to S3 Feed" (amazon-s3 target) with a modification timestamp of 2026-04-14 16:15:03.000 UTC. Live API evidence is needed to validate the requested sandbox. Live API verification was not executed because Adobe credentials are unavailable.

Gold answer: Based on the evidence provided, only one destination was found: "Activate segments to S3 Feed" (amazon-s3 target) with a modification timestamp of 2026-04-14 at 16:15:03 UTC. However, this result is from the "external-benchmarking" sandbox rather than the "b2b-prod" sandbox you requested, and the API response is incomplete, so the full export cannot be validated from the evidence shown.

### example_000 / SQL_FIRST_API_VERIFY / 0.8650

Query: When was the journey 'Birthday Message' published?

Failure category: `DRY_RUN_ONLY`

Recommended fix: Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations.

Generated SQL:
```sql
SELECT "NAME" AS campaign_name, "LASTDEPLOYEDTIME" AS published_time FROM "dim_campaign" LIMIT 50
```

Gold SQL:
```sql
SELECT name AS campaign_name,
       lastdeployedtime AS published_time
FROM dim_campaign
WHERE name IN ('Birthday Message', 'Gold Tier Welcome Email')
LIMIT 50
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/ajo/journey",
    "params": {
      "filter": "name==Birthday Message"
    }
  }
]
```

Gold API:
```json
[
  "GET /ajo/journey?filter=name==Birthday Message"
]
```

Generated answer: The journey "Birthday Message" has not been published. The database shows a null published_time for this journey, and live API verification was not executed because Adobe credentials are unavailable.

Gold answer: The journey "Birthday Message" has not been published. The database shows a null published_time for this journey, and the Adobe AJO API returns no results for it.

### example_000 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.8654

Query: When was the journey 'Birthday Message' published?

Failure category: `DRY_RUN_ONLY`

Recommended fix: Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations.

Generated SQL:
```sql
SELECT "NAME" AS campaign_name, "LASTDEPLOYEDTIME" AS published_time FROM "dim_campaign" LIMIT 50
```

Gold SQL:
```sql
SELECT name AS campaign_name,
       lastdeployedtime AS published_time
FROM dim_campaign
WHERE name IN ('Birthday Message', 'Gold Tier Welcome Email')
LIMIT 50
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/ajo/journey",
    "params": {
      "filter": "name==Birthday Message"
    }
  }
]
```

Gold API:
```json
[
  "GET /ajo/journey?filter=name==Birthday Message"
]
```

Generated answer: The journey "Birthday Message" has not been published. The database shows a null published_time for this journey, and live API verification was not executed because Adobe credentials are unavailable.

Gold answer: The journey "Birthday Message" has not been published. The database shows a null published_time for this journey, and the Adobe AJO API returns no results for it.

### example_000 / TEMPLATE_FIRST / 0.8654

Query: When was the journey 'Birthday Message' published?

Failure category: `DRY_RUN_ONLY`

Recommended fix: Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations.

Generated SQL:
```sql
SELECT "NAME" AS campaign_name, "LASTDEPLOYEDTIME" AS published_time FROM "dim_campaign" LIMIT 50
```

Gold SQL:
```sql
SELECT name AS campaign_name,
       lastdeployedtime AS published_time
FROM dim_campaign
WHERE name IN ('Birthday Message', 'Gold Tier Welcome Email')
LIMIT 50
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/ajo/journey",
    "params": {
      "filter": "name==Birthday Message"
    }
  }
]
```

Gold API:
```json
[
  "GET /ajo/journey?filter=name==Birthday Message"
]
```

Generated answer: The journey "Birthday Message" has not been published. The database shows a null published_time for this journey, and live API verification was not executed because Adobe credentials are unavailable.

Gold answer: The journey "Birthday Message" has not been published. The database shows a null published_time for this journey, and the Adobe AJO API returns no results for it.

### example_008 / SQL_FIRST_API_VERIFY / 0.8701

Query: show me the field for Person: Birthday Today 001

Failure category: `UNKNOWN`

Recommended fix: Inspect trajectory manually and add a targeted deterministic rule only if it generalizes.

Generated SQL:
```sql
SELECT DISTINCT SP."PROPERTY" AS property_name, S."NAME" AS segment_name FROM "hkg_br_segment_property" AS SP JOIN "dim_segment" AS S ON SP."SEGMENTID" = S."SEGMENTID" WHERE S."NAME" = 'Person: Birthday Today 001' LIMIT 20
```

Gold SQL:
```sql
SELECT DISTINCT aa.property AS property_name, a.name AS segment_name
FROM hkg_br_segment_property aa
JOIN dim_segment a ON aa.segmentid = a.segmentid
WHERE a.name = 'Person: Birthday Today 001'
LIMIT 20
```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/datasets?limit=20&filter=name:SG AND name:non loyalty"
]
```

Generated answer: The field for "Person: Birthday Today 001" is person.birthDate. This is the birth date property from the SQL evidence. This field captures when a person was born and is used to identify birthday-related audiences.

Gold answer: The field for the "Person: Birthday Today 001" segment is the birth date property. This field captures when a person was born and is used to identify individuals celebrating their birthday today.

### example_008 / DETERMINISTIC_ROUTER_SELECTED_METADATA / 0.8704

Query: show me the field for Person: Birthday Today 001

Failure category: `UNKNOWN`

Recommended fix: Inspect trajectory manually and add a targeted deterministic rule only if it generalizes.

Generated SQL:
```sql
SELECT DISTINCT SP."PROPERTY" AS property_name, S."NAME" AS segment_name FROM "hkg_br_segment_property" AS SP JOIN "dim_segment" AS S ON SP."SEGMENTID" = S."SEGMENTID" WHERE S."NAME" = 'Person: Birthday Today 001' LIMIT 20
```

Gold SQL:
```sql
SELECT DISTINCT aa.property AS property_name, a.name AS segment_name
FROM hkg_br_segment_property aa
JOIN dim_segment a ON aa.segmentid = a.segmentid
WHERE a.name = 'Person: Birthday Today 001'
LIMIT 20
```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/datasets?limit=20&filter=name:SG AND name:non loyalty"
]
```

Generated answer: The field for "Person: Birthday Today 001" is person.birthDate. This is the birth date property from the SQL evidence. This field captures when a person was born and is used to identify birthday-related audiences.

Gold answer: The field for the "Person: Birthday Today 001" segment is the birth date property. This field captures when a person was born and is used to identify individuals celebrating their birthday today.

### example_008 / SQL_ONLY_BASELINE / 0.8705

Query: show me the field for Person: Birthday Today 001

Failure category: `UNKNOWN`

Recommended fix: Inspect trajectory manually and add a targeted deterministic rule only if it generalizes.

Generated SQL:
```sql
SELECT DISTINCT SP."PROPERTY" AS property_name, S."NAME" AS segment_name FROM "hkg_br_segment_property" AS SP JOIN "dim_segment" AS S ON SP."SEGMENTID" = S."SEGMENTID" WHERE S."NAME" = 'Person: Birthday Today 001' LIMIT 20
```

Gold SQL:
```sql
SELECT DISTINCT aa.property AS property_name, a.name AS segment_name
FROM hkg_br_segment_property aa
JOIN dim_segment a ON aa.segmentid = a.segmentid
WHERE a.name = 'Person: Birthday Today 001'
LIMIT 20
```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/datasets?limit=20&filter=name:SG AND name:non loyalty"
]
```

Generated answer: The field for "Person: Birthday Today 001" is person.birthDate. This is the birth date property from the SQL evidence. This field captures when a person was born and is used to identify birthday-related audiences.

Gold answer: The field for the "Person: Birthday Today 001" segment is the birth date property. This field captures when a person was born and is used to identify individuals celebrating their birthday today.

### example_008 / TEMPLATE_FIRST / 0.8705

Query: show me the field for Person: Birthday Today 001

Failure category: `UNKNOWN`

Recommended fix: Inspect trajectory manually and add a targeted deterministic rule only if it generalizes.

Generated SQL:
```sql
SELECT DISTINCT SP."PROPERTY" AS property_name, S."NAME" AS segment_name FROM "hkg_br_segment_property" AS SP JOIN "dim_segment" AS S ON SP."SEGMENTID" = S."SEGMENTID" WHERE S."NAME" = 'Person: Birthday Today 001' LIMIT 20
```

Gold SQL:
```sql
SELECT DISTINCT aa.property AS property_name, a.name AS segment_name
FROM hkg_br_segment_property aa
JOIN dim_segment a ON aa.segmentid = a.segmentid
WHERE a.name = 'Person: Birthday Today 001'
LIMIT 20
```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /data/foundation/catalog/datasets?limit=20&filter=name:SG AND name:non loyalty"
]
```

Generated answer: The field for "Person: Birthday Today 001" is person.birthDate. This is the birth date property from the SQL evidence. This field captures when a person was born and is used to identify birthday-related audiences.

Gold answer: The field for the "Person: Birthday Today 001" segment is the birth date property. This field captures when a person was born and is used to identify individuals celebrating their birthday today.

### example_000 / SQL_ONLY_BASELINE / 0.9023

Query: When was the journey 'Birthday Message' published?

Failure category: `UNKNOWN`

Recommended fix: Inspect trajectory manually and add a targeted deterministic rule only if it generalizes.

Generated SQL:
```sql
SELECT "NAME" AS campaign_name, "LASTDEPLOYEDTIME" AS published_time FROM "dim_campaign" LIMIT 50
```

Gold SQL:
```sql
SELECT name AS campaign_name,
       lastdeployedtime AS published_time
FROM dim_campaign
WHERE name IN ('Birthday Message', 'Gold Tier Welcome Email')
LIMIT 50
```

Generated API:
```json
[]
```

Gold API:
```json
[
  "GET /ajo/journey?filter=name==Birthday Message"
]
```

Generated answer: The journey "Birthday Message" has not been published. The database shows a null published_time for this journey, and API evidence was not requested.

Gold answer: The journey "Birthday Message" has not been published. The database shows a null published_time for this journey, and the Adobe AJO API returns no results for it.

### example_010 / SQL_FIRST_API_VERIFY / 0.9215

Query: Count the number of XDM Experience Event schemas that are enabled for profile.

Failure category: `DRY_RUN_ONLY`

Recommended fix: Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations.

Generated SQL:
```sql
SELECT COUNT(DISTINCT B."BLUEPRINTID") AS num_experience_event_profile_enabled_blueprints FROM "dim_blueprint" AS B WHERE LOWER(B."CLASS") LIKE LOWER('%download%') AND B."ISPROFILEENABLED" = TRUE
```

Gold SQL:
```sql
SELECT COUNT(DISTINCT S.BLUEPRINTID) AS num_experience_event_profile_enabled_blueprints
FROM DIM_BLUEPRINT AS S
WHERE LOWER(S.CLASS) LIKE LOWER('%download%')
  AND S.ISPROFILEENABLED = TRUE
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/schemaregistry/tenant/schemas",
    "params": {
      "filter": "class==ExperienceEvent;isProfileEnabled==true",
      "limit": "25"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/schemaregistry/tenant/schemas?limit=25&filter=class==ExperienceEvent;isProfileEnabled==true"
]
```

Generated answer: Based on the SQL query result, there are 0 XDM Experience Event schemas enabled for profile in your environment.

Gold answer: Based on the SQL query result, there are **0 XDM Experience Event schemas enabled for profile** in your environment.

### example_010 / TEMPLATE_FIRST / 0.9218

Query: Count the number of XDM Experience Event schemas that are enabled for profile.

Failure category: `DRY_RUN_ONLY`

Recommended fix: Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations.

Generated SQL:
```sql
SELECT COUNT(DISTINCT B."BLUEPRINTID") AS num_experience_event_profile_enabled_blueprints FROM "dim_blueprint" AS B WHERE LOWER(B."CLASS") LIKE LOWER('%download%') AND B."ISPROFILEENABLED" = TRUE
```

Gold SQL:
```sql
SELECT COUNT(DISTINCT S.BLUEPRINTID) AS num_experience_event_profile_enabled_blueprints
FROM DIM_BLUEPRINT AS S
WHERE LOWER(S.CLASS) LIKE LOWER('%download%')
  AND S.ISPROFILEENABLED = TRUE
```

Generated API:
```json
[
  {
    "method": "GET",
    "path": "/data/foundation/schemaregistry/tenant/schemas",
    "params": {
      "filter": "class==ExperienceEvent;isProfileEnabled==true",
      "limit": "25"
    }
  }
]
```

Gold API:
```json
[
  "GET /data/foundation/schemaregistry/tenant/schemas?limit=25&filter=class==ExperienceEvent;isProfileEnabled==true"
]
```

Generated answer: Based on the SQL query result, there are 0 XDM Experience Event schemas enabled for profile in your environment.

Gold answer: Based on the SQL query result, there are **0 XDM Experience Event schemas enabled for profile** in your environment.
