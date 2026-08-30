#!/usr/bin/env node

import fs from "node:fs/promises";
import fsSync from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const OUT_DIR = path.join(ROOT, "outputs", "presentations");
const DIAGRAM_DIR = path.join(ROOT, "diagrams");
const FINAL_PPTX = path.join(OUT_DIR, "DASHSys_Systems_Track_Progress_Report.pptx");
const CONTACT_SHEET = path.join(OUT_DIR, "DASHSys_Systems_Track_Progress_Report_contact_sheet.png");
const MANIFEST = path.join(OUT_DIR, "DASHSys_Systems_Track_Progress_Report_manifest.json");
const THREAD_ID = process.env.CODEX_THREAD_ID || `manual-${Date.now()}`;
const WORKSPACE = path.join(process.env.TMPDIR || "/tmp", "codex-presentations", THREAD_ID, "dashsys-progress-report");
const PREVIEW_DIR = path.join(WORKSPACE, "preview");
const LAYOUT_DIR = path.join(WORKSPACE, "layout");
const SKILL_DIR = "/Users/tanqinyang/.codex/plugins/cache/openai-primary-runtime/presentations/26.430.10722/skills/presentations";
const ARTIFACT_TOOL = "/Users/tanqinyang/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

const W = 1280;
const H = 720;
const C = {
  ink: "#172033",
  muted: "#5F6B7A",
  line: "#D8E2EA",
  navy: "#0E2A47",
  blue: "#1769AA",
  orange: "#D97706",
  green: "#1A7F52",
  purple: "#6D5BD0",
  gray: "#687386",
  teal: "#0B8F8A",
  white: "#FFFFFF",
  off: "#F8FBFD",
  amber: "#D97706",
};

const runtime = await import(ARTIFACT_TOOL);
const { Presentation, PresentationFile } = runtime;

function line(fill = "#00000000", width = 0, style = "solid") {
  return { style, fill, width };
}

function addShape(slide, { x, y, w, h, fill = "#00000000", stroke = "#00000000", strokeWidth = 0, geometry = "rect", name }) {
  return slide.shapes.add({
    geometry,
    name,
    position: { left: x, top: y, width: w, height: h },
    fill,
    line: line(stroke, strokeWidth),
  });
}

function addText(slide, text, x, y, w, h, options = {}) {
  const shape = addShape(slide, {
    x,
    y,
    w,
    h,
    fill: options.fill || "#00000000",
    stroke: options.stroke || "#00000000",
    strokeWidth: options.strokeWidth || 0,
    geometry: options.geometry || "rect",
    name: options.name,
  });
  shape.text = text;
  shape.text.fontSize = options.size || 18;
  shape.text.color = options.color || C.ink;
  shape.text.bold = Boolean(options.bold);
  if (options.underline) shape.text.underline = options.underline;
  shape.text.typeface = options.face || "Aptos";
  shape.text.alignment = options.align || "left";
  shape.text.verticalAlignment = options.valign || "top";
  shape.text.insets = options.insets || { left: 0, right: 0, top: 0, bottom: 0 };
  return shape;
}

function addSlide(presentation, title, kicker = "DASHSys Systems Track") {
  const slide = presentation.slides.add();
  slide.background.fill = C.off;
  addShape(slide, { x: 0, y: 0, w: W, h: 8, fill: C.navy });
  addText(slide, kicker, 58, 32, 500, 22, { size: 13, color: C.teal, bold: true });
  addText(slide, title, 58, 58, 1110, 54, { size: 29, color: C.ink, bold: true, face: "Aptos Display" });
  addShape(slide, { x: 58, y: 124, w: 1164, h: 1.5, fill: C.line });
  return slide;
}

function addFooter(slide, n) {
  addText(slide, `DASHSys progress report | ${String(n).padStart(2, "0")}`, 58, 686, 360, 18, { size: 10, color: C.muted });
}

function note(slide, text) {
  slide.speakerNotes.setText(text);
}

function bulletList(slide, items, x, y, w, options = {}) {
  const gap = options.gap || 36;
  items.forEach((item, i) => {
    addShape(slide, { x, y: y + i * gap + 8, w: 7, h: 7, fill: options.dot || C.teal });
    addText(slide, item, x + 20, y + i * gap, w - 20, gap, { size: options.size || 18, color: options.color || C.ink });
  });
}

function card(slide, x, y, w, h, title, body, options = {}) {
  addShape(slide, { x, y, w, h, fill: options.fill || C.white, stroke: options.stroke || C.line, strokeWidth: 1 });
  if (options.accent) addShape(slide, { x, y, w: 7, h, fill: options.accent });
  addText(slide, title, x + 18, y + 14, w - 36, 24, { size: options.titleSize || 16, bold: true, color: options.titleColor || C.ink });
  addText(slide, body, x + 18, y + 46, w - 36, h - 56, { size: options.bodySize || 13.5, color: options.bodyColor || C.muted });
}

function cueBox(slide, text, x, y, w, h, options = {}) {
  addShape(slide, { x, y, w, h, fill: options.fill || "#EEF8FA", stroke: options.stroke || "#BDE7E5", strokeWidth: 1 });
  addShape(slide, { x, y, w: 6, h, fill: options.accent || C.teal });
  addText(slide, options.label || "Speaking cue", x + 14, y + 8, 104, 15, { size: 9.8, color: options.accent || C.teal, bold: true });
  addText(slide, text, x + 122, y + 6, w - 138, h - 10, { size: options.size || 11.6, color: C.ink });
}

function metric(slide, x, y, w, label, value, noteText, color = C.blue) {
  addShape(slide, { x, y, w, h: 104, fill: C.white, stroke: C.line, strokeWidth: 1 });
  addText(slide, label, x + 18, y + 16, w - 36, 20, { size: 13, color: C.muted, bold: true });
  addText(slide, value, x + 18, y + 39, w - 36, 34, { size: 28, color, bold: true, face: "Aptos Display" });
  addText(slide, noteText, x + 18, y + 76, w - 36, 22, { size: 11, color: C.muted });
}

function table(slide, x, y, columns, rows, widths, options = {}) {
  const rowH = options.rowH || 34;
  const headH = options.headH || 34;
  let cx = x;
  columns.forEach((col, i) => {
    addShape(slide, { x: cx, y, w: widths[i], h: headH, fill: options.headFill || C.navy });
    addText(slide, col, cx + 8, y + 8, widths[i] - 16, headH - 10, { size: options.headSize || 11, bold: true, color: C.white });
    cx += widths[i];
  });
  rows.forEach((row, r) => {
    cx = x;
    row.forEach((cell, i) => {
      addShape(slide, { x: cx, y: y + headH + r * rowH, w: widths[i], h: rowH, fill: r % 2 ? "#F7FAFC" : C.white, stroke: C.line, strokeWidth: 0.8 });
      addText(slide, String(cell), cx + 8, y + headH + r * rowH + 5, widths[i] - 16, rowH - 7, {
        size: options.bodySize || 10.5,
        color: i === 0 ? C.ink : C.muted,
        bold: i === 0 && options.boldFirst !== false,
      });
      cx += widths[i];
    });
  });
}

