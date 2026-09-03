# Theme Cross-Pollination Analysis: DASHSys 2026

## The Power of Theme-Theme Heatmaps

**Why this matters:** Unlike a paper-theme matrix (which shows *what* themes each paper touches), a theme-theme co-occurrence matrix shows **how themes work together** - revealing the field's emergent structure.

---

## 🔥 Top 3 Strongest Theme Pairs

### 1. **Data Management ↔ Infrastructure (8 co-occurrences)**
**The Foundation Layer**

**Papers bridging these themes:**
- GitLake (2+2)
- Walk Before You Run (2+1)
- Structured State Management (2+2)
- Data Canvas (2+1)

**Why this matters:**
- Data management papers ARE infrastructure papers
- Can't have agents without reliable data substrates
- **Insight:** The field recognizes data infrastructure as prerequisite to agent deployment

**Example integration:**
> "GitLake lifts single-table snapshots into lakehouse-wide commits" - Data management implemented as infrastructure primitive

---

### 2. **HITL ↔ Provenance (6 co-occurrences)**
**The Trust & Transparency Cluster**

**Papers bridging these themes:**
- AgentTrails (2+2) - Provenance FOR human understanding
- Walk Before You Run (2+1) - Human checkpoints NEED provenance artifacts
- Data Canvas (0+2) - Provenance-guided feedback loop
- GUIDE (1+1) - End-to-end provenance for HITL escalation

**Why this matters:**
- Humans can't review agent behavior without provenance
- Provenance enables trust, which enables delegation
- **Insight:** HITL and Provenance are co-dependent, not separate concerns

**The dependency:**
```
Human oversight requires → Provenance (to understand what happened)
Provenance enables → Better human oversight
```

---

### 3. **Agentic Systems ↔ Multi-Agent (6 co-occurrences)**
**The Architecture Consensus**

**Papers bridging these themes:**
- ASMR (2+1) - 2 specialized agents
- GUIDE (2+1) - 6 specialized agents  
- Multi-agent Framework (2+1) - Vision for multi-agent data discovery

**Why this matters:**
- When building agentic systems, community defaults to multi-agent
- NOT: "One smart agent to rule them all"
- **Insight:** Specialization > Generalization for production systems

**The pattern:**
- Monolithic agent → Hard to debug, hard to improve
- Multi-agent → Each component testable, each failure attributable

---

## 📊 Cross-Pollination Tiers

### **Tier 1: Tight Integration (6-8 co-occurrences)**
These theme pairs almost always appear together:

1. **Data Mgmt + Infrastructure** (8)
   - *Relationship:* Identity - they're the same thing
   
2. **HITL + Provenance** (6)
   - *Relationship:* Co-dependency - can't have one without the other
   
3. **Agentic Systems + Multi-Agent** (6)
   - *Relationship:* Implementation pattern - how to build agents

---

### **Tier 2: Strong Bridges (4 co-occurrences)**
These pairs frequently work together:

4. **Data Mgmt + HITL** (4)
   - Walk Before You Run, GitLake
   - *Pattern:* Data infrastructure with human review gates

5. **Data Mgmt + Provenance** (4)
   - Data Canvas, Walk Before You Run
   - *Pattern:* Data operations need provenance for debugging

6. **Agentic Systems + HITL** (4)
   - ASMR, GUIDE
   - *Pattern:* Agent design includes human escalation from start

7. **HITL + Infrastructure** (4)
   - GitLake (human review), Structured State (human checkpoints)
   - *Pattern:* Infrastructure provides the hooks for human oversight

8. **HITL + Multi-Agent** (4)
   - GUIDE, ASMR
   - *Pattern:* Multi-agent systems delegate different roles to humans

9. **Infrastructure + Provenance** (4)
   - Data Canvas, Walk Before You Run
   - *Pattern:* Infrastructure that's observable and debuggable

---

### **Tier 3: Weak/Missing Connections (0-2 co-occurrences)**

10. **Evaluation + [Everything]** (0-1 each)
    - Only connects to Provenance (1) via SANA
    - **Gap Insight:** Evaluation is isolated, not integrated

11. **Data Mgmt + Agentic Systems** (0)
    - **Surprising!** These should bridge more
    - Papers choose one side or the other, not both
    - **Gap:** Need more papers that design data systems FOR agents

