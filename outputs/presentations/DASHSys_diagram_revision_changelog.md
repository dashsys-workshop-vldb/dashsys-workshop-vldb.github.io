# DASHSys Progress Deck Diagram Revision Changelog

## What Changed

- Replaced simple block-to-block workflow diagrams with generated Graphviz DOT diagrams.
- Kept Mermaid `.mmd` source companions for each diagram, but Graphviz DOT is now the rendered layout source of truth.
- Added richer object/dataflow diagrams that show:
  - component names
  - important fields inside each data object
  - transition labels on arrows
  - decisions such as `API_REQUIRED`, `API_OPTIONAL`, and `API_SKIP`
  - artifacts written to `metadata.json`, `filled_system_prompt.txt`, and `trajectory.json`

## Slides Rebuilt

- Technique slides 6-26 now use data-structure, decision-tree, scoring-table, state-transition, or cache-hierarchy diagrams instead of simple process chains.
- The integrated workflow was split into two readable slides:
  - Planning dataflow: `RawQuery` through `ValidatedPlan`
  - Evidence/answer dataflow: `ValidatedPlan` through final artifacts
- The Birthday Message trace now shows structured query tokens, SQL result, API dry-run plan, answer slots, verifier decision, and trajectory output.
- The memory/cache slide now shows L1/L2 hit-miss decisions, freshness checks, DuckDB rebuild path, Adobe API boundary, and artifact storage.

## How Overflow Was Prevented

- Diagram layout is generated as high-resolution PNG/SVG assets rather than dozens of fragile PowerPoint text boxes.
- Long fields are wrapped inside DOT object boxes before rendering.
- Dense integrated workflow content was split into two slides instead of shrinking text.
- PowerPoint slides now reserve larger diagram frames and keep explanation boxes separate from diagram images.

## Generated Diagram Assets

- Source companions: `diagrams/*.mmd`
- Graphviz sources: `diagrams/*.dot`
- Editable vector exports: `diagrams/*.svg`
- PPT image exports: `diagrams/*.png`
- Diagram mapping and regeneration notes: `diagrams/README.md`