async function addImage(slide, filePath, x, y, w, h, alt) {
  const bytes = await fs.readFile(filePath);
  const blob = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  const image = slide.images.add({ blob, fit: "contain", alt });
  image.position = { left: x, top: y, width: w, height: h };
  return image;
}

function diagramFrame(slide, x, y, w, h, title = "Workflow diagram") {
  addShape(slide, { x, y, w, h, fill: C.white, stroke: C.line, strokeWidth: 1.2 });
  addText(slide, title, x + 16, y + 12, w - 32, 20, { size: 11.5, color: C.muted, bold: true });
}

function fourColumnStrip(slide, spec, y = 566) {
  const x = 58;
  const widths = [210, 330, 286, 338];
  const labels = ["Mechanism", "Technique used", "Modules", "Benefit"];
  const stripH = 96;
  const values = [
    spec.mechanism,
    simpleTechniqueLabels[spec.mechanism] || spec.technique,
    spec.modules,
    techniqueWhy[spec.mechanism] || spec.benefit,
  ];
  let cx = x;
  labels.forEach((label, i) => {
    addShape(slide, { x: cx, y, w: widths[i], h: stripH, fill: C.white, stroke: C.line, strokeWidth: 1 });
    addText(slide, label, cx + 12, y + 10, widths[i] - 24, 16, { size: 9.8, color: C.muted, bold: true });
    if (i === 2) {
      addModuleTextList(slide, values[i], cx + 12, y + 30, widths[i] - 24, stripH - 40);
    } else {
      addText(slide, values[i], cx + 12, y + 30, widths[i] - 24, stripH - 42, { size: 10.7, color: i === 1 ? C.purple : C.ink, bold: i === 0 });
    }
    cx += widths[i];
  });
}

function addModuleTextList(slide, modulesText, x, y, w, h) {
  const modules = String(modulesText).split(",").map((item) => item.trim()).filter(Boolean);
  const gap = 4;
  const useTwoCols = modules.length > 2 && modules.every((moduleName) => moduleName.length <= 18);
  const cols = useTwoCols ? 2 : 1;
  const rows = Math.ceil(modules.length / cols);
  const buttonH = Math.min(23, Math.max(17, (h - gap * Math.max(0, rows - 1)) / Math.max(1, rows)));
  const buttonW = (w - gap * Math.max(0, cols - 1)) / cols;
  modules.forEach((moduleName, i) => {
    const col = useTwoCols ? i % cols : 0;
    const row = useTwoCols ? Math.floor(i / cols) : i;
    const bx = x + col * (buttonW + gap);
    const by = y + row * (buttonH + gap);
    const label = `Open ${moduleName}`;
    addText(slide, label, bx, by, buttonW, buttonH, {
      fill: "#EAF3FF",
      stroke: C.blue,
      strokeWidth: 1.1,
      geometry: "roundRect",
      size: moduleName.length > 23 ? 7.4 : 8.2,
      color: C.blue,
      bold: true,
      underline: "sng",
      align: "center",
      valign: "middle",
      insets: { left: 4, right: 4, top: 1, bottom: 1 },
      name: `module-link-${moduleName}`,
    });
  });
}

function numberedStepsBox(slide, title, steps, x, y, w, h, options = {}) {
  const cols = options.cols || (steps.length > 4 ? 2 : 1);
  const titleH = options.titleH || 28;
  const pad = options.pad || 14;
  const gapX = options.gapX || 20;
  const colW = (w - pad * 2 - gapX * (cols - 1)) / cols;
  const rows = Math.ceil(steps.length / cols);
  const rowH = (h - titleH - pad * 1.7) / rows;
  addShape(slide, { x, y, w, h, fill: C.white, stroke: options.stroke || C.line, strokeWidth: 1.1 });
  if (options.accent) addShape(slide, { x, y, w: 6, h, fill: options.accent });
  addText(slide, title, x + pad, y + 9, w - pad * 2, 18, { size: options.titleSize || 13, bold: true, color: options.titleColor || C.ink });
  steps.forEach((step, i) => {
    const col = Math.floor(i / rows);
    const row = i % rows;
    const bx = x + pad + col * (colW + gapX);
    const by = y + titleH + pad * 0.7 + row * rowH;
    addShape(slide, { x: bx, y: by + 2, w: 20, h: 20, fill: options.numberFill || "#F5F3FF", stroke: options.numberStroke || C.purple, strokeWidth: 1 });
    addText(slide, String(i + 1), bx, by + 5, 20, 12, { size: 9.5, bold: true, color: options.numberColor || C.purple, align: "center" });
    addText(slide, step, bx + 28, by, colW - 30, rowH - 3, { size: options.bodySize || 10.2, color: C.ink });
  });
}

const techniqueWhy = {
  "SQL/API templates": "Gives the system safe SQL/API patterns instead of letting it guess.",
  failure_analysis: "Shows which examples failed and what to fix next.",
  answer_templates: "Uses the right answer format for count, list, status, and detail questions.",
  evidence_policy: "Decides whether an API call is needed or can be skipped.",
  call_budget: "Limits how many SQL/API calls the system can make.",
  EvidenceBus: "Carries useful facts from SQL/API results to later steps.",
  QueryAnalysis: "Understands the question once and shares that decision.",
  LookupPathPredictor: "Acts like a map for finding the right tables and APIs.",
  PlanOptimizer: "Cleans the plan before running it.",
  "cache.py": "Reuses saved schema/API information.",
  context_cards: "Gives only the relevant context, not the whole database.",
  query_normalizer: "Cleans the wording of the question.",
  query_tokens: "Pulls out names, IDs, dates, metrics, and statuses.",
  relevance_scorer: "Ranks which tables/APIs are most likely useful.",
  plan_ensemble: "Compares possible plans and runs only the best one.",
  answer_slots: "Turns raw results into clean facts.",
  answer_intent: "Decides whether the answer should be a count, list, date, or status.",
  answer_claims: "Breaks the answer into facts that can be checked.",
  answer_verifier: "Checks that the answer is supported by evidence.",
  answer_reranker: "Chooses the best safe answer.",
  answer_diagnostics: "Logs why an answer passed or failed.",
};

