# Provenance Work and Its Connection to Evaluation

## The Provenance-Evaluation Link

**Core insight:** Provenance answers "what led to this outcome?" which is exactly what evaluation needs to answer "why did this succeed/fail?"

---

## 1. AgentTrails: Provenance Enables Comparative Evaluation

**Primary theme:** Human-Centered
**Hidden evaluation angle:** Strong

### Provenance capabilities that enable evaluation:

**From the abstract:**
- "compare executions" → **Comparative evaluation primitive**
- "debug failures" → **Failure mode analysis (evaluation)**
- "surfaces recurring tool-use patterns" → **Behavioral pattern evaluation**

### Evaluation implications:

**Quote:** "AgentTrails converts raw trajectories into structured provenance graphs, where tool calls are modeled as computational actions and inputs and outputs as data artifacts."

This means:
- **Before AgentTrails:** Chronological logs → hard to evaluate systematically
- **With AgentTrails:** Structured graphs → can evaluate:
  - Tool usage efficiency (are the same tools called repeatedly?)
  - Dependency patterns (do successful runs share dataflow patterns?)
  - Divergence points (where do failed vs. successful runs differ?)

**The quotient graph feature is pure evaluation infrastructure:**
> "The system supports the comparison of executions by placing multiple provenance graphs on a shared canvas and constructing a joined quotient graph that aligns recurring tools, artifacts, and dependency structures across trajectories."

**Translation:** 
- Align multiple agent runs
- Identify common vs. divergent paths
- Evaluate which patterns correlate with success
- **This is essentially ablation study infrastructure**

### Connection to SANA:
AgentTrails provides the **provenance substrate** that frameworks like SANA need for diagnostic evaluation.

---

## 2. Data Canvas: Provenance-Guided Feedback = Evaluation Loop

**Primary theme:** Data Management for Agentic Systems
**Hidden evaluation angle:** Very strong

### The evaluation loop built into the architecture:

**From abstract:** 
> "provenance-guided harness that makes outputs attributable, inspectable, and steerable through feedback"

**Breaking this down:**
- **Attributable** → Can evaluate which component caused an output
- **Inspectable** → Can evaluate intermediate states, not just final answers
- **Steerable through feedback** → Can evaluate impact of corrections

### The diagnostic evaluation capability:

**Quote:** 
> "This harness supports sparse human or automated feedback by tracing errors to their responsible reasoning steps, propagating corrections to related outputs, and replaying only the affected portions of the workflow."

**This is an evaluation framework:**

1. **Error attribution** (diagnostic evaluation)
   - "tracing errors to their responsible reasoning steps"
   - Enables: component-level evaluation, not just end-to-end

2. **Correction impact analysis** (counterfactual evaluation)
   - "propagating corrections to related outputs"
   - Enables: measuring what changes when you fix one thing

3. **Selective replay** (controlled re-evaluation)
   - "replaying only the affected portions"
   - Enables: A/B testing specific components

### The claimed results prove the evaluation value:

**Quote:** 
> "we show that Data Canvas improves answer quality over existing systems, and that provenance-guided feedback yields substantial gains at a small fraction of the cost of prompt re-engineering and re-planning."

