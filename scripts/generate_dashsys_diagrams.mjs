#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const DIAGRAM_DIR = path.join(ROOT, "diagrams");

const COLORS = {
  planning: { fill: "#EFE7FF", stroke: "#6D5BD0" },
  sql: { fill: "#EAF3FF", stroke: "#1769AA" },
  api: { fill: "#FFF3E0", stroke: "#D97706" },
  validation: { fill: "#E8F7ED", stroke: "#1A7F52" },
  artifact: { fill: "#F2F4F7", stroke: "#687386" },
  evidence: { fill: "#E8FAF8", stroke: "#0B8F8A" },
};

const TECHNIQUES = [
  {
    id: "technique_01_sql_api_templates",
    title: "Schema-guided planning: SQL/API templates",
    subtitle: "Templates constrain SQL joins and API params to validated schema/catalog choices.",
    mechanism: "SQL/API templates",
    technique: "Schema-guided planning / constrained generation",
    modules: "sql_templates.py, api_templates.py, planner.py",
    benefit: "Higher SQL/API correctness",
    theme: "planning",
    steps: ["Query", "Identify family", "Choose SQL/API template", "Fill schema/API params", "Validate", "Structured plan"],
  },
  {
    id: "technique_02_failure_analysis",
    title: "Error-driven optimization: failure_analysis",
    subtitle: "Evaluation failures are ranked and converted into reusable fixes.",
    mechanism: "failure_analysis",
    technique: "Benchmark-guided debugging / error-driven optimization",
    modules: "failure_analysis.py, generate_failure_analysis.py",
    benefit: "Targeted fixes; less random iteration",
    theme: "artifact",
    steps: ["run_dev_eval", "Scores", "failure_analysis", "Rank low-score cases", "Patch reusable rule", "Regression test"],
  },
  {
    id: "technique_03_answer_templates",
    title: "Structured generation: answer_templates",
    subtitle: "Domain answer families render tool evidence with consistent concise wording.",
    mechanism: "answer_templates",
    technique: "Structured generation / answer templating",
    modules: "answer_templates.py",
    benefit: "More stable responses",
    theme: "validation",
    steps: ["Tool evidence", "Answer family", "Template selection", "Fill fields", "Concise answer"],
  },
  {
    id: "technique_04_evidence_policy",
    title: "Conditional execution: evidence_policy",
    subtitle: "The planner predicts whether API evidence is required, optional, or skippable.",
    mechanism: "evidence_policy",
    technique: "Branch prediction / conditional execution",
    modules: "evidence_policy.py",
    benefit: "Better efficiency",
    theme: "planning",
    steps: ["Query family", "API_REQUIRED / OPTIONAL / SKIP", "Annotate plan", "Reduce calls"],
  },
  {
    id: "technique_05_call_budget",
    title: "Resource scheduling: call_budget",
    subtitle: "Each strategy/family receives a bounded SQL/API call budget.",
    mechanism: "call_budget",
    technique: "Resource scheduling / execution budget",
    modules: "call_budget.py",
    benefit: "Controls tool calls and tokens",
    theme: "planning",
    steps: ["Draft plan", "Count SQL/API calls", "Apply family budget", "Trim optional calls", "Bounded plan"],
  },
  {
    id: "technique_06_evidence_bus",
    title: "Operand forwarding: EvidenceBus",
    subtitle: "Structured evidence is forwarded directly instead of rediscovered from text.",
    mechanism: "EvidenceBus",
    technique: "Operand forwarding / bypassing",
    modules: "evidence_bus.py, executor.py",
    benefit: "Better correctness; fewer repeated decisions",
    theme: "evidence",
    steps: ["SQL/API results", "Extract IDs/names/counts/timestamps", "EvidenceBus", "API params / answer slots"],
  },
  {
    id: "technique_07_query_analysis",
    title: "Shared decode: QueryAnalysis",
    subtitle: "One query analysis object shares route, family, templates, and confidence.",
    mechanism: "QueryAnalysis",
    technique: "Shared decode / branch prediction",
    modules: "query_analysis.py",
    benefit: "Less repeated computation",
    theme: "planning",
    steps: ["Normalized query + tokens", "Route/domain/family", "SQL/API templates", "Confidence", "Shared analysis object"],
  },
  {
    id: "technique_08_lookup_path_predictor",
    title: "Lookup-path prediction: LookupPathPredictor",
    subtitle: "Reusable lookup paths guide table, join, endpoint, and ID selection.",
    mechanism: "LookupPathPredictor",
    technique: "Lookup-path prediction / TLB-style path guidance",
    modules: "lookup_paths.py",
    benefit: "Better schema/API relevance",
    theme: "planning",
    steps: ["Query family", "Choose lookup path", "Tables + joins + IDs", "Guide metadata/API selection"],
  },
  {
    id: "technique_09_plan_optimizer",
    title: "Compiler optimization: PlanOptimizer",
    subtitle: "Draft plans are simplified before validation and execution.",
    mechanism: "PlanOptimizer",
    technique: "Compiler optimization",
    modules: "plan_optimizer.py",
    benefit: "Fewer wasted calls",
    theme: "planning",
    steps: ["Draft plan", "Deduplicate", "Remove API_SKIP", "Drop placeholders", "Enforce budget", "Optimized plan"],
  },
  {
    id: "technique_10_cache_hierarchy",
    title: "Multi-level caching: cache.py",
    subtitle: "Fresh schema, join, endpoint, and pattern artifacts are reused across queries.",
    mechanism: "cache.py",
    technique: "Multi-level caching",
    modules: "cache.py",
    benefit: "Lower preprocessing/runtime",
    theme: "artifact",
    steps: ["Query", "L1 in-memory cache", "L2 disk cache", "L3 DuckDB snapshot", "L4 Adobe API"],
  },
  {
    id: "technique_11_context_cards",
    title: "Context packing: context_cards",
    subtitle: "Family-specific cards pass only the context likely needed for a query.",
    mechanism: "context_cards",
    technique: "Context packing / huge-page-style compaction",
    modules: "context_cards.py, metadata_selector.py",
    benefit: "Lower prompt tokens",
    theme: "artifact",
    steps: ["Query family", "Choose context card", "Pack tables/columns/APIs", "Compact metadata"],
  },
  {
    id: "technique_12_query_normalizer",
    title: "Data cleaning: query_normalizer",
    subtitle: "Surface wording is normalized for matching while preserving original query text.",
    mechanism: "query_normalizer",
    technique: "Data cleaning / normalization",
    modules: "query_normalizer.py",
    benefit: "More robust matching",
    theme: "planning",
    steps: ["Raw query", "Clean whitespace", "Normalize quotes/hyphens", "Normalize synonyms/plurals", "Normalized query"],
  },
  {
    id: "technique_13_query_tokens",
    title: "Tokenization and entity extraction: query_tokens",
    subtitle: "Important entities, IDs, dates, metrics, and statuses become structured tokens.",
    mechanism: "query_tokens",
    technique: "Tokenization / entity extraction",
    modules: "query_tokens.py",
    benefit: "Better routing and template fill",
    theme: "planning",
    steps: ["Normalized query", "Extract entities", "Extract IDs", "Extract dates/metrics/status", "Structured query tokens"],
  },
  {
    id: "technique_14_relevance_scorer",
    title: "Attention-style selection: relevance_scorer",
    subtitle: "Schema/API candidates are ranked by deterministic overlap and family weights.",
    mechanism: "relevance_scorer",
    technique: "Attention-style relevance ranking",
    modules: "relevance_scorer.py",
    benefit: "Smaller metadata; better relevance",
    theme: "planning",
    steps: ["Query tokens", "Score tables/columns/APIs", "Rank candidates", "Select top context"],
  },
  {
    id: "technique_15_plan_ensemble",
    title: "Ensemble selection: plan_ensemble",
    subtitle: "Candidate plans are scored cheaply before exactly one plan executes.",
    mechanism: "plan_ensemble",
    technique: "Ensemble selection / pre-execution reranking",
    modules: "plan_ensemble.py",
    benefit: "Better plan choice without more tool calls",
    theme: "planning",
    steps: ["Candidate plans", "Validation score", "Relevance score", "Cost score", "Choose one plan", "Execute one plan only"],
  },
  {
    id: "technique_16_answer_slots",
    title: "Evidence slot extraction: answer_slots",
    subtitle: "SQL/API evidence is converted into typed slots before final answer synthesis.",
    mechanism: "answer_slots",
    technique: "Evidence slot extraction / slot filling",
    modules: "answer_slots.py",
    benefit: "Clean structured facts for answering",
    theme: "validation",
    steps: ["Tool results", "Extract entity/count/status/time/metric", "Structured evidence slots"],
  },
  {
    id: "technique_17_answer_intent",
    title: "Intent-aware response shaping: answer_intent",
    subtitle: "The answer starts with the shape implied by the question intent.",
    mechanism: "answer_intent",
    technique: "Intent-aware response shaping",
    modules: "answer_intent.py",
    benefit: "Better answer relevance",
    theme: "validation",
    steps: ["Question", "Classify COUNT/LIST/WHEN/STATUS/DETAIL", "Choose answer shape"],
  },
  {
    id: "technique_18_answer_claims",
    title: "Claim decomposition: answer_claims",
    subtitle: "Candidate answer text is split into factual claims before verification.",
    mechanism: "answer_claims",
    technique: "Claim decomposition",
    modules: "answer_claims.py",
    benefit: "Supports grounded checking",
    theme: "validation",
    steps: ["Candidate answer", "Number/entity/time/status/API claims", "Verification units"],
  },
  {
    id: "technique_19_answer_verifier",
    title: "Groundedness checking: answer_verifier",
    subtitle: "Answer claims are checked against slots and tool evidence.",
    mechanism: "answer_verifier",
    technique: "Claim verification / groundedness checking",
    modules: "answer_verifier.py",
    benefit: "Reduces unsupported claims",
    theme: "validation",
    steps: ["Claims + evidence slots", "Support check", "Dry-run caveat", "Discrepancy check", "Verified answer"],
  },
  {
    id: "technique_20_answer_reranker",
    title: "Deterministic reranking: answer_reranker",
    subtitle: "Same-evidence candidate answers are ranked without extra tool or LLM calls.",
    mechanism: "answer_reranker",
    technique: "Deterministic reranking",
    modules: "answer_reranker.py",
    benefit: "Better answer correctness",
    theme: "validation",
    steps: ["Candidate answers", "Verifier results", "Intent/style score", "Choose best answer"],
  },
  {
    id: "technique_21_answer_diagnostics",
    title: "Error observability: answer_diagnostics",
    subtitle: "Compact answer diagnostics are logged for future failure analysis.",
    mechanism: "answer_diagnostics",
    technique: "Error analysis / observability",
    modules: "answer_diagnostics.py, trajectory.py",
    benefit: "Debuggable answer failures",
    theme: "artifact",
    steps: ["Final answer", "answer_family/intent", "Verifier status", "unsupported_count", "Trajectory diagnostics"],
  },
];