12. **Agentic Systems + Infrastructure** (0)
    - Similar to above
    - **Gap:** Agent architectures don't talk to infrastructure

---

## 🎯 What Theme Isolation Scores Reveal

### **Most Connected Themes:**

**1. HITL (11 connections)** - The Universal Connector
- Touches EVERY other theme except Evaluation
- Appears in: Data Mgmt papers, Agentic papers, Infrastructure papers
- **Insight:** HITL is not a niche - it's a cross-cutting requirement

**2. Provenance (10 connections)** - The Integration Layer
- Connects to all themes except (ironically) nothing
- Bridges Data ↔ HITL, Infrastructure ↔ Evaluation
- **Insight:** Provenance is the glue between subsystems

**3. Data Mgmt (8 connections)** & **Infrastructure (8 connections)** - The Foundation
- Tied score because they're essentially the same cluster
- Strong internal coherence
- **Insight:** Mature, self-contained research area

---

### **Moderately Connected:**

**4. Agentic Systems (6 connections)** & **Multi-Agent (6 connections)**
- Form their own tight cluster
- Connect to HITL and Provenance, but NOT to Data/Infrastructure
- **Gap:** Agent research isn't talking to data infrastructure research

---

### **Isolated Theme:**

**5. Evaluation (1 connection)** - The Lone Wolf
- Only connects to Provenance via SANA
- **Critical Gap:** Evaluation is an afterthought, not integrated into design
- **Opportunity:** Papers that evaluate Infrastructure, HITL, or Multi-Agent designs

---

## 🔍 Network Analysis: Clusters & Gaps

### **Cluster 1: Data Infrastructure** (Tightly Connected)
```
Data Management ←→ Infrastructure ←→ Provenance
       ↓                ↓               ↓
      HITL ←----------→ HITL ←--------→ HITL
```
**Character:** Mature, integrated research area
**Papers:** GitLake, Structured State, Data Canvas, Walk Before You Run

---

### **Cluster 2: Agent Architectures** (Moderately Connected)
```
Agentic Systems ←→ Multi-Agent
       ↓                ↓
      HITL ←----------→ HITL
       ↓                ↓
   Provenance ←-----→ Provenance
```
**Character:** Emerging design patterns
**Papers:** ASMR, GUIDE, Multi-agent Framework

---

### **Island: Evaluation** (Isolated)
```
        [Cluster 1]    [Cluster 2]
             ↓              ↓
         Provenance ←---→ Provenance
                 ↓
             Evaluation (SANA only)
```
**Character:** Disconnected from main clusters
**Papers:** SANA (alone)

---

## 💡 Research Gaps Revealed by Cross-Pollination

### **Missing Bridge 1: Data Mgmt ↔ Agentic Systems (0 co-occurrences)**

**The Gap:**
- Data Management papers don't design FOR agents
- Agentic Systems papers don't engage with data infrastructure

**What's missing:**
- "How should data systems change to support agentic workloads?"
- "What data primitives do agents need?"
- "Benchmarking data systems under agentic access patterns"

**Potential paper titles:**
- "Agent-Aware Data Layouts"
- "Indexing for Iterative Agent Queries"
- "Data Systems for Uncertain Agentic Workloads"

---

### **Missing Bridge 2: Evaluation ↔ [Everything] (isolated)**

**The Gap:**
- Evaluation is not integrated into system design
- Systems built first, evaluated later (if at all)

**What's missing:**
- "Evaluation-Driven Design for Multi-Agent Systems"
- "HITL Evaluation Frameworks"
- "Continuous Evaluation for Data Infrastructure"

**Potential paper titles:**
- "Test-Driven Development for Agentic Data Systems"
- "Evaluation as a First-Class Design Constraint"
- "Benchmarks for Human-Agent Collaboration Quality"

---

### **Weak Bridge: Infrastructure ↔ Multi-Agent (0 co-occurrences)**

**The Gap:**
- Multi-agent architectures don't discuss infrastructure requirements
- Infrastructure papers don't optimize for multi-agent patterns

**What's missing:**
- "Infrastructure for Multi-Agent Coordination"
- "Scalable Communication Substrates for Agent Swarms"
- "Provenance Tracking Across Agent Boundaries"

---

## 🎨 Visualization Recommendations

### **1. Symmetric Heatmap** (Best for Co-occurrence Matrix)