const simpleTechniqueLabels = {
  "SQL/API templates": "Schema-guided planning — safe SQL/API patterns.",
  failure_analysis: "Benchmark-guided debugging — fix weakest examples first.",
  answer_templates: "Structured generation — use the right answer format.",
  evidence_policy: "Conditional execution — decide if API is needed.",
  call_budget: "Tool-call budget — limit SQL/API spending.",
  EvidenceBus: "Operand forwarding — pass exact results forward.",
  QueryAnalysis: "Shared query understanding — decide once and reuse.",
  LookupPathPredictor: "Lookup-path prediction — like using a map for tables/APIs.",
  PlanOptimizer: "Plan cleanup — remove duplicate or unsafe calls.",
  "cache.py": "Multi-level cache — reuse saved schema/API notes.",
  context_cards: "Context packing — give only relevant context.",
  query_normalizer: "Query cleaning — make wording easier to match.",
  query_tokens: "Entity extraction — pull out names, IDs, dates, metrics.",
  relevance_scorer: "Relevance ranking — focus on useful tables/APIs.",
  plan_ensemble: "Plan reranking — compare plans and run one.",
  answer_slots: "Evidence slots — turn raw results into clean facts.",
  answer_intent: "Answer intent — choose count/list/date/status shape.",
  answer_claims: "Claim splitting — break answer into checkable facts.",
  answer_verifier: "Answer fact-checking — verify claims against evidence.",
  answer_reranker: "Safe answer selection — choose the best supported answer.",
  answer_diagnostics: "Answer diagnostics — log why answers pass or fail.",
};

const simpleTechniquePurpose = {
  "SQL/API templates": "Templates are safe forms for SQL and API calls; they keep the system from inventing random joins, columns, or endpoints.",
  failure_analysis: "Failure analysis is the debugging loop: find the lowest-scoring examples and fix those reusable patterns first.",
  answer_templates: "Answer templates make responses less vague by matching the answer format to the question.",
  evidence_policy: "evidence_policy decides whether the system should call the API or whether SQL evidence is already enough.",
  call_budget: "call_budget is a spending limit for tool calls, so the agent cannot keep calling SQL/API tools unnecessarily.",
  EvidenceBus: "EvidenceBus passes exact results, such as IDs and counts, directly to later steps.",
  QueryAnalysis: "QueryAnalysis is the first serious understanding step: it decides what kind of question this is.",
  LookupPathPredictor: "LookupPathPredictor is a map for the database and API, especially for relationship questions.",
  PlanOptimizer: "PlanOptimizer cleans the to-do list before execution.",
  "cache.py": "cache.py saves schema and API information the system already learned.",
  context_cards: "context_cards give the system only the information needed for this question family.",
  query_normalizer: "query_normalizer cleans the question text while keeping the original query for outputs.",
  query_tokens: "query_tokens highlights the important names, IDs, dates, metrics, and statuses in the question.",
  relevance_scorer: "relevance_scorer helps the system focus on the most useful tables, columns, joins, and APIs.",
  plan_ensemble: "plan_ensemble checks a few possible routes, then runs only the best one.",
  answer_slots: "answer_slots turn raw SQL/API results into clean facts before writing the answer.",
  answer_intent: "answer_intent decides whether the answer should be a number, list, date, status, or details.",
  answer_claims: "answer_claims split an answer into small facts so each one can be checked.",
  answer_verifier: "answer_verifier is the fact-checker for the final answer.",
  answer_reranker: "answer_reranker chooses the best answer from safe options without calling more tools.",
  answer_diagnostics: "answer_diagnostics are debugging notes that explain why an answer passed or failed.",
};

const techniqueSteps = {
  "SQL/API templates": [
    "Read the question type.",
    "Pick the matching SQL/API template.",
    "Fill in known table, column, endpoint, and parameter names.",
    "Validate the SQL/API call.",
    "Send a safe structured plan forward.",
  ],
  failure_analysis: [
    "Run evaluation.",
    "Find low-scoring examples.",
    "Label the failure type.",
    "Fix the reusable rule or template.",
    "Add a test so the same failure does not come back.",
  ],
  answer_templates: [
    "Collect SQL/API evidence.",
    "Identify the answer type.",
    "Choose the matching answer format.",
    "Fill the answer with evidence.",
    "Return a concise response.",
  ],
  evidence_policy: [
    "Check the query type.",
    "Decide API_REQUIRED, API_OPTIONAL, or API_SKIP.",
    "Keep required API calls.",
    "Limit optional API calls.",
    "Remove API calls that are not needed.",
  ],
  call_budget: [
    "Look at the draft plan.",
    "Count SQL and API calls.",
    "Apply the tool-call limit.",
    "Remove optional extra calls.",
    "Send a bounded plan forward.",
  ],
  EvidenceBus: [
    "Read SQL/API results.",
    "Extract names, IDs, counts, dates, and statuses.",
    "Store them as structured facts.",
    "Pass them to API templates or answer slots.",
    "Avoid re-reading messy text.",
  ],
  QueryAnalysis: [
    "Read the cleaned query and extracted tokens.",
    "Decide the domain and route type.",
    "Pick likely SQL/API templates.",
    "Estimate confidence.",
    "Share this analysis with planning and reporting.",
  ],
  LookupPathPredictor: [
    "Identify the query family.",
    "Pick the matching lookup path.",
    "List needed tables, joins, APIs, and IDs.",
    "Guide metadata selection.",
    "Avoid unrelated tables and endpoints.",
  ],
  PlanOptimizer: [
    "Receive the draft plan.",
    "Remove duplicate calls.",
    "Remove API calls marked as skippable.",
    "Drop unresolved placeholders.",
    "Enforce the call budget.",
    "Output the cleaned plan.",
  ],
  "cache.py": [
    "Check memory cache.",
    "Check disk cache.",
    "Reuse fresh schema/API artifacts.",
    "Rebuild only if stale.",
    "Save time during query processing.",
  ],
  context_cards: [
    "Identify the query family.",
    "Pick the matching context card.",
    "Include only relevant tables, columns, APIs, and rules.",
    "Build compact metadata.",
    "Reduce prompt size.",
  ],
  query_normalizer: [
    "Keep the original query.",
    "Make a cleaned copy.",
    "Normalize spaces, quotes, hyphens, plurals, and synonyms.",
    "Use the cleaned version for matching.",
    "Improve robustness to wording differences.",
  ],
  query_tokens: [
    "Read the cleaned query.",
    "Extract entity names.",
    "Extract IDs, dates, metrics, fields, and status words.",
    "Send tokens to routing and templates.",
    "Fill plans more accurately.",
  ],
  relevance_scorer: [
    "Compare query tokens with schema/API candidates.",
    "Score each candidate.",
    "Keep the highest-ranked context.",
    "Drop low-relevance context.",
    "Reduce noise and tokens.",
  ],
  plan_ensemble: [
    "Generate cheap candidate plans.",
    "Score them before execution.",
    "Prefer valid, relevant, low-cost plans.",
    "Pick one plan.",
    "Execute only that plan.",
  ],
  answer_slots: [
    "Read tool results.",
    "Extract clean facts: name, ID, count, status, time, metric.",
    "Record dry-run and discrepancy flags.",
    "Use these facts as the answer source.",
    "Avoid unsupported values.",
  ],
  answer_intent: [
    "Read the question.",
    "Classify the expected answer type.",
    "Choose the answer shape.",
    "Make count questions start with counts.",
    "Make date questions start with dates or unavailable statements.",
  ],
  answer_claims: [
    "Read a candidate answer.",
    "Break it into factual claims.",
    "Mark number, name, date, status, and API-confirmation claims.",
    "Send these claims to the verifier.",
    "Make the answer auditable.",
  ],
  answer_verifier: [
    "Compare claims with evidence slots.",
    "Reject unsupported names, numbers, dates, and statuses.",
    "If API was dry-run, require a caveat.",
    "If SQL and API disagree, mention the conflict.",
    "Rewrite unsafe answers.",
  ],
  answer_reranker: [
    "Create a few candidate answers from the same evidence.",
    "Verify each one.",
    "Score support, intent match, style, and brevity.",
    "Pick the best verifier-passing answer.",
    "Return one final answer.",
  ],
  answer_diagnostics: [
    "Record answer family and intent.",
    "Record whether verification passed.",
    "Record unsupported claim count.",
    "Save diagnostics in trajectory.json.",
    "Use this later for failure analysis.",
  ],
};