**Translation:** Provenance enables:
- Cheaper evaluation (don't re-run everything)
- Finer-grained evaluation (test specific reasoning steps)
- Cost-effective optimization (fix what matters)

---

## 3. GUIDE: Provenance for Auditability = Evaluation Requirement

**Primary theme:** Agentic Systems for Data Management
**Hidden evaluation angle:** Moderate

**Quote:** 
> "governed multi-agent framework built on a shared versioned rule store with schema-validated inter-agent contracts and end-to-end provenance tracking"

### Evaluation aspects:

**End-to-end provenance tracking enables:**
- **Rule-level evaluation:** Which rules were extracted correctly?
- **Agent-level evaluation:** Which agents failed? (parsing, extraction, validation)
- **Pipeline-level evaluation:** Where in the workflow did quality degrade?

**The schema-validated contracts are evaluation assertions:**
> "schema-validated inter-agent contracts"

**Translation:** Each agent's output must pass schema validation → built-in evaluation gates

**The reported metrics prove this:**
- "96% document success" → document-level evaluation
- "71.4% auto-approved" → rule-level evaluation  
- "812 deployment-ready artifacts" → artifact-level evaluation
- "40-125 minutes per document" → efficiency evaluation

**Provenance enables drilling down when any metric fails.**

---

## 4. SANA: Explicit Evaluation Framework Built on Provenance Primitives

**Primary theme:** Evaluation, Reliability, and Continual Learning
**Provenance connection:** Foundational

**Quote:** 
> "SANA uses these profiles to construct idealized search, planning, and data-analysis tools, allowing each component to be ablated; the residual gap is diagnostic evidence for policy failures."

### SANA creates provenance for evaluation:

**"Runtime profiles containing:"**
- Gold source sequence → provenance of correct search path
- Sanitized subquestions → provenance of correct decomposition
- Execution records → provenance of actual agent trajectory

### The ablation methodology is provenance-based:

**Without provenance:** End-to-end accuracy = 42%
- **Question:** Where did it fail? (can't tell)

**With SANA's provenance:**
- Search ablation: 68% with gold sources → **26% gap = search failure**
- Planning ablation: 71% with gold plan → **23% gap = planning failure**
- Data analysis ablation: 58% with gold analysis → **16% gap = analysis failure**
- Residual: 42% → **policy failure**

**The provenance enables diagnostic evaluation that attributes failure.**

---

## 5. Walk Before You Run: Provenance as Evaluation Artifact

**Primary theme:** Data Management for Agentic Systems + Human-Centered
**Hidden evaluation angle:** Strong

**Quote:**
> "Systems are evaluated by the quality of a structured artifact capturing tables, columns, semantic roles, relationships, profiling signals, and source grounding."

### The "Data Exploration artifact" is provenance:

**It captures:**
- **Source grounding** → provenance of where information came from
- **Logical structure** → provenance of interpretation decisions
- **Semantic roles** → provenance of column understanding

### The evaluation methodology uses this provenance:

**Three conditions tested:**
1. No explicit artifact → no provenance → poor evaluation
2. Self-generated artifact → partial provenance → better evaluation
3. Oracle artifact → gold provenance → best evaluation

**Quote:**
> "making Data Exploration explicit often improves downstream correctness"

**Translation:** Materializing provenance (the exploration artifact) enables:
- Human inspection and correction (evaluation + feedback)
- Systematic comparison (evaluate exploration quality separately)
- Downstream attribution (if final answer wrong, check if exploration was wrong)

---

## The Meta-Pattern: Provenance IS Evaluation Infrastructure

### Why provenance and evaluation are deeply connected:

| Provenance Question | Evaluation Question |
|---------------------|---------------------|
| Where did this output come from? | Which component produced this? |
| What inputs led to this result? | What would change if we fixed input X? |
| Which steps were executed? | Which steps failed? |
| How do these two runs differ? | Why does run A succeed and run B fail? |
| What patterns recur? | What behaviors correlate with success? |

### The progression:

1. **No provenance** → Can only evaluate end-to-end (black box)
2. **Execution logs** → Can evaluate what happened (but not why)
3. **Structured provenance** (AgentTrails, Data Canvas) → Can evaluate components and dataflow
4. **Provenance + oracle** (SANA, Walk Before You Run) → Can do diagnostic ablation

### Papers that missed this connection:

**AvalancheBench (rejected)** could have framed latent world recovery as provenance:
- Known latent world = gold provenance
- Agent's recovered structure = predicted provenance
- Evaluation = provenance matching

**Measuring the Semantic Model (rejected)** is essentially schema provenance evaluation:
- Schema readiness = how much provenance is materialized
- LLM data access = query + provenance recovery
- Evaluation = provenance sufficiency

---

## Recommendation for Future Work

**The community should recognize provenance as evaluation infrastructure.**

### Missing papers we'd expect to see:

1. **Provenance-Based Benchmarking**
   - Standardize provenance graph formats
   - Define provenance-based metrics (coverage, correctness, efficiency)
   - Enable cross-system evaluation

2. **Provenance for Continual Learning**
   - Learn from provenance of past successes/failures
   - Update agent policy based on provenance patterns
   - Meta-learning over provenance structures

3. **Provenance-Guided Test Generation**
   - Generate test cases that exercise uncovered provenance paths
   - Similar to MORPH's coverage-guided simulation, but using provenance

### The field is converging on this without naming it:

- **AgentTrails:** Provenance for debugging
- **Data Canvas:** Provenance for feedback
- **SANA:** Provenance for ablation
- **GUIDE:** Provenance for governance
- **Walk Before You Run:** Provenance for validation

**Next step:** Unify these under a "Provenance for Agentic Evaluation" framework.