const EXTRA_DIAGRAMS = [
  {
    id: "whole_project_planning_dataflow",
    title: "Whole Project Workflow: Planning Dataflow",
    theme: "planning",
  },
  {
    id: "whole_project_evidence_answer_dataflow",
    title: "Whole Project Workflow: Evidence and Answer Dataflow",
    theme: "evidence",
  },
  {
    id: "whole_project_workflow",
    title: "Whole Project Workflow",
    theme: "planning",
    groups: [
      { name: "Query Frontend", theme: "planning", steps: ["Raw Query", "Query Normalization", "Token Extraction", "Routing + QueryAnalysis"] },
      { name: "Planning Control Plane", theme: "planning", steps: ["Metadata Selection", "Planning", "Evidence Policy + Budget", "Plan Optimizer", "Validators"] },
      { name: "Execution / Evidence Plane", theme: "evidence", steps: ["SQL/API Execution", "EvidenceBus", "Live Parser", "Answer Slots"] },
      { name: "Answer / Artifact Plane", theme: "validation", steps: ["Claim Verifier + Reranker", "Final Answer", "metadata/prompt/trajectory", "Evaluation + Packaging"] },
    ],
  },
  {
    id: "concrete_birthday_message",
    title: "Concrete Dry-Run Example: Birthday Message",
    theme: "planning",
    direction: "TD",
    steps: [
      "Question: When was Birthday Message published?",
      "Normalize + extract entity",
      "Route: JOURNEY_CAMPAIGN + STATUS",
      "SQL: dim_campaign.lastdeployedtime",
      "SQL result: null",
      "API dry-run: GET /ajo/journey?filter=name==Birthday Message",
      "Gold API comparison",
      "Verifier requires dry-run caveat",
      "Final answer: not published; live API not executed",
    ],
  },
  {
    id: "memory_cache_hierarchy",
    title: "Memory and Cache Hierarchy",
    theme: "artifact",
    direction: "TD",
    steps: [
      "L1 In-memory cache",
      "L2 Disk cache",
      "L3 DuckDB / DBSnapshot",
      "L4 Adobe REST API",
      "Artifact Store",
    ],
  },
];