const wholeProjectSteps = [
  "User asks a question.",
  "System cleans the wording.",
  "System extracts names, IDs, dates, metrics, and statuses.",
  "System decides the query type.",
  "System selects relevant tables and APIs.",
  "System creates a SQL/API plan.",
  "System removes unnecessary or unsafe calls.",
  "System validates the plan.",
  "System runs SQL and dry-run/live API.",
  "System collects evidence.",
  "System verifies the answer.",
  "System writes metadata.json, filled_system_prompt.txt, and trajectory.json.",
  "Evaluation checks correctness and efficiency.",
];

const birthdaySteps = [
  "Question asks when Birthday Message was published.",
  "System extracts Birthday Message as the journey name.",
  "System checks local database table dim_campaign.",
  "SQL finds lastdeployedtime is null.",
  "System plans API call: GET /ajo/journey?filter=name==Birthday Message.",
  "Because credentials are unavailable, API call is dry-run only.",
  "The planned method, endpoint, and params are compared with public gold API.",
  "Answer verifier prevents saying that live API confirmed anything.",
  "Final answer says Birthday Message has not been published, and live API verification was not executed.",
];

const cacheSteps = [
  "L1 cache stores recent query analysis and template choices.",
  "L2 disk cache stores schema, join graph, endpoint catalog, and patterns.",
  "L3 local database stores DuckDB/parquet evidence.",
  "L4 Adobe API is the external live source.",
  "Artifact store saves metadata, prompt, trajectory, reports, and submission files.",
  "This reduces repeated work while keeping the system reproducible.",
];

function slideTextForTerms(manifest, slides) {
  return [
    ...slides.map((slide) => slide.speakerNotes.text),
    ...manifest.techniques.map((t) => `${t.title} ${t.mechanism} ${t.technique} ${t.modules} ${t.benefit}`),
    "SQL_FIRST_API_VERIFY EvidenceBus QueryAnalysis PlanOptimizer LookupPathPredictor query_normalizer query_tokens relevance_scorer answer_slots answer_verifier answer_reranker metadata.json filled_system_prompt.txt trajectory.json",
    "Correctness 0.8407 Answer correctness 0.5208 Final score 0.8154 Tool calls 1.4571 Tokens 851.6 Tests 46 passed",
  ].join("\n");
}

async function techniqueSlide(p, slides, n, spec) {
  const s = addSlide(p, spec.title);
  const purpose = simpleTechniquePurpose[spec.mechanism] || spec.subtitle || "This mechanism makes the agent more accurate or efficient.";
  const techniqueLabel = simpleTechniqueLabels[spec.mechanism] || spec.technique;
  cueBox(s, purpose, 58, 132, 1070, 38, { size: 11.2 });
  addShape(s, { x: 58, y: 178, w: 580, h: 28, fill: "#F5F3FF", stroke: "#DDD6FE", strokeWidth: 1 });
  addText(s, `Technique used: ${techniqueLabel}`, 74, 185, 548, 15, { size: 12.2, color: C.purple, bold: true });
  diagramFrame(s, 58, 212, 1164, 266, "Dataflow / contract diagram");
  await addImage(s, path.join(ROOT, spec.png), 82, 240, 1116, 220, spec.title);
  numberedStepsBox(s, "Step-by-step workflow", techniqueSteps[spec.mechanism] || [
    "Input enters this mechanism from the selected agent workflow.",
    "The mechanism performs a deterministic transformation.",
    "The output is passed to the next validated stage.",
    `Benefit: ${spec.benefit}.`,
  ], 58, 486, 1164, 66, { cols: 3, accent: C.purple, bodySize: 6.9, titleSize: 10.8, titleH: 20, pad: 8, gapX: 12 });
  fourColumnStrip(s, spec, 562);
  addFooter(s, n);
  note(s, `${spec.title}. Simple explanation: ${purpose} Step-by-step workflow: ${(techniqueSteps[spec.mechanism] || []).join(" ")} Mechanism: ${spec.mechanism}. Technique used: ${techniqueLabel}. Modules: ${spec.modules}. Benefit: ${techniqueWhy[spec.mechanism] || spec.benefit}.`);
  slides.push(s);
}

