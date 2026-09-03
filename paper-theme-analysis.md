# DASHSys 2026: Accepted Papers Theme Analysis

## Workshop Themes
1. **Data Management for Agentic Systems**
2. **Agentic Systems for Data Management**
3. **Evaluation, Reliability, and Continual Learning**
4. **Human-Centered and Human-in-the-Loop Agentic Systems**

---

## Theme Distribution

### Theme 1: Data Management for Agentic Systems (5 papers)

**Long Papers:**
- **Walk Before You Run: The Importance of Data Exploration for Data Analysis Agents**
  - *Key insight:* Makes data exploration an explicit, first-class stage in LLM workflows
  - *Data management angle:* Introduces structured artifacts for capturing tables, columns, relationships, and profiling signals
  - *Human-in-loop:* Creates natural checkpoints where domain experts can review dataset understanding
  - *Primary Subject Area:* Data Management for Agentic Systems
  
**Short Papers:**
- **GitLake: Git-for-Data for the Agentic Lakehouse**
  - *Key insight:* Lifts single-table snapshots into lakehouse-wide commits, branches, and merges
  - *Data management angle:* Enables agents to work on isolated branches with atomic publication
  - *Human-in-loop:* Humans review and publish changes through merge workflows
  - *Keywords:* agentic data systems; lakehouse; Git-for-data; human-in-the-loop review

- **Structured State Management for Agentic Data Pipelines**
  - *Key insight:* Each step accesses only specific needed data; outputs checked before saving
  - *Data management angle:* Bounded context and schema contracts reduce retry costs by 73.2%
  - *Innovation:* Selective recovery - only failed steps are redone
  - *Keywords:* Agentic Data Pipelines, Structured State Management, LLM Agents

- **Data Canvas: A Provenance-Guided Harness for Agentic Data Engineering**
  - *Key insight:* Wraps LLM execution with structured semantic operators and provenance graphs
  - *Data management angle:* Makes outputs attributable, inspectable, and steerable through feedback
  - *Innovation:* Traces errors to responsible steps, propagates corrections, replays affected portions
  - *Keywords:* Agentic Systems, Tool-augmented Language Models, Data Integration

---

### Theme 2: Agentic Systems for Data Management (3 papers)

**Long Papers:**
- **ASMR: Agentic Schema Generation for Ship Maintenance Report Writing**
  - *Key insight:* Multi-agent framework for automatic schema generation from historical reports
  - *Agent architecture:* Field Generation Agent + Structural Optimizer Agent (RL-based)
  - *Application:* Guides report authors toward complete, consistent, actionable reports
  - *Keywords:* Agentic AI, Schema Generation, Reinforcement Learning, Human-AI Collaboration

**Short Papers:**
- **Utilizing LLM-based Multi-agent Framework for Pipelining Complex Data Discovery Tasks**
  - *Key insight:* Vision paper for LLM-based multi-agent system for data lake discovery
  - *Challenge:* Supporting complex tasks requiring multiple operations
  - *Contribution:* Discusses challenges and potential design choices for different agents
  - *Keywords:* data discovery, large language model, multi-agent system

- **GUIDE: Governed Unified Intelligence for Document-to-Artifact Generation**
  - *Key insight:* Six specialized agents with shared versioned rule store and schema-validated contracts
  - *Performance:* 96% document success, 71.4% auto-approved rules, 40-125 min turnaround
  - *Innovation:* Handles parsing, VLM extraction, consistency checking, HITL escalation, artifact synthesis
  - *Keywords:* Governed multi-agent systems, VLM-based information extraction, Schema-validated provenance

---

### Theme 3: Evaluation, Reliability, and Continual Learning (1 paper)

**Long Papers:**
- **SANA: What Matters for QA Agents over Massive Data Lakes?**
  - *Key insight:* Diagnostic ablation framework that deconstructs end-to-end accuracy
  - *Innovation:* Separates failures in search, planning, data analysis, and action policy
  - *Method:* Constructs idealized tools for each component to identify bottlenecks
  - *Finding:* Data analysis is consistent bottleneck; search major in large lakes
  - *Keywords:* Data-Centric Agents; Exploratory Question Answering; Agent Evaluation; Ablation Framework

---

### Theme 4: Human-Centered and Human-in-the-Loop Agentic Systems (5 papers)

**Long Papers:**
- **Toward Resource Rational Dataset Search Interfaces**
  - *Key insight:* Dataset evaluation is selective, task-conditioned, and cost-sensitive
  - *Human study:* Survey (N=41), interviews (N=10), secondary analysis (N=36)
  - *Finding:* Workers screen candidates, escalate effort when uncertainty matters
  - *Design implication:* Interfaces should align checking cost with evidence needed
  - *Keywords:* Data Discovery, Information Needs, Large Language Models, HCI