function q(text) {
  return String(text).replace(/"/g, '\\"');
}

function mmdText(text) {
  return String(text).replace(/"/g, "&quot;").replace(/\n/g, "<br/>");
}

function mermaidSourceForDiagram(spec, diagram) {
  const lines = [
    "%% Auto-generated by scripts/generate_dashsys_diagrams.mjs",
    "%% Source companion for the exported Graphviz diagram.",
    "flowchart LR",
  ];
  (diagram.nodes || []).forEach((node) => {
    lines.push(`  ${node.id}["${mmdText([node.title, ...(node.fields || [])].join("\n"))}"]`);
  });
  (diagram.edges || []).forEach((edge) => {
    lines.push(`  ${edge.from} -->|${mmdText(edge.label || "")}| ${edge.to}`);
  });
  lines.push("");
  lines.push("  classDef planning fill:#EFE7FF,stroke:#6D5BD0,color:#111;");
  lines.push("  classDef sql fill:#EAF3FF,stroke:#1769AA,color:#111;");
  lines.push("  classDef api fill:#FFF3E0,stroke:#D97706,color:#111;");
  lines.push("  classDef validation fill:#E8F7ED,stroke:#1A7F52,color:#111;");
  lines.push("  classDef artifact fill:#F2F4F7,stroke:#687386,color:#111;");
  lines.push("  classDef evidence fill:#E8FAF8,stroke:#0B8F8A,color:#111;");
  for (const theme of Object.keys(COLORS)) {
    const ids = (diagram.nodes || []).filter((node) => (node.theme || spec.theme) === theme).map((node) => node.id);
    if (ids.length) lines.push(`  class ${ids.join(",")} ${theme};`);
  }
  return `${lines.join("\n")}\n`;
}

function wrap(text, max = 36) {
  const words = String(text).split(/\s+/);
  const out = [];
  let current = "";
  for (const word of words) {
    if ((current ? `${current} ${word}` : word).length > max && current) {
      out.push(current);
      current = word;
    } else {
      current = current ? `${current} ${word}` : word;
    }
  }
  if (current) out.push(current);
  return out.join("\\n");
}

function nodeLabel(title, fields = []) {
  const body = [wrap(title, 28), ...fields.map((field) => `• ${wrap(field, 30)}`)].join("\\n");
  return q(body);
}

function nodeLine(node, defaultTheme = "planning") {
  const theme = COLORS[node.theme || defaultTheme] || COLORS.planning;
  const shape = node.shape || "rect";
  const extra = shape === "diamond" ? ", width=1.95, height=1.00" : "";
  return `  ${node.id} [label="${nodeLabel(node.title, node.fields)}", shape=${shape}, fillcolor="${theme.fill}", color="${theme.stroke}"${extra}];`;
}

function edgeLine(edge) {
  const label = edge.label ? ` [label="${q(wrap(edge.label, 30))}"]` : "";
  return `  ${edge.from} -> ${edge.to}${label};`;
}

function dotHeader(direction = "LR") {
  return [
    "digraph G {",
    `  graph [rankdir=${direction}, bgcolor="white", pad=0.10, nodesep=0.48, ranksep=0.62, splines=ortho];`,
    '  node [shape=rect, style="rounded,filled", fontname="Aptos", fontsize=19, margin="0.16,0.10", penwidth=2.0];',
    '  edge [fontname="Aptos", fontsize=12.5, color="#687386", fontcolor="#425466", penwidth=1.7, arrowsize=0.72];',
  ];
}

function dotSourceFromDiagram(spec, diagram) {
  const lines = dotHeader(diagram.direction || "LR");
  (diagram.clusters || []).forEach((cluster, i) => {
    const color = COLORS[cluster.theme || spec.theme] || COLORS.planning;
    lines.push(`  subgraph cluster_${i} {`);
    lines.push(`    label="${q(cluster.label)}"; labelloc=t; fontsize=22; fontname="Aptos";`);
    lines.push(`    color="${color.stroke}"; fillcolor="${color.fill}"; style="rounded,filled";`);
    (cluster.nodeIds || []).forEach((id) => {
      const node = diagram.nodes.find((item) => item.id === id);
      lines.push(`  ${nodeLine(node, cluster.theme || spec.theme).trim()}`);
    });
    lines.push("  }");
  });
  const clustered = new Set((diagram.clusters || []).flatMap((cluster) => cluster.nodeIds || []));
  (diagram.nodes || []).filter((node) => !clustered.has(node.id)).forEach((node) => lines.push(nodeLine(node, spec.theme)));
  (diagram.ranks || []).forEach((rank) => lines.push(`  { rank=same; ${rank.join("; ")}; }`));
  (diagram.edges || []).forEach((edge) => lines.push(edgeLine(edge)));
  lines.push("}");
  return `${lines.join("\n")}\n`;
}

function n(id, title, fields = [], theme = "planning", shape = "rect") {
  return { id, title, fields, theme, shape };
}

function e(from, to, label = "") {
  return { from, to, label };
}

function genericDiagram(spec) {
  const nodes = (spec.steps || []).map((step, i) => n(`n${i}`, step, [], spec.theme));
  return { direction: spec.direction === "TD" ? "TB" : "LR", nodes, edges: nodes.slice(1).map((node, i) => e(nodes[i].id, node.id, "next")) };
}

const DETAILED_DIAGRAMS = {
  technique_01_sql_api_templates: {
    direction: "LR",
    nodes: [
      n("qa", "QueryAnalysis", ["domain_type", "answer_family", "sql_template_id", "api_template_ids"], "planning"),
      n("tpl", "Template Binder", ["choose by family", "bind entities / IDs", "use known schema + catalog"], "planning"),
      n("guard", "Validators", ["table + column exist", "endpoint + params allowed"], "validation"),
      n("plan", "DraftPlan", ["sql_steps[]", "api_steps[]", "dependencies[]"], "artifact"),
    ],
    edges: [e("qa", "tpl", "template selected by family"), e("tpl", "guard", "schema/catalog binding"), e("guard", "plan", "validated step emitted")],
  },
  technique_02_failure_analysis: {
    direction: "LR",
    nodes: [
      n("eval", "EvalResults", ["sql_score", "api_score", "answer_score", "final_score", "tool_calls", "tokens"], "artifact"),
      n("rank", "FailureAnalysis", ["lowest_examples[]", "failure_category", "recommended_fix"], "artifact"),
      n("patch", "Reusable Fix", ["rule/template update", "not exact public answer"], "planning"),
      n("tests", "RegressionTests", ["test_name", "expected_behavior"], "validation"),
    ],
    edges: [e("eval", "rank", "rank low-score cases"), e("rank", "patch", "categorize + inspect"), e("patch", "tests", "lock behavior")],
  },
  technique_03_answer_templates: {
    direction: "LR",
    nodes: [
      n("tool", "ToolEvidence", ["sql rows", "api payloads", "dry_run/errors"], "evidence"),
      n("family", "Answer Family", ["count", "list", "published status", "tag detail", "observability"], "planning"),
      n("fill", "Template Fill", ["insert supported fields", "keep caveats"], "validation"),
      n("answer", "CandidateAnswer", ["concise text", "evidence-grounded"], "artifact"),
    ],
    edges: [e("tool", "family", "classify answer shape"), e("family", "fill", "choose template"), e("fill", "answer", "render from evidence")],
  },
  technique_04_evidence_policy: {
    direction: "TB",
    nodes: [
      n("input", "QueryAnalysis + DraftPlan", ["family", "route_type", "sql evidence possible", "api templates"], "planning"),
      n("d1", "API-only or live data?", [], "planning", "diamond"),
      n("required", "ApiNeedDecision", ["mode = API_REQUIRED", "reason", "max_api_calls"], "api"),
      n("d2", "Can SQL fully answer?", [], "planning", "diamond"),
      n("skip", "ApiNeedDecision", ["mode = API_SKIP", "reason = SQL enough"], "validation"),
      n("optional", "ApiNeedDecision", ["mode = API_OPTIONAL", "cap optional API calls"], "planning"),
    ],
    edges: [e("input", "d1", "inspect query family"), e("d1", "required", "yes"), e("d1", "d2", "no"), e("d2", "skip", "yes"), e("d2", "optional", "API may verify")],
  },
  technique_05_call_budget: {
    direction: "LR",
    nodes: [
      n("draft", "DraftPlan", ["sql_steps = n", "api_steps = m", "optional flags"], "artifact"),
      n("rule", "BudgetRule", ["max_sql", "max_api", "max_total", "family exceptions"], "planning"),
      n("apply", "Budget Applier", ["trim optional first", "preserve required", "warn on drops"], "planning"),
      n("budgeted", "BudgetedPlan", ["kept_steps[]", "trimmed_steps[]", "reason"], "artifact"),
    ],
    edges: [e("draft", "apply", "count calls"), e("rule", "apply", "limits by family"), e("apply", "budgeted", "bounded plan")],
  },
  technique_06_evidence_bus: {
    direction: "LR",
    nodes: [
      n("results", "ToolResults", ["sql_rows[]", "api_payloads[]", "dry_run_flags[]", "errors[]"], "evidence"),
      n("bus", "EvidenceBus", ["entity_ids{destination_id,schema_id,campaign_id,tag_id}", "names[]", "counts{}", "timestamps[]", "statuses[]", "sql_rows_preview[]", "api_items_preview[]"], "evidence"),
      n("api", "API Templates", ["forwarded IDs", "resolved params"], "api"),
      n("slots", "AnswerSlots", ["structured facts", "dry_run/discrepancy flags"], "validation"),
      n("traj", "trajectory.json", ["compact evidence", "tool previews"], "artifact"),
    ],
    edges: [e("results", "bus", "extract exact evidence"), e("bus", "api", "forward IDs"), e("bus", "slots", "facts for answer"), e("bus", "traj", "log preview")],
  },
  technique_07_query_analysis: {
    direction: "LR",
    nodes: [
      n("input", "NormalizedQuery + QueryTokens", ["normalized_text", "entities[]", "ids[]", "metrics[]"], "planning"),
      n("internal", "QueryAnalysis Internals", ["route classifier", "domain classifier", "answer family", "template selector", "confidence scoring"], "planning"),
      n("qa", "QueryAnalysis", ["route_type", "domain_type", "answer_family", "sql_template", "api_templates", "confidence"], "artifact"),
      n("users", "Shared By", ["MetadataSelector", "Planner", "EvidencePolicy", "Reporting"], "validation"),
    ],
    edges: [e("input", "internal", "decode once"), e("internal", "qa", "analysis object"), e("qa", "users", "reuse same decision")],
  },
  technique_08_lookup_path_predictor: {
    direction: "LR",
    nodes: [
      n("family", "query_family", ["segment_destination"], "planning"),
      n("path", "LookupPath", ["tables: dim_segment, bridge, dim_target", "joins: segment_id -> target_id", "required_ids: destination_id", "api_family: audience_by_destination"], "planning"),
      n("meta", "Metadata Selection", ["relevant tables", "join hints", "API candidates"], "artifact"),
      n("planner", "Planner/API Params", ["choose join path", "resolve required IDs"], "api"),
    ],
    edges: [e("family", "path", "map family to path"), e("path", "meta", "guide context"), e("path", "planner", "guide plan fill")],
  },
  technique_09_plan_optimizer: {
    direction: "LR",
    nodes: [
      n("before", "DraftPlan Before", ["steps = [SQL1, API1, API1_dup, API_<id>]", "api_skip flags", "placeholders"], "artifact"),
      n("opt", "PlanOptimizer", ["remove duplicates", "remove API_SKIP", "drop placeholders", "enforce budget"], "planning"),
      n("after", "OptimizedPlan After", ["steps = [SQL1, API1]", "optimizer_actions[]", "unresolved_placeholders[]"], "validation"),
    ],
    edges: [e("before", "opt", "state transition"), e("opt", "after", "cleaned + bounded")],
  },
  technique_10_cache_hierarchy: {
    direction: "LR",
    nodes: [
      n("request", "Query Request", ["query_id", "data mtimes", "pattern version"], "planning"),
      n("l1", "L1 Memory Cache", ["query analysis", "template choice"], "artifact"),
      n("hit1", "L1 hit?", [], "artifact", "diamond"),
      n("l2", "L2 Disk Cache", ["schema_summary.json", "join_graph.json", "endpoint_catalog.json", "gold patterns"], "artifact"),
      n("hit2", "L2 fresh?", [], "artifact", "diamond"),
      n("rebuild", "Rebuild", ["DBSnapshot file mtimes", "data.json mtime", "save artifacts"], "sql"),
      n("return", "Cached Context", ["analysis", "schema/API artifacts"], "validation"),
    ],
    edges: [e("request", "l1", "lookup key"), e("l1", "hit1", "check memory"), e("hit1", "return", "yes"), e("hit1", "l2", "no"), e("l2", "hit2", "freshness check"), e("hit2", "return", "yes"), e("hit2", "rebuild", "no"), e("rebuild", "return", "save + reuse")],
  },
  technique_11_context_cards: {
    direction: "LR",
    nodes: [
      n("family", "query_family", ["journey", "tag", "schema_dataset", "destination"], "planning"),
      n("card", "ContextCard", ["family", "tables[]", "columns[]", "joins[]", "apis[]", "answer_policy"], "artifact"),
      n("meta", "SelectedMetadata", ["compact schema", "top APIs", "join hints", "context_card"], "artifact"),
    ],
    edges: [e("family", "card", "choose family card"), e("card", "meta", "replace broad schema")],
  },
  technique_12_query_normalizer: {
    direction: "LR",
    nodes: [
      n("raw", "RawQuery", ["original text", "smart quotes", "data-flow", "extra spaces"], "planning"),
      n("norm", "Normalizer", ["clean whitespace", "normalize quotes/hyphens", "normalize synonyms/plurals"], "planning"),
      n("out", "NormalizedQuery", ["original", "normalized", "matching_text", "rewrites[]"], "artifact"),
    ],
    edges: [e("raw", "norm", "preserve original"), e("norm", "out", "clean text for matching")],
  },
  technique_13_query_tokens: {
    direction: "LR",
    nodes: [
      n("norm", "NormalizedQuery", ["normalized_text", "original_text"], "planning"),
      n("tokens", "QueryTokens", ["quoted_entities: [Birthday Message]", "ids[]", "dates[]", "metrics[]", "statuses: [published]"], "artifact"),
      n("uses", "Used By", ["Router", "templates", "relevance_scorer"], "validation"),
    ],
    edges: [e("norm", "tokens", "extract entities / IDs / dates"), e("tokens", "uses", "structured tokens")],
  },
  technique_14_relevance_scorer: {
    direction: "LR",
    nodes: [
      n("tokens", "QueryTokens", ["domain tokens", "entities", "metrics", "statuses"], "planning"),
      n("score", "Scoring Table", ["dim_campaign: 0.92", "/ajo/journey: 0.88", "dim_target: 0.21"], "artifact"),
      n("top", "Top Context", ["tables[]", "columns[]", "join_hints[]", "api_candidates[]"], "validation"),
    ],
    edges: [e("tokens", "score", "token/family overlap"), e("score", "top", "keep high relevance")],
  },
  technique_15_plan_ensemble: {
    direction: "LR",
    nodes: [
      n("cands", "Candidate Plans", ["A fast path", "B SQL template", "C lookup path", "D generic"], "planning"),
      n("scores", "Pre-execution Scores", ["validation", "relevance", "cost", "placeholder risk"], "artifact"),
      n("selected", "SelectedPlan", ["highest score", "unresolved = 0", "estimated low cost"], "validation"),
      n("execute", "Executor", ["execute one plan only"], "sql"),
    ],
    edges: [e("cands", "scores", "score before execution"), e("scores", "selected", "pick winner"), e("selected", "execute", "single plan")],
  },
  technique_16_answer_slots: {
    direction: "LR",
    nodes: [
      n("results", "ToolResults", ["rows: [{name, lastdeployedtime:null}]", "api dry_run=true"], "evidence"),
      n("slots", "AnswerSlots", ["entity_name", "entity_id", "count", "status", "timestamp", "metric_value", "dry_run", "discrepancy"], "validation"),
      n("answer", "Answer Source", ["only supported values", "safe caveats"], "artifact"),
    ],
    edges: [e("results", "slots", "raw -> structured"), e("slots", "answer", "source of truth")],
  },
  technique_17_answer_intent: {
    direction: "TB",
    nodes: [
      n("q", "Question", ["original query text"], "planning"),
      n("d1", "starts how many?", [], "planning", "diamond"),
      n("count", "COUNT shape", ["start with count"], "validation"),
      n("d2", "asks when?", [], "planning", "diamond"),
      n("when", "WHEN shape", ["date/time or unavailable"], "validation"),
      n("d3", "asks which/list/status?", [], "planning", "diamond"),
      n("other", "LIST / STATUS / DETAIL", ["choose answer shape"], "validation"),
    ],
    edges: [e("q", "d1", "classify intent"), e("d1", "count", "yes"), e("d1", "d2", "no"), e("d2", "when", "yes"), e("d2", "d3", "no"), e("d3", "other", "match keywords")],
  },
  technique_18_answer_claims: {
    direction: "LR",
    nodes: [
      n("answer", "CandidateAnswer", ["Birthday Message has not been published"], "artifact"),
      n("claims", "AnswerClaims", ["entity: Birthday Message", "status: not published", "number/timestamp/API claims"], "validation"),
      n("verify", "Verification Units", ["claim type", "claim value", "support needed"], "validation"),
    ],
    edges: [e("answer", "claims", "split into facts"), e("claims", "verify", "prepare support checks")],
  },
  technique_19_answer_verifier: {
    direction: "LR",
    nodes: [
      n("claims", "Claims + EvidenceSlots", ["claim list", "supported slot values", "dry_run flag"], "validation"),
      n("table", "Support Check Table", ["published_time=null | SQL row | supported", "API confirmed | dry_run=true | blocked"], "artifact"),
      n("out", "VerifiedAnswer", ["final_text", "verifier_passed", "caveats[]", "safe_rewrite?"] , "validation"),
    ],
    edges: [e("claims", "table", "compare every claim"), e("table", "out", "pass or rewrite")],
  },
  technique_20_answer_reranker: {
    direction: "LR",
    nodes: [
      n("candidates", "Candidate Answers", ["concise", "evidence-grounded", "gold-style"], "artifact"),
      n("scores", "Rerank Table", ["verifier pass", "intent match", "length", "unsupported claims"], "validation"),
      n("final", "Final Answer", ["best supported", "short if tied"], "validation"),
    ],
    edges: [e("candidates", "scores", "same evidence only"), e("scores", "final", "choose best")],
  },
  technique_21_answer_diagnostics: {
    direction: "LR",
    nodes: [
      n("final", "Final Answer", ["answer_family", "answer_intent", "verifier status"], "validation"),
      n("diag", "AnswerDiagnostics", ["verifier_passed", "unsupported_claims_count", "rewrite_applied", "selected_candidate_type"], "artifact"),
      n("traj", "trajectory.json", ["answer diagnostics", "tool results", "optimizer actions"], "artifact"),
      n("fail", "failure_analysis", ["weak family", "recommended_fix"], "artifact"),
    ],
    edges: [e("final", "diag", "record compact stats"), e("diag", "traj", "write trace"), e("traj", "fail", "debug next pass")],
  },
};

function wholeProjectDiagram() {
  const nodes = [
    n("raw", "RawQuery", ["text", "query_id", "strategy"], "planning"),
    n("norm", "NormalizedQuery", ["original_text", "normalized_text", "rewrites[]"], "planning"),
    n("tok", "QueryTokens", ["entities[]", "ids[]", "dates[]", "metrics[]", "statuses[]"], "planning"),
    n("qa", "QueryAnalysis", ["route_type", "domain_type", "answer_family", "sql_template", "api_templates", "confidence"], "planning"),
    n("meta", "SelectedMetadata", ["tables[]", "columns[]", "join_hints[]", "api_candidates[]", "context_card"], "artifact"),
    n("draft", "DraftPlan", ["sql_steps[]", "api_steps[]", "dependencies[]"], "planning"),
    n("budget", "BudgetedPlan", ["required_calls[]", "optional_calls[]", "skipped_calls[]", "max_tool_calls"], "planning"),
    n("opt", "OptimizedPlan", ["steps[]", "optimizer_actions[]", "unresolved_placeholders[]"], "validation"),
    n("valid", "ValidatedPlan", ["valid_sql_steps[]", "valid_api_steps[]", "validation_warnings[]"], "validation"),
    n("results", "ToolResults", ["sql_rows[]", "api_payloads[]", "dry_run_flags[]", "errors[]"], "evidence"),
    n("bus", "EvidenceBus", ["entity_ids{}", "names[]", "counts{}", "timestamps[]", "statuses[]", "sql_rows[]", "api_items[]"], "evidence"),
    n("slots", "AnswerSlots", ["entity_name", "entity_id", "count", "status", "timestamp", "metric_value", "dry_run", "discrepancy"], "validation"),
    n("ans", "VerifiedAnswer", ["final_text", "verifier_passed", "unsupported_claims_count", "caveats[]"], "validation"),
    n("art", "Artifacts", ["metadata.json", "filled_system_prompt.txt", "trajectory.json", "eval reports"], "artifact"),
  ];
  const edges = [
    e("raw", "norm", "normalize: clean text; preserve original"),
    e("norm", "tok", "tokenize: names, IDs, dates, metrics"),
    e("tok", "qa", "classify: domain + templates"),
    e("qa", "meta", "select compact schema/API context"),
    e("meta", "draft", "plan: generate SQL/API steps"),
    e("draft", "budget", "policy: REQUIRED/OPTIONAL/SKIP"),
    e("budget", "opt", "optimize: dedupe + drop placeholders"),
    e("opt", "valid", "validate SQL safety + API catalog"),
    e("valid", "results", "execute_sql + call_api/dry-run"),
    e("results", "bus", "extract structured facts"),
    e("bus", "slots", "forward exact evidence"),
    e("slots", "ans", "verify claims + rerank"),
    e("ans", "art", "write reproducible trace"),
  ];
  return {
    direction: "TB",
    nodes,
    edges,
    ranks: [
      ["raw", "norm", "tok"],
      ["qa", "meta", "draft", "budget", "opt", "valid"],
      ["results", "bus"],
      ["slots", "ans", "art"],
    ],
    clusters: [
      { label: "Query Frontend", theme: "planning", nodeIds: ["raw", "norm", "tok"] },
      { label: "Planning / Control", theme: "planning", nodeIds: ["qa", "meta", "draft", "budget", "opt", "valid"] },
      { label: "Execution / Evidence", theme: "evidence", nodeIds: ["results", "bus"] },
      { label: "Answer / Artifacts", theme: "validation", nodeIds: ["slots", "ans", "art"] },
    ],
  };
}

function wholeProjectPlanningDiagram() {
  const nodes = [
    n("raw", "RawQuery", ["text", "query_id", "strategy"], "planning"),
    n("norm", "NormalizedQuery", ["original_text", "normalized_text", "rewrites[]"], "planning"),
    n("tok", "QueryTokens", ["entities[]", "ids[]", "dates[]", "metrics[]", "statuses[]"], "planning"),
    n("qa", "QueryAnalysis", ["route_type", "domain_type", "answer_family", "sql_template", "api_templates", "confidence"], "planning"),
    n("meta", "SelectedMetadata", ["tables[]", "columns[]", "join_hints[]", "api_candidates[]", "context_card"], "artifact"),
    n("draft", "DraftPlan", ["sql_steps[]", "api_steps[]", "dependencies[]"], "planning"),
    n("budget", "BudgetedPlan", ["required_calls[]", "optional_calls[]", "skipped_calls[]", "max_tool_calls"], "planning"),
    n("opt", "OptimizedPlan", ["steps[]", "optimizer_actions[]", "unresolved_placeholders[]"], "validation"),
    n("valid", "ValidatedPlan", ["valid_sql_steps[]", "valid_api_steps[]", "validation_warnings[]"], "validation"),
  ];
  const edges = [
    e("raw", "norm", "normalize: clean text; preserve original"),
    e("norm", "tok", "tokenize: names, IDs, dates, metrics"),
    e("tok", "qa", "classify: domain + templates"),
    e("qa", "meta", "select compact schema/API context"),
    e("meta", "draft", "plan: generate SQL/API steps"),
    e("draft", "budget", "policy: REQUIRED / OPTIONAL / SKIP"),
    e("budget", "opt", "optimize: dedupe + drop placeholders"),
    e("opt", "valid", "validate SQL safety + API catalog"),
  ];
  return {
    direction: "TB",
    nodes,
    edges,
    ranks: [["raw", "norm", "tok"], ["qa", "meta", "draft"], ["budget", "opt", "valid"]],
  };
}

function wholeProjectEvidenceAnswerDiagram() {
  const nodes = [
    n("valid", "ValidatedPlan", ["valid_sql_steps[]", "valid_api_steps[]", "validation_warnings[]"], "validation"),
    n("results", "ToolResults", ["sql_rows[]", "api_payloads[]", "dry_run_flags[]", "errors[]"], "evidence"),
    n("bus", "EvidenceBus", ["entity_ids{}", "names[]", "counts{}", "timestamps[]", "statuses[]", "sql_rows[]", "api_items[]"], "evidence"),
    n("slots", "AnswerSlots", ["entity_name", "entity_id", "count", "status", "timestamp", "metric_value", "dry_run", "discrepancy"], "validation"),
    n("ans", "VerifiedAnswer", ["final_text", "verifier_passed", "unsupported_claims_count", "caveats[]"], "validation"),
    n("art", "Artifacts", ["metadata.json", "filled_system_prompt.txt", "trajectory.json", "eval reports"], "artifact"),
  ];
  const edges = [
    e("valid", "results", "execute_sql + call_api/dry-run"),
    e("results", "bus", "extract structured facts"),
    e("bus", "slots", "forward exact evidence"),
    e("slots", "ans", "verify claims + rerank"),
    e("ans", "art", "write reproducible trace"),
  ];
  return {
    direction: "TB",
    nodes,
    edges,
    ranks: [["valid", "results", "bus"], ["slots", "ans", "art"]],
  };
}

function birthdayDiagram() {
  const nodes = [
    n("raw", "RawQuery", ['When was "Birthday Message" published?'], "planning"),
    n("tokens", "QueryTokens", ["entity = Birthday Message", "intent = WHEN / STATUS"], "planning"),
    n("analysis", "QueryAnalysis", ["domain = JOURNEY_CAMPAIGN", "table = dim_campaign", "api = /ajo/journey"], "planning"),
    n("sql", "SQL Step", ["SELECT name, lastdeployedtime", "FROM dim_campaign", "WHERE name = Birthday Message"], "sql"),
    n("sqlres", "SQL Result", ["lastdeployedtime = null"], "sql"),
    n("api", "API Dry-Run", ["GET /ajo/journey", "filter=name==Birthday Message", "dry_run = true"], "api"),
    n("gold", "Gold API Comparison", ["method/path/params match"], "api"),
    n("slots", "AnswerSlots", ["entity_name = Birthday Message", "published_time = null", "dry_run = true"], "validation"),
    n("verifier", "Verifier", ["API confirmation blocked", "dry-run caveat required"], "validation"),
    n("answer", "FinalAnswer", ["not published", "live API verification not executed"], "validation"),
    n("traj", "Artifact", ["trajectory.json records SQL, API dry-run, diagnostics"], "artifact"),
  ];
  const edges = [
    e("raw", "tokens", "extract entity + intent"),
    e("tokens", "analysis", "route journey/status"),
    e("analysis", "sql", "generate SQL"),
    e("sql", "sqlres", "execute_sql"),
    e("sqlres", "api", "plan verification API"),
    e("api", "gold", "dry-run scoring"),
    e("gold", "slots", "store evidence"),
    e("slots", "verifier", "check claims"),
    e("verifier", "answer", "safe final text"),
    e("answer", "traj", "log trace"),
  ];
  return {
    direction: "TB",
    nodes,
    edges,
    ranks: [
      ["raw", "tokens", "analysis"],
      ["sql", "sqlres"],
      ["api", "gold"],
      ["slots", "verifier", "answer", "traj"],
    ],
  };
}

function memoryCacheDiagram() {
  const nodes = [
    n("request", "Query request", ["query_id", "strategy", "file mtimes"], "planning"),
    n("l1", "L1 In-memory cache", ["QueryAnalysis cache", "template selection cache"], "artifact"),
    n("hit1", "L1 hit?", [], "artifact", "diamond"),
    n("l2", "L2 Disk cache", ["schema_summary.json", "join_graph.json", "endpoint_catalog.json", "gold patterns"], "artifact"),
    n("fresh", "fresh?", ["file mtimes", "artifact version"], "artifact", "diamond"),
    n("l3", "L3 Local database", ["DuckDB", "DBSnapshot parquet", "dim_* tables", "hkg_br_* bridge tables"], "sql"),
    n("l4", "L4 External API", ["Adobe Journey Optimizer", "Adobe Experience Platform", "dry-run or live"], "api"),
    n("store", "Artifact Store", ["metadata.json", "filled_system_prompt.txt", "trajectory.json", "eval reports", "source_code.zip", "final_submission_manifest.json"], "artifact"),
  ];
  const edges = [
    e("request", "l1", "lookup analysis"),
    e("l1", "hit1", "memory check"),
    e("hit1", "store", "yes: reuse"),
    e("hit1", "l2", "no"),
    e("l2", "fresh", "checksum/mtime check"),
    e("fresh", "store", "yes: load artifacts"),
    e("fresh", "l3", "no: rebuild schema"),
    e("l3", "l2", "write fresh cache"),
    e("l3", "l4", "API only when needed"),
    e("l4", "store", "log dry-run/live evidence"),
  ];
  return {
    direction: "TB",
    nodes,
    edges,
    ranks: [
      ["request", "store"],
      ["l1", "hit1"],
      ["l2", "fresh"],
      ["l3", "l4"],
    ],
  };
}

function detailedDiagramFor(spec) {
  if (spec.id === "whole_project_planning_dataflow") return wholeProjectPlanningDiagram();
  if (spec.id === "whole_project_evidence_answer_dataflow") return wholeProjectEvidenceAnswerDiagram();
  if (spec.id === "whole_project_workflow") return wholeProjectDiagram();
  if (spec.id === "concrete_birthday_message") return birthdayDiagram();
  if (spec.id === "memory_cache_hierarchy") return memoryCacheDiagram();
  return DETAILED_DIAGRAMS[spec.id] || genericDiagram(spec);
}

async function writeFile(file, content) {
  await fs.mkdir(path.dirname(file), { recursive: true });
  await fs.writeFile(file, content, "utf8");
}

function renderDot(dotPath, svgPath, pngPath) {
  const svg = spawnSync("dot", ["-Tsvg", dotPath, "-o", svgPath], { encoding: "utf8" });
  if (svg.status !== 0) throw new Error(`dot svg failed for ${dotPath}: ${svg.stderr || svg.stdout}`);
  const png = spawnSync("dot", ["-Tpng", "-Gdpi=230", dotPath, "-o", pngPath], { encoding: "utf8" });
  if (png.status !== 0) throw new Error(`dot png failed for ${dotPath}: ${png.stderr || png.stdout}`);
}

function renderMermaid(mmdPath, svgPath, pngPath) {
  const svg = spawnSync("npx", ["--yes", "@mermaid-js/mermaid-cli@latest", "-i", mmdPath, "-o", svgPath, "-b", "white"], { encoding: "utf8" });
  if (svg.status !== 0) throw new Error(`mmdc svg failed for ${mmdPath}: ${svg.stderr || svg.stdout}`);
  const png = spawnSync("npx", ["--yes", "@mermaid-js/mermaid-cli@latest", "-i", mmdPath, "-o", pngPath, "-b", "white", "-s", "3"], { encoding: "utf8" });
  if (png.status !== 0) throw new Error(`mmdc png failed for ${mmdPath}: ${png.stderr || png.stdout}`);
}

async function writeDiagram(spec) {
  const base = path.join(DIAGRAM_DIR, spec.id);
  const diagram = detailedDiagramFor(spec);
  const mmd = mermaidSourceForDiagram(spec, diagram);
  const dot = dotSourceFromDiagram(spec, diagram);
  await writeFile(`${base}.mmd`, mmd);
  await writeFile(`${base}.dot`, dot);
  renderDot(`${base}.dot`, `${base}.svg`, `${base}.png`);
  return {
    id: spec.id,
    title: spec.title,
    subtitle: spec.subtitle || "",
    mechanism: spec.mechanism || spec.title,
    technique: spec.technique || "",
    modules: spec.modules || "",
    benefit: spec.benefit || "",
    mmd: path.relative(ROOT, `${base}.mmd`),
    dot: path.relative(ROOT, `${base}.dot`),
    svg: path.relative(ROOT, `${base}.svg`),
    png: path.relative(ROOT, `${base}.png`),
  };
}

async function writeReadme(manifest) {
  const techniqueRows = manifest.techniques.map((d, i) => `| ${i + 6} | ${d.title} | \`${d.mmd}\` | \`${d.png}\` |`).join("\n");
  const extraRows = [
    [27, "Whole Project Workflow: Planning Dataflow", "whole_project_planning_dataflow"],
    [28, "Whole Project Workflow: Evidence and Answer Dataflow", "whole_project_evidence_answer_dataflow"],
    [29, "Concrete Birthday Message Example", "concrete_birthday_message"],
    [30, "Memory and Cache Hierarchy", "memory_cache_hierarchy"],
  ].map(([slide, title, id]) => `| ${slide} | ${title} | \`diagrams/${id}.mmd\` | \`diagrams/${id}.png\` |`).join("\n");
  const readme = `# DASHSys Progress Deck Diagrams

These diagrams are generated source assets for the DASHSys Systems Track progress deck.

## Tooling

- Diagram source: Mermaid flowchart files (\`.mmd\`) are generated as readable source companions.
- Rendered export: Graphviz DOT (\`.dot\`) is the layout source of truth for \`.svg\` and high-resolution \`.png\`.
- The DOT diagrams use object boxes, decision diamonds, score/table-like nodes, state transitions, and labeled payload arrows so the deck avoids fragile PowerPoint-native diagram layout.

## Regeneration

\`\`\`bash
node scripts/generate_dashsys_diagrams.mjs
node scripts/create_dashsys_progress_deck.mjs
\`\`\`

The PowerPoint generator inserts the exported \`.png\` files instead of manually recreating diagrams with many PowerPoint text boxes.

## Slide Mapping

| PPT slide | Diagram | Mermaid source | PNG export |
|---:|---|---|---|
${techniqueRows}
${extraRows}

The full one-file whole-project diagram is also generated for source completeness:
\`diagrams/whole_project_workflow.mmd\`, \`diagrams/whole_project_workflow.dot\`, \`diagrams/whole_project_workflow.svg\`, and \`diagrams/whole_project_workflow.png\`.

## Style

- Purple: planning/control
- Blue: SQL/local database
- Orange: API/live or dry-run
- Green: validation/verification
- Teal: evidence
- Gray: artifacts/logging
`;
  await writeFile(path.join(DIAGRAM_DIR, "README.md"), readme);
}

async function main() {
  await fs.mkdir(DIAGRAM_DIR, { recursive: true });
  const techniques = [];
  for (const spec of TECHNIQUES) techniques.push(await writeDiagram(spec));
  const extras = [];
  for (const spec of EXTRA_DIAGRAMS) extras.push(await writeDiagram(spec));
  const manifest = { generated_at: new Date().toISOString(), renderer: "Graphviz DOT with Mermaid source companions", techniques, extras };
  await writeFile(path.join(DIAGRAM_DIR, "diagram_manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
  await writeReadme(manifest);
  console.log(JSON.stringify({ diagrams: techniques.length + extras.length, output_dir: DIAGRAM_DIR }, null, 2));
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exit(1);
});