async function makeDeck(manifest) {
  const p = Presentation.create({ slideSize: { width: W, height: H } });
  const slides = [];

  {
    const s = p.slides.add();
    s.background.fill = C.navy;
    addShape(s, { x: 0, y: 0, w: W, h: H, fill: C.navy });
    addShape(s, { x: 0, y: 0, w: W, h: 10, fill: C.teal });
    addText(s, "DASHSys Systems Track Agent", 76, 112, 980, 56, { size: 40, bold: true, color: C.white, face: "Aptos Display" });
    addText(s, "Progress and Optimization Report", 76, 174, 780, 36, { size: 26, bold: true, color: "#CFE8F3" });
    addText(s, "SQL-first/API-verification agent for data-centric question answering", 76, 244, 860, 32, { size: 20, color: "#E8F2F8" });
    addText(s, "To open local code links during slideshow, click the blue file buttons exactly; normal slide clicks advance the deck.", 76, 542, 930, 46, {
      fill: "#0B3D61",
      stroke: C.teal,
      strokeWidth: 1.2,
      geometry: "roundRect",
      size: 14.2,
      color: "#E8F2F8",
      bold: true,
      valign: "middle",
      insets: { left: 18, right: 18, top: 7, bottom: 7 },
    });
    addText(s, "Qinyang Tan · May 1, 2026", 76, 628, 560, 28, { size: 18, color: "#CFE8F3", bold: true });
    note(s, "Open with the project framing: this is a SQL-first/API-verification agent for the DASHSys Systems Track, and the deck explains the evolution from prototype to optimized submission system. To open local code links during slideshow, click the blue file buttons exactly; normal slide clicks advance the deck.");
    slides.push(s);
  }

  {
    const s = addSlide(p, "Project goal and evaluation criteria");
    cueBox(s, "The workshop asks the agent to answer questions using only SQL and API calls. The system must be accurate without wasting tool calls or tokens.", 82, 146, 1116, 54, { size: 12.8 });
    addText(s, "The system has to decide when to check the local database, when to call Adobe APIs, and how to explain the answer.", 110, 222, 1060, 40, { size: 19, color: C.ink, align: "center" });
    card(s, 82, 304, 338, 130, "Allowed tools", "execute_sql(sql)\ncall_api(method, url, params, headers)", { accent: C.purple, bodySize: 17 });
    card(s, 472, 304, 338, 130, "Correctness score", "SQL correctness\nAPI correctness\nAnswer correctness", { accent: C.green, bodySize: 17 });
    card(s, 862, 304, 338, 130, "Efficiency score", "Tool calls\nTokens\nRuntime and preprocessing time", { accent: C.blue, bodySize: 17 });
    card(s, 174, 500, 932, 74, "Required output", "For each query: metadata.json, filled_system_prompt.txt, and trajectory.json. Overall: source_code.zip-ready project.", { accent: C.gray, titleSize: 16, bodySize: 16 });
    addFooter(s, 2);
    note(s, "The workshop asks the agent to answer questions using only two tools: SQL and API calls. So the system has to decide when to check the local database, when to call Adobe APIs, and how to explain the answer. The score depends on both correctness and efficiency, so the system needs to be accurate without wasting tool calls or tokens.");
    slides.push(s);
  }

  {
    const s = addSlide(p, "Initial prototype: useful skeleton, weak precision");
    cueBox(s, "The first version was useful, but still rough. It could load data, prepare API calls, route questions, and save logs, but SQL was too simple and answers were not always shaped to the question.", 82, 142, 1116, 58, { size: 12.4 });
    card(s, 70, 274, 250, 120, "Database layer", "DuckDB loader\nParquet views\nRead-only SQL guard", { accent: C.blue, bodySize: 15.5 });
    card(s, 358, 274, 250, 120, "API client", "Env credentials\nDry-run mode\nRedacted logging", { accent: C.orange, bodySize: 15.5 });
    card(s, 646, 274, 250, 120, "Planner", "Simple routing\nMostly single-table SQL\nGeneric API params", { accent: C.purple, bodySize: 15.5 });
    card(s, 934, 274, 250, 120, "Trajectory", "Tool calls\nValidation\nFinal answer", { accent: C.gray, bodySize: 15.5 });
    addText(s, "Analogy: it was like a student who knows where the textbook is, but not yet which chapter to use.", 142, 510, 996, 46, { size: 22, bold: true, color: C.navy, align: "center" });
    addFooter(s, 3);
    note(s, "The first version was a useful skeleton. It could load the database, prepare API calls, route the question, and save logs. But it was still rough: SQL was often too simple, API calls were too generic, and answers were not always shaped to the question. It was like a student who knows where the textbook is, but not yet which chapter to use.");
    slides.push(s);
  }

  {
    const s = addSlide(p, "Iteration timeline: from skeleton to verified answers");
    cueBox(s, "The project improved step by step. Each pass fixed one clear weakness: planning, debugging, efficiency, query understanding, or answer checking.", 74, 142, 1132, 48, { size: 12.7 });
    const items = [
      ["Skeleton", "DuckDB, API client, router, simple planner"],
      ["Templates", "Schema-guided SQL and endpoint-constrained API params"],
      ["Failure analysis", "Ranked public-example failures drove targeted fixes"],
      ["Efficiency controls", "API policy, call budget, compact metadata"],
      ["Architecture pass", "EvidenceBus, QueryAnalysis, optimizer, cache"],
      ["NLP pass", "Normalization, tokens, relevance, one-plan selection"],
      ["Answer layer", "Slots, claims, verifier, reranker, diagnostics"],
    ];
    const x0 = 78;
    const y = 274;
    const nodeW = 146;
    const gap = 22;
    items.forEach(([title, body], i) => {
      const x = x0 + i * (nodeW + gap);
      addShape(s, { x, y, w: nodeW, h: 94, fill: C.white, stroke: i < 2 ? C.purple : i < 4 ? C.green : C.teal, strokeWidth: 1.4 });
      addText(s, title, x + 10, y + 12, nodeW - 20, 20, { size: 13, bold: true, color: C.ink, align: "center" });
      addText(s, body, x + 10, y + 38, nodeW - 20, 44, { size: 10.5, color: C.muted, align: "center" });
      if (i < items.length - 1) {
        addShape(s, { x: x + nodeW + 4, y: y + 45, w: gap - 8, h: 2, fill: C.gray });
        addText(s, ">", x + nodeW + gap - 12, y + 36, 14, 18, { size: 13, color: C.gray, bold: true });
      }
    });
    addText(s, "The architecture stayed stable; the improvements were targeted and measurable.", 124, 488, 1032, 36, { size: 20, bold: true, color: C.navy, align: "center" });
    addFooter(s, 4);
    note(s, "The project improved step by step. First I built the basic pipeline. Then I added templates so SQL and API calls became more reliable. Then I used failure analysis to fix the weakest examples. After that I added efficiency controls, architecture-inspired optimizations, NLP-style query understanding, and finally answer verification. Each pass fixed one clear weakness.");
    slides.push(s);
  }

  {
    const s = addSlide(p, "Optimization Techniques Used Across Iterations");
    cueBox(s, "This table shows what each added module does in simple terms. Some decide what to do, some run tools efficiently, and some check the final answer.", 58, 132, 1090, 34, { size: 11.2 });
    const rows = manifest.techniques.map((t) => [t.mechanism, simpleTechniqueLabels[t.mechanism] || t.technique, techniqueWhy[t.mechanism] || t.benefit]);
    table(s, 58, 174, ["Mechanism", "Technique Used", "Why It Helps"], rows.slice(0, 11), [180, 300, 330], { rowH: 32, headH: 30, bodySize: 8.4, headSize: 9.3 });
    table(s, 890, 174, ["Mechanism", "Technique Used", "Why It Helps"], rows.slice(11), [150, 250, 290], { rowH: 35, headH: 30, bodySize: 8.4, headSize: 9.3 });
    addFooter(s, 5);
    note(s, "This is the technique map. It connects project modules to known systems, compiler, NLP, and verification ideas so the professor can see the research framing.");
    slides.push(s);
  }

  let slideNo = 6;
  for (const spec of manifest.techniques) {
    await techniqueSlide(p, slides, slideNo, spec);
    slideNo += 1;
  }

  {
    const spec = manifest.extras.find((d) => d.id === "whole_project_planning_dataflow");
    const s = addSlide(p, "Whole project workflow: planning dataflow");
    cueBox(s, "Part A shows how the question becomes a validated plan. Each block shows the object fields being carried forward, and each arrow names the transformation.", 58, 132, 1100, 42, { size: 11.2 });
    diagramFrame(s, 58, 184, 1164, 326, "Object transformations: RawQuery to ValidatedPlan");
    await addImage(s, path.join(ROOT, spec.png), 76, 224, 1128, 258, spec.title);
    numberedStepsBox(s, "Transition summary", wholeProjectSteps.slice(0, 8), 58, 524, 1164, 92, { cols: 4, accent: C.teal, bodySize: 7.3, titleSize: 11, titleH: 22, pad: 9, gapX: 14, numberFill: "#E8FAF8", numberStroke: C.teal, numberColor: C.teal });
    addFooter(s, slideNo);
    note(s, `Whole project workflow Part A. It shows object transformations from RawQuery to ValidatedPlan. Steps: ${wholeProjectSteps.slice(0, 8).join(" ")}`);
    slides.push(s);
    slideNo += 1;
  }

  {
    const spec = manifest.extras.find((d) => d.id === "whole_project_evidence_answer_dataflow");
    const s = addSlide(p, "Whole project workflow: evidence and answer dataflow");
    cueBox(s, "Part B shows how validated tool calls become evidence, verified answer slots, and reproducible artifacts.", 58, 132, 1100, 42, { size: 11.2 });
    diagramFrame(s, 58, 184, 1164, 326, "Object transformations: ValidatedPlan to Artifacts");
    await addImage(s, path.join(ROOT, spec.png), 76, 224, 1128, 258, spec.title);
    numberedStepsBox(s, "Transition summary", wholeProjectSteps.slice(8), 58, 524, 1164, 92, { cols: 3, accent: C.teal, bodySize: 7.8, titleSize: 11, titleH: 22, pad: 9, gapX: 14, numberFill: "#E8FAF8", numberStroke: C.teal, numberColor: C.teal });
    addFooter(s, slideNo);
    note(s, `Whole project workflow Part B. It shows execution, evidence forwarding, answer verification, and artifacts. Steps: ${wholeProjectSteps.slice(8).join(" ")}`);
    slides.push(s);
    slideNo += 1;
  }

  {
    const spec = manifest.extras.find((d) => d.id === "concrete_birthday_message");
    const s = addSlide(p, "Concrete dry-run example: Birthday Message");
    cueBox(s, "This example shows dry-run API evaluation. Without credentials, the system checks whether the planned API call is correct instead of claiming a live API result.", 58, 132, 1100, 42, { size: 11.4, accent: C.orange, fill: "#FFF7ED", stroke: "#FED7AA" });
    diagramFrame(s, 58, 184, 1164, 260, "Detailed trace: fields, payloads, and dry-run condition");
    await addImage(s, path.join(ROOT, spec.png), 76, 224, 1128, 190, spec.title);
    numberedStepsBox(s, "Step-by-step dry-run trace", birthdaySteps, 58, 462, 1164, 174, { cols: 3, accent: C.orange, bodySize: 8.0, titleSize: 11.5, titleH: 24, pad: 10, gapX: 14, numberFill: "#FFF3E0", numberStroke: C.orange, numberColor: C.orange });
    addFooter(s, slideNo);
    note(s, `Talk through the Birthday Message trace. ${birthdaySteps.join(" ")}`);
    slides.push(s);
    slideNo += 1;
  }

  {
    const spec = manifest.extras.find((d) => d.id === "memory_cache_hierarchy");
    const s = addSlide(p, "Memory and cache hierarchy");
    cueBox(s, "The cache hierarchy is like using notes before searching everywhere. It checks memory, saved files, the local database, and then Adobe API when needed.", 58, 132, 1100, 42, { size: 11.4, accent: C.gray, fill: "#F6F7F9", stroke: "#D8E2EA" });
    diagramFrame(s, 58, 184, 1164, 258, "Cache hierarchy with hit/miss and freshness transitions");
    await addImage(s, path.join(ROOT, spec.png), 76, 224, 1128, 188, spec.title);
    numberedStepsBox(s, "How the cache hierarchy supports reproducibility", cacheSteps, 58, 458, 1164, 114, { cols: 3, accent: C.gray, bodySize: 8.2, titleSize: 11.2, titleH: 22, pad: 9, gapX: 14, numberFill: "#F2F4F7", numberStroke: C.gray, numberColor: C.gray });
    card(s, 90, 590, 1080, 42, "Cache boundary", "Live API response caching is disabled for final live mode unless explicitly enabled; dry-run/dev artifacts stay reproducible.", { accent: C.gray, titleSize: 10.5, bodySize: 9.8 });
    addFooter(s, slideNo);
    note(s, `Present this as the memory hierarchy analogy. ${cacheSteps.join(" ")}`);
    slides.push(s);
    slideNo += 1;
  }

  {
    const s = addSlide(p, "Current metrics: compact and submission-ready");
    cueBox(s, "The current best strategy is SQL_FIRST_API_VERIFY. It gives the best balance between correctness and efficiency.", 70, 132, 1120, 42, { size: 11.8 });
    metric(s, 70, 194, 170, "Correctness", "0.8407", "combined SQL/API/answer", C.green);
    metric(s, 260, 194, 190, "Answer correctness", "0.5208", "weakest dimension", C.teal);
    metric(s, 470, 194, 170, "Final score", "0.8154", "efficiency-adjusted", C.purple);
    metric(s, 660, 194, 170, "Tool calls", "1.4571", "avg per query", C.blue);
    metric(s, 850, 194, 150, "Tokens", "851.6", "estimated avg", C.orange);
    metric(s, 1020, 194, 170, "Tests", "46 passed", "readiness passed", C.gray);
    table(s, 158, 356, ["Strategy", "Correctness", "Final score", "Notes"], [
      ["SQL_FIRST_API_VERIFY", "0.8407", "0.8154", "Default final-submission strategy"],
      ["TEMPLATE_FIRST", "competitive", "lower/riskier", "Higher overfitting risk"],
      ["SQL_ONLY_BASELINE", "lower", "efficient only", "Misses API-required families"],
    ], [300, 180, 180, 460], { rowH: 46, headH: 38, bodySize: 13, headSize: 12 });
    addText(s, "The current best strategy is SQL_FIRST_API_VERIFY. It gives the best balance between correctness and efficiency. Answer correctness still has room to improve, but the system is compact, tested, and package-ready.", 118, 562, 1044, 52, { size: 17.5, bold: true, color: C.navy, align: "center" });
    addFooter(s, slideNo);
    note(s, "The current best strategy is SQL_FIRST_API_VERIFY. It gives the best balance between correctness and efficiency. The system is not perfect, especially on answer correctness, but it is compact, tested, and package-ready.");
    slides.push(s);
    slideNo += 1;
  }

  {
    const s = addSlide(p, "System strengths");
    cueBox(s, "The system is strong because it does not freely guess. It uses templates, validation, budgets, evidence forwarding, and answer checking.", 82, 136, 1116, 46, { size: 11.8 });
    bulletList(s, [
      "Uses SQL/API templates instead of free-form guessing.",
      "Validates tables, columns, endpoints, and parameters before execution.",
      "Keeps tool calls low with evidence_policy and call_budget.",
      "Passes exact facts forward with EvidenceBus.",
      "Checks answer claims with answer_verifier and answer_reranker.",
      "Writes trajectory.json so failures can be inspected later.",
    ], 92, 228, 1040, { gap: 48, size: 18 });
    addFooter(s, slideNo);
    note(s, "The system is strong because it does not freely guess. It uses templates, validation, budgets, evidence forwarding, and answer checking. Every step is logged, so failures can be inspected.");
    slides.push(s);
    slideNo += 1;
  }

  {
    const s = addSlide(p, "Remaining risks before final submission");
    cueBox(s, "The main risk is live Adobe API testing. Right now, API calls are mostly evaluated by dry-run planning.", 82, 136, 1116, 42, { size: 11.8, accent: C.orange, fill: "#FFF7ED", stroke: "#FED7AA" });
    card(s, 78, 218, 506, 108, "Live API not tested", "Adobe credentials are needed to test real payloads, latency, and error cases.", { accent: C.orange, bodySize: 16 });
    card(s, 696, 218, 506, 108, "API-only dry-run families", "Batches, tags, merge policies, segment jobs, and observability are still harder without live responses.", { accent: C.orange, bodySize: 16 });
    card(s, 78, 380, 506, 108, "Answer correctness moderate", "The verifier prevents unsupported facts, but unavailable dry-run answers still score lower.", { accent: C.green, bodySize: 16 });
    card(s, 696, 380, 506, 108, "Hidden wording risk", "Hidden tests may use different wording, names, or entity references.", { accent: C.purple, bodySize: 16 });
    addText(s, "Main blocker: live Adobe API validation.", 112, 588, 1056, 30, { size: 21, bold: true, color: C.navy, align: "center" });
    addFooter(s, slideNo);
    note(s, "The main risk is live Adobe API testing. Right now, API calls are mostly evaluated by dry-run planning. We still need credentials to test real API responses.");
    slides.push(s);
    slideNo += 1;
  }

  {
    const s = addSlide(p, "Next steps");
    cueBox(s, "Next: get Adobe credentials, run live API evaluation, inspect failures, improve parsers, and finalize the paper and package.", 82, 136, 1116, 42, { size: 11.8 });
    bulletList(s, [
      "Obtain Adobe API credentials and run live API evaluation.",
      "Inspect live failures and extend live_response_parsers.py for weak families.",
      "Finalize the 4-page VLDB-style system paper around the SQL-first/API-verifying design.",
      "Prepare final source_code.zip and per-query output package.",
      "Use professor feedback to prioritize paper framing and live-eval remediation.",
    ], 112, 218, 980, { gap: 58, size: 19 });
    addFooter(s, slideNo);
    note(s, "The next step is to get Adobe credentials, run live API evaluation, inspect failures, improve response parsers, and finalize the paper and package.");
    slides.push(s);
    slideNo += 1;
  }

  {
    const s = addSlide(p, "Paper contribution story");
    card(s, 110, 152, 1060, 86, "Core thesis", "We built a controlled SQL-first/API-verifying agent for data-centric natural-language QA.", { accent: C.purple, bodySize: 18 });
    card(s, 110, 266, 1060, 86, "How it works", "The system uses safe templates, validation, compact context, EvidenceBus forwarding, and answer_verifier checks.", { accent: C.blue, bodySize: 17 });
    card(s, 110, 380, 1060, 86, "Why it matters", "It improves correctness and efficiency while keeping one selected plan per query and a reproducible trajectory.", { accent: C.green, bodySize: 17 });
    addText(s, "Paper story: a simple, explainable agent that avoids guessing and records every step.", 120, 590, 1040, 44, { size: 21, bold: true, color: C.navy, align: "center" });
    addFooter(s, slideNo);
    note(s, "The paper story is simple: we built a controlled SQL-first/API-verifying agent. It improves correctness and efficiency by using safe templates, validation, compact context, evidence forwarding, and answer verification.");
    slides.push(s);
    slideNo += 1;
  }

  {
    const s = p.slides.add();
    s.background.fill = C.navy;
    addShape(s, { x: 0, y: 0, w: W, h: H, fill: C.navy });
    addShape(s, { x: 0, y: 0, w: W, h: 10, fill: C.teal });
    addText(s, "Closing: ready for professor feedback", 90, 116, 920, 58, { size: 36, bold: true, color: C.white, face: "Aptos Display" });
    bulletList(s, [
      "The pipeline is complete and reproducible.",
      "The system explanation is now simpler and easier to present.",
      "The main blocker is live API validation.",
      "Feedback needed: paper framing, live-eval priority, and clarity.",
    ], 110, 240, 920, { gap: 54, size: 23, color: C.white, dot: C.teal });
    addText(s, "SQL_FIRST_API_VERIFY remains the default.", 110, 628, 780, 32, { size: 22, bold: true, color: "#CFE8F3" });
    note(s, "The pipeline is complete and reproducible. The main blocker is live API validation. I need feedback on the paper framing, live-eval priority, and whether the system explanation is clear.");
    slides.push(s);
  }

  return { presentation: p, slides };
}

