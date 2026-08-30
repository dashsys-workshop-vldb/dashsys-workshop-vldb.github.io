# Visualization Summary

- Primary example: `example_011`
- Raw prompt: How many schemas do I have?
- Main storyboard: `outputs/visualizations/sql_prompt_storyboard_primary.md`
- End-to-end system dataflow: `outputs/visualizations/end_to_end_system_dataflow.html`
- Single SVG project overview: `outputs/visualizations/full_project_dataflow.svg`
- Secondary reference: example_031 remains a secondary API/dry-run bottleneck reference only.

## Prompt To SQL Mapping

- `schemas` → `dim_blueprint`
- `how many` → `COUNT DISTINCT`
- `BLUEPRINTID` → `blueprint_count = 74`