**Short Papers:**
- **Be Fair! Can Machine Learning Engineering Agents Adhere to Fairness Constraints?**
  - *Key insight:* Responsibility gap in ML automation for sensitive domains
  - *Finding:* Agent pipelines show high variance, underperform baselines on fairness
  - *Contribution:* Responsibility-centered evaluation framework
  - *Keywords:* machine learning engineering agents; fairness; responsibility-centric evaluation

- **AgentTrails: Towards Trust and Reuse for Agentic Tasks**
  - *Key insight:* Converts chronological logs into structured provenance graphs
  - *Innovation:* Reveals dataflow dependencies between actions and artifacts
  - *Use cases:* Compare executions, debug failures, reuse computations, extract patterns
  - *Keywords:* Provenance, LLM Agents, Visual Analytics

- **Querying with Conflicts of Interest**
  - *Key insight:* Data sources may return biased answers due to conflicting incentives
  - *Innovation:* Query reformulation algorithms to increase relevant information
  - *Application:* E.g., product search biased toward revenue vs. user preference
  - *Keywords:* multi-agent interaction, database querying, game theory, user interaction

---

## Cross-Cutting Themes

Several papers span multiple themes:

**Data Management + Human-in-Loop:**
- Walk Before You Run (explicit checkpoints for domain experts)
- GitLake (human review and publication gates)
- Data Canvas (provenance-guided feedback)

**Agentic Systems + Human-in-Loop:**
- ASMR (human-AI collaboration)
- GUIDE (HITL escalation)

**Evaluation + Human-Centered:**
- SANA (diagnostic framework reveals where human oversight needed)
- Toward Resource Rational Interfaces (understanding human evaluation behavior)

---

## Key Observations

### 1. **Strong Emphasis on Human-in-the-Loop (7/12 papers)**
   - Even papers primarily about data/agent infrastructure include HITL components
   - Reflects maturity: community recognizes agents need human oversight, not full autonomy

### 2. **Data Management Infrastructure is Foundation (5/12 papers)**
   - GitLake, Structured State Management, Data Canvas provide the "plumbing"
   - Walk Before You Run argues for data exploration as first-class primitive
   - These enable reliable agent operation

### 3. **Under-Represented: Pure Evaluation (1/12 papers)**
   - Only SANA directly addresses evaluation methodology
   - Most papers include evaluation sections but don't advance evaluation science
   - Gap: Limited work on benchmarking, reliability metrics, continual learning

### 4. **Multi-Agent Architectures Dominant**
   - ASMR (2 agents), GUIDE (6 agents), LLM Multi-agent Framework
   - Trend toward specialized agents vs. monolithic systems

### 5. **Provenance and Observability Emerge as Core Concerns**
   - AgentTrails (provenance graphs)
   - Data Canvas (provenance-guided harness)
   - GUIDE (end-to-end provenance tracking)
   - Critical for trust, debugging, and reuse

### 6. **Fairness and Responsibility Enter the Conversation**
   - Be Fair! (fairness constraints)
   - Toward Fairness-Aware Human Feedback (rejected, but shows community interest)
   - Querying with Conflicts of Interest (bias in data sources)

---

## Research Gaps (Based on Accepted vs. Rejected)

**What got accepted:**
- Concrete systems with measurable improvements
- Clear human-centered design
- Strong evaluation on real-world datasets
- Provenance and observability

**What got rejected (but interesting):**
- Pure benchmarks without systems (AvalancheBench)
- Safety mechanisms without deployment validation (Sentri)
- Schema-side evaluation (Measuring the Semantic Model)
- Testing frameworks (MORPH)

**Implication:** Workshop favors working systems over frameworks/benchmarks alone.

---

## Thematic Coherence

The accepted papers tell a coherent story:

1. **Infrastructure Layer** (GitLake, Structured State Management, Data Canvas)
   → Build reliable data substrates for agents

2. **Agent Design** (ASMR, GUIDE, Multi-agent Framework)
   → How to architect agentic systems

3. **Human-Agent Collaboration** (Walk Before You Run, Resource Rational Interfaces, Be Fair!, AgentTrails, Conflicts of Interest)
   → How humans and agents work together

4. **Evaluation** (SANA)
   → How to measure what matters

This progression mirrors the maturity arc: infrastructure → design patterns → collaboration models → rigorous evaluation.