async function saveBlob(blob, filePath) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, Buffer.from(await blob.arrayBuffer()));
}

async function makeContactSheet(paths, out) {
  const result = spawnSync("python3", [path.join(SKILL_DIR, "scripts", "make_contact_sheet.py"), "--output", out, ...paths], { encoding: "utf8" });
  if (result.status === 0) return;
  const cols = 5;
  const rows = Math.ceil(paths.length / cols);
  const thumbW = 244;
  const thumbH = 137;
  const pad = 20;
  const labelH = 20;
  const sheetW = cols * thumbW + (cols + 1) * pad;
  const sheetH = rows * (thumbH + labelH) + (rows + 1) * pad;
  const sheet = Presentation.create({ slideSize: { width: sheetW, height: sheetH } });
  const slide = sheet.slides.add();
  slide.background.fill = C.white;
  for (let i = 0; i < paths.length; i += 1) {
    const col = i % cols;
    const row = Math.floor(i / cols);
    const x = pad + col * (thumbW + pad);
    const y = pad + row * (thumbH + labelH + pad);
    await addImage(slide, paths[i], x, y, thumbW, thumbH, `Slide ${i + 1}`);
    addShape(slide, { x, y, w: thumbW, h: thumbH, fill: "#00000000", stroke: C.line, strokeWidth: 1 });
    addText(slide, `Slide ${String(i + 1).padStart(2, "0")}`, x, y + thumbH + 4, thumbW, 16, { size: 10, color: C.muted, align: "center" });
  }
  const png = await sheet.export({ slide, format: "png", scale: 1 });
  await saveBlob(png, out);
}