**What to show:**
- 7×7 matrix (themes × themes)
- Diagonal = 0 (self-connections excluded)
- Color intensity = co-occurrence count
- Annotate cells with numbers

**What it reveals at a glance:**
- Dark clusters = tight integration
- White cells = gaps
- Asymmetries = directional dependencies (rare here)

**Color scheme:**
- White (0) → Light Blue (1-2) → Blue (3-4) → Dark Blue (5-6) → Navy (7-8)

---

### **2. Chord Diagram** (Best for Showing Flow)

**What to show:**
- Themes as arcs around a circle
- Connections as ribbons between themes
- Ribbon width = co-occurrence count

**What it reveals at a glance:**
- Which themes are hubs (HITL, Provenance)
- Which are isolated (Evaluation)
- Cluster structure (Data+Infra, Agentic+Multi)

**Visual impact:** Beautiful, intuitive, shareable

---

### **3. Network Graph** (Best for Cluster Detection)

**What to show:**
- Themes as nodes (sized by total connections)
- Edges between themes (thickness = co-occurrence)
- Layout algorithm clusters connected themes

**What it reveals:**
- Cluster 1: Data/Infrastructure/Provenance
- Cluster 2: Agentic/Multi-Agent
- Hub: HITL (connects clusters)
- Island: Evaluation

**Insight:** Literally shows the field's structure

---

### **4. Alluvial Diagram with Theme-Theme Layer** (Best for Complete Story)

**Three layers:**
1. Papers (12)
2. Primary Themes (4)
3. Theme Pairs (top 9)

**What it reveals:**
- Which papers contribute to which cross-pollination
- How primary themes aggregate into pairs
- The path from individual work to field structure

---

## 📈 Quantitative Insights

### **Connectivity Distribution:**
```
Theme              Connections    Connectedness
HITL                    11           157% of average
Provenance              10           143% of average
Data Mgmt                8           114% of average
Infrastructure           8           114% of average
Agentic Systems          6            86% of average
Multi-Agent              6            86% of average
Evaluation               1            14% of average
──────────────────────────────────────────────────
Average:                7.1 connections
```

**Interpretation:**
- HITL and Provenance are 50%+ above average connectivity
- Evaluation is 86% BELOW average - severe isolation

---

### **Cluster Density:**

**Cluster 1 (Data Infrastructure):**
- Nodes: Data Mgmt, Infrastructure, Provenance, HITL
- Possible connections: 6 pairs
- Actual connections: 4 strong (≥4) + 2 moderate
- **Density: 100%** (fully connected)

**Cluster 2 (Agent Architectures):**
- Nodes: Agentic Systems, Multi-Agent, HITL, Provenance
- Possible connections: 6 pairs
- Actual connections: 3 strong + 2 moderate
- **Density: 83%** (well connected)

**Evaluation:**
- Connections to other clusters: 1 (to Provenance only)
- **Density: 14%** (nearly isolated)

---

## 🚀 Strategic Implications

### **For Workshop Organizers:**

**Encourage bridge papers:**
- Offer "Bridge Paper" award for best cross-theme work
- Explicitly solicit papers at theme intersections
- Create "gap analysis" session

**Target missing bridges:**
- Issue special call for "Data Mgmt ↔ Agentic Systems" papers
- Invite keynote on "Evaluation-Driven Design"
- Panel: "Infrastructure for Multi-Agent Systems"

---

### **For Researchers:**

**High-impact opportunities:**
1. **Data Systems FOR Agents** (missing bridge)
2. **Integrated Evaluation** (isolated theme)
3. **Multi-Agent Infrastructure** (weak bridge)

**Safe bets (established clusters):**
1. Data Infrastructure + HITL + Provenance
2. Multi-Agent + HITL

---

## 🎯 The Takeaway

**Theme co-occurrence reveals the field's hidden structure:**

✅ **Strong clusters:**
- Data/Infrastructure/Provenance (the foundation)
- Agentic/Multi-Agent (the architecture)

✅ **Universal connectors:**
- HITL (bridges everything)
- Provenance (integration layer)

⚠️ **Critical gaps:**
- Evaluation is isolated
- Data ↔ Agent systems don't talk
- Infrastructure ↔ Multi-Agent missing

**The thesis:** 
*Cross-pollination patterns reveal not just what papers were accepted, but how the field is structuring itself. Gaps in co-occurrence are research opportunities.*