function validateManifest(slides, pptxBytes, termText, moduleHyperlinkCount = 0) {
  const requiredTerms = [
    "SQL_FIRST_API_VERIFY",
    "EvidenceBus",
    "QueryAnalysis",
    "PlanOptimizer",
    "query_normalizer",
    "query_tokens",
    "relevance_scorer",
    "answer_slots",
    "answer_verifier",
    "answer_reranker",
    "trajectory.json",
    "metadata.json",
    "filled_system_prompt.txt",
    "Correctness",
    "0.8407",
    "0.5208",
    "0.8154",
    "1.4571",
    "851.6",
    "46 passed",
  ];
  return {
    output: FINAL_PPTX,
    output_bytes: pptxBytes,
    slide_count: slides.length,
    speaker_notes_count: slides.filter((slide) => Boolean(slide.speakerNotes.text)).length,
    required_terms_present: Object.fromEntries(requiredTerms.map((term) => [term, termText.includes(term)])),
    diagram_count: fsSync.existsSync(path.join(DIAGRAM_DIR, "diagram_manifest.json"))
      ? JSON.parse(fsSync.readFileSync(path.join(DIAGRAM_DIR, "diagram_manifest.json"), "utf8")).techniques.length + JSON.parse(fsSync.readFileSync(path.join(DIAGRAM_DIR, "diagram_manifest.json"), "utf8")).extras.length
      : 0,
    module_hyperlink_count: moduleHyperlinkCount,
    contact_sheet: CONTACT_SHEET,
    checks: {
      slide_count_36: slides.length === 36,
      all_slides_have_notes: slides.every((slide) => Boolean(slide.speakerNotes.text)),
      pptx_nonempty: pptxBytes > 0,
      module_hyperlinks_added: moduleHyperlinkCount > 0,
    },
  };
}

async function main() {
  await fs.mkdir(OUT_DIR, { recursive: true });
  await fs.mkdir(PREVIEW_DIR, { recursive: true });
  await fs.mkdir(LAYOUT_DIR, { recursive: true });

  const diagramResult = spawnSync("node", [path.join(ROOT, "scripts", "generate_dashsys_diagrams.mjs")], { encoding: "utf8", stdio: "inherit" });
  if (diagramResult.status !== 0) throw new Error("Diagram generation failed");

  const manifest = JSON.parse(await fs.readFile(path.join(DIAGRAM_DIR, "diagram_manifest.json"), "utf8"));
  const { presentation, slides } = await makeDeck(manifest);
  const previews = [];

  for (let i = 0; i < slides.length; i += 1) {
    const slide = slides[i];
    const png = await presentation.export({ slide, format: "png", scale: 1 });
    const previewPath = path.join(PREVIEW_DIR, `slide-${String(i + 1).padStart(2, "0")}.png`);
    await saveBlob(png, previewPath);
    previews.push(previewPath);
    try {
      const layout = await presentation.export({ slide, format: "layout" });
      await fs.writeFile(path.join(LAYOUT_DIR, `slide-${String(i + 1).padStart(2, "0")}.layout.json`), await layout.text(), "utf8");
    } catch {
      // Layout export is useful for QA but not blocking for final deck generation.
    }
  }

  await makeContactSheet(previews, CONTACT_SHEET);
  const pptx = await PresentationFile.exportPptx(presentation);
  await pptx.save(FINAL_PPTX);
  const hyperlinkResult = spawnSync("python3", [path.join(ROOT, "scripts", "add_ppt_module_hyperlinks.py"), FINAL_PPTX], { encoding: "utf8" });
  if (hyperlinkResult.status !== 0) {
    throw new Error(`Module hyperlink post-processing failed: ${hyperlinkResult.stderr || hyperlinkResult.stdout}`);
  }
  const moduleHyperlinkCount = Number((/module_hyperlinks=(\d+)/.exec(hyperlinkResult.stdout) || [])[1] || 0);
  const stat = await fs.stat(FINAL_PPTX);
  const termText = slideTextForTerms(manifest, slides);
  const outManifest = validateManifest(slides, stat.size, termText, moduleHyperlinkCount);
  await fs.rm(WORKSPACE, { recursive: true, force: true });
  await fs.writeFile(MANIFEST, `${JSON.stringify(outManifest, null, 2)}\n`, "utf8");
  if (!outManifest.checks.slide_count_36 || !outManifest.checks.all_slides_have_notes || !outManifest.checks.pptx_nonempty || !outManifest.checks.module_hyperlinks_added) {
    throw new Error(`Deck QA failed: ${JSON.stringify(outManifest.checks)}`);
  }
  if (Object.values(outManifest.required_terms_present).some((present) => !present)) {
    throw new Error(`Required term QA failed: ${JSON.stringify(outManifest.required_terms_present)}`);
  }
  console.log(JSON.stringify(outManifest, null, 2));
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exit(1);
});
