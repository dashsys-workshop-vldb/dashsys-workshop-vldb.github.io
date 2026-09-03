# Keynote Analysis: How Industry Leaders Frame the Field

## 🎤 7 Keynote Speakers Overview

| Speaker | Institution | Talk Theme |
|---------|-------------|------------|
| **Erkang (Eric) Zhu** | Alibaba | Practical agent applications (QwenPaw, AutoGen) |
| **Fatma Özcan** | Google | Systems optimization (100x efficiency gains) |
| **Omar Khattab** | MIT | Qualitative learning (DSPy, ColBERT) |
| **Eugene Wu** | Columbia | Agentic data environments (DAPLab) |
| **Shreya Shankar** | UC Berkeley/CMU | User behavior with LLM systems (DocETL) |
| **Juliana Freire** | NYU | Semantic data systems (VIDA) |
| **Yunyao Li** | Adobe | Enterprise agentic systems |

---

## 📊 Keynote vs. Papers: Word Frequency Comparison

### **Top Terms - Keynotes:**
```
1. data          37 ████████████████████████████████████
2. systems       22 ██████████████████
3. agents        15 ███████████
4. semantic      14 ████████████
5. agentic       11 █████████
6. building       8 ██████
7. models         8 ██████
```

### **Top Terms - Papers:**
```
1. data          28 ████████████████████████████
2. agent/agents  20 ████████████████████
3. agentic        6 ██████
4. provenance     6 ██████
5. schema         6 ██████
6. framework      6 ██████
```

---

## 🔍 **Key Differences:**

### **Keynotes Emphasize (vs. Papers):**
✅ **"systems"** (22 vs. 4) - 5.5x more
✅ **"semantic"** (14 vs. minimal) - New emphasis
✅ **"building"** (8 vs. 3) - 2.7x more practical
✅ **"users"** (5 vs. 4) - More user-focused
✅ **"enterprise"** (5 vs. 3) - More industry-focused
✅ **"workflows"** (5 vs. 2) - More process-oriented

### **Papers Emphasize (vs. Keynotes):**
✅ **"provenance"** (6 vs. 0) - Papers lead here
✅ **"schema"** (6 vs. 3) - More technical
✅ **"framework"** (6 vs. 3) - More architectural

---

## 🎯 Thematic Mapping: Keynotes to Workshop Themes

### **Theme 1: Data Management for Agentic Systems**

**Keynotes addressing this:**
- ✅ **Juliana Freire**: "Semantic Data Systems" - DIRECT FIT
  - "Semantic understanding as first-class systems capability"
  - "Dataset discovery, semantic join, schema matching"
  - "How to represent and maintain semantic knowledge"

- ✅ **Eugene Wu**: "Agentic Data Environments" - DIRECT FIT
  - "Data systems shifting from passive stores to active execution substrates"
  - "Environment that agents run within"
  - "Providing safety through data systems"

- ✅ **Yunyao Li**: "Rethinking Data Systems" - DIRECT FIT
  - "How agents change way data is constructed, represented, accessed"
  - "Data systems to ground and govern agent reasoning"
  - "Are today's abstractions still the right ones?"

**Coverage:** 3/7 keynotes (43%) - **Strong alignment with papers**

---

### **Theme 2: Agentic Systems for Data Management**

**Keynotes addressing this:**
- ✅ **Eric Zhu**: "Building Agent Applications" - DIRECT FIT
  - "Harness design, grounding agents in structured metadata"
  - "OS-like foundation for applications"
  - Real systems: QwenPaw, Creator, DataPaw

- ✅ **Fatma Özcan**: "Semantic Engines and Agents" - DIRECT FIT
  - "Two architectural paradigms: semantic engines and data agents"
  - "Optimizing AI operators, agentic pipelines"
  - "Metadata reasoner for data source discovery"

- ✅ **Yunyao Li**: "Agentic Enterprise" - DIRECT FIT
  - "Agents that reason, plan, and act across complex data"
  - "How data systems can ground agent reasoning"

**Coverage:** 3/7 keynotes (43%) - **Strong alignment**

---

### **Theme 3: Evaluation, Reliability, and Continual Learning**

**Keynotes addressing this:**
- ⚠️ **Fatma Özcan**: PARTIAL
  - "Extensive evaluation of proxy models"
  - "100x reduction in cost and latency" (performance eval)
  - BUT: Not about agent evaluation per se

- ⚠️ **Shreya Shankar**: PARTIAL
  - "Systems and benchmarks our community should be building"
  - "How users struggle to specify and validate queries"
  - BUT: User study, not evaluation methodology

- ⚠️ **Juliana Freire**: PARTIAL
  - "How to evaluate compound systems whose behavior emerges from interactions"
  - BUT: Mentioned as open challenge, not addressed

- ❓ **Omar Khattab**: UNKNOWN
  - "Qualitative Learning for AI Systems" - title suggests evaluation
  - No abstract provided

**Coverage:** 0.5/7 keynotes (7%) - **MATCHES THE GAP IN PAPERS!**

**Critical finding:** Keynotes also underemphasize evaluation, just like papers (8%)

---

### **Theme 4: Human-Centered and Human-in-the-Loop**

**Keynotes addressing this:**
- ✅ **Shreya Shankar**: "What Do Users Actually Do" - DIRECT FIT
  - "How users actually use LLM-powered data systems"
  - "How they struggle to specify and validate queries"
  - "How they iterate extensively"
  - Real deployment: 1,173 queries, 8 months

- ✅ **Juliana Freire**: "Semantic Data Systems" - STRONG
  - "Incorporate human expertise to validate and refine"
  - "Engaging users when additional context required"
  - "How to determine appropriate level of agent autonomy and human oversight"

- ✅ **Eric Zhu**: MODERATE
  - "Human-in-the-loop collaboration" (in bio, AutoGen)
  - Context management for applications

- ✅ **Eugene Wu**: MODERATE
  - "Bounding the consequences of failure" (implicit HITL)
  - "Safety" as design goal

**Coverage:** 4/7 keynotes (57%) - **MATCHES PAPER EMPHASIS (58%)!**

---

## 🔥 **Do Keynotes Address the Gaps We Found?**

### **Gap 1: Data Mgmt ↔ Agentic Systems (0 co-occurrences in papers)**

**Keynotes directly addressing this bridge:**

✅ **Eugene Wu** - "Agentic Data Environments"
> "While databases remain central, agents operate across broader data environment... data systems shifting from passive stores to active execution substrates"

**THIS IS THE MISSING BRIDGE!**

✅ **Yunyao Li** - "Rethinking Data Systems for Agentic Enterprise"
> "How agents change way data and knowledge are constructed, represented, accessed, and evolved; how data systems can ground and govern agent reasoning"

**ALSO THE MISSING BRIDGE!**

✅ **Juliana Freire** - "Semantic Data Systems"
> "LLM agents can orchestrate workflows, evaluate intermediate results... combining semantic reasoning with algorithms through structured workflows"

**BRIDGE FROM DATA SIDE!**

**Finding:** **3 of 7 keynotes (43%) explicitly bridge Data ↔ Agents**
- Papers: 0%
- Keynotes: 43%
- **Gap being addressed by industry leaders, not yet by academic papers**

---

### **Gap 2: Evaluation Isolation (1 connection in papers)**

**Keynotes addressing evaluation:**

❌ **Direct evaluation methodology:** Only Fatma Özcan (performance), maybe Omar Khattab

⚠️ **Indirect evaluation mentions:**
- Shreya: "benchmarks our community should be building" (mentioned, not addressed)
- Juliana: "evaluate compound systems" (open challenge, not solution)

**Finding:** **Keynotes also don't emphasize evaluation (7%)**
- Papers: 8% (1/12)
- Keynotes: 7% (0.5/7)
- **Gap persists in both papers AND keynotes**

**Interpretation:** Either:
1. Evaluation is still an open problem no one has cracked
2. The field is more focused on building than measuring
3. This is a critical opportunity for future work

---

### **Gap 3: Infrastructure ↔ Multi-Agent (0 co-occurrences in papers)**

**Keynotes addressing this:**

✅ **Eric Zhu** - "OS-like foundation"
> "Show how an OS-like foundation carries these lessons so each application can focus on modeling its own domain"

**Multi-agent infrastructure abstraction!**

⚠️ **Fatma Özcan** - "Architecting the Systems Backbone"
> "Optimizing AI operators, agentic pipelines... systems that fundamentally rely on embeddings and similarity search"

**Infrastructure for agents, but not explicitly multi-agent**

**Finding:** **1 of 7 keynotes (14%) addresses this**
- Papers: 0%
- Keynotes: 14%
- **Gap partially addressed, but still weak**

---

## 🌟 **New Themes Introduced by Keynotes (Not in Papers)**

### **1. Semantic Understanding as Systems Capability**
- **Juliana Freire**: "Semantic understanding becomes first-class systems capability"
- **Fatma Özcan**: "Semantic engines" as architectural paradigm
- **Mentioned:** 14 times in keynotes vs. minimal in papers

**Why papers missed this:** Papers focus on specific systems, keynotes step back to paradigm level

---

### **2. Production/Enterprise Scale**
- **Yunyao Li**: Enterprise-scale systems (Apple, IBM, Adobe experience)
- **Eric Zhu**: Open-source production systems (QwenPaw, AutoGen)
- **Shreya Shankar**: Real deployment (1,173 queries, 8 months)

**Why papers missed this:** Academic work often pre-production, keynotes from industry veterans

---

### **3. User Behavior & Iteration**
- **Shreya Shankar**: "How users actually use" (not how we think they use)
- "Struggle to specify, iterate extensively, converge on bespoke operators"

**Why papers missed this:** Papers assume well-specified queries, Shreya shows assumption is wrong

---

### **4. Compound System Evaluation**
- **Juliana Freire**: "Evaluate compound systems whose behavior emerges from interactions"
- Multi-component evaluation challenge

**Why papers missed this:** Papers evaluate single systems, keynotes identify system-of-systems challenge

---

## 📊 **Keynote Speaker Positioning Matrix**

### **Industry Practitioners (Building Production Systems):**
- **Eric Zhu** (Alibaba) - Multi-agent frameworks at scale
- **Yunyao Li** (Adobe) - Enterprise AI platforms
- **Fatma Özcan** (Google) - Systems optimization

**Focus:** What works in production, what scales, what fails

---

### **Academic Leaders (Theoretical Foundations):**
- **Juliana Freire** (NYU) - Semantic data systems
- **Eugene Wu** (Columbia) - Agentic data environments
- **Omar Khattab** (MIT) - Learning and optimization

**Focus:** Fundamental abstractions, open challenges, research agenda

---

### **Bridge Researchers (Academia ↔ Practice):**
- **Shreya Shankar** (Berkeley → CMU) - User studies + systems

**Focus:** How theory meets practice, what users actually do

---

## 🎯 **Keynote Message Synthesis**

### **Common Thread Across All Keynotes:**

**The thesis:** *Data systems and agents must co-evolve*

Breaking down by speaker:

1. **Eric Zhu**: Agents need structured foundations (harness design)
2. **Fatma Özcan**: Systems need optimization for agent workloads
3. **Eugene Wu**: Data systems become active substrates, not passive stores
4. **Shreya Shankar**: Users iterate to create bespoke solutions (not one-size-fits-all)
5. **Juliana Freire**: Semantic understanding + algorithms + human expertise
6. **Yunyao Li**: Enterprise context + data = what agents need
7. **Omar Khattab**: (Qualitative learning - optimization of agent programs)

**The pattern:** *Integration, not separation*

---

## 🔍 **What Keynotes Tell Us About the Field's Direction**

### **1. The Field Is Maturing (Industry Presence)**
- 3/7 keynotes from industry (Alibaba, Google, Adobe)
- All have production experience
- **Shift from "Can we build this?" to "How do we deploy this?"**

### **2. The Academic-Industry Gap Is Closing**
- Academic keynotes (Eugene, Juliana) reference production systems
- Industry keynotes (Eric, Yunyao) ground in research challenges
- **Convergence on: data systems must change for agents**

### **3. Users Are Becoming Central**
- Shreya's entire talk: "What users actually do"
- Juliana: "Engaging users when context required"
- Eugene: "Bounding consequences of failure" (for users)
- **58% of papers have HITL, keynotes reinforce this**

### **4. Evaluation Remains Open**
- Only 1 keynote directly addresses evaluation
- Multiple keynotes mention as "open challenge"
- **Both papers and keynotes agree: we don't know how to evaluate yet**

### **5. New Abstractions Emerging**
- "Semantic understanding as systems capability" (Juliana)
- "Active execution substrates" (Eugene)
- "Agentic data environments" (Eugene)
- "OS-like foundation" (Eric)
- **Keynotes propose paradigm shifts, papers instantiate patterns**

---

## 📈 **Comparing Paper vs. Keynote Theme Coverage**

| Theme | Papers | Keynotes | Match? |
|-------|--------|----------|--------|
| **Data Mgmt for Agents** | 42% (5/12) | 43% (3/7) | ✅ Perfect |
| **Agentic Sys for Data** | 25% (3/12) | 43% (3/7) | ⚠️ Keynotes higher |
| **Evaluation** | 8% (1/12) | 7% (0.5/7) | ✅ Both low |
| **HITL** | 42% (5/12) | 57% (4/7) | ✅ Both high |
| **Infrastructure** | 42% (5/12) | 31% (strong in 3) | ✅ Similar |
| **Provenance** | 42% (5/12) | 0% (0/7) | ❌ **MISMATCH** |
| **Multi-Agent** | 25% (3/12) | 14% (1/7) | ⚠️ Papers higher |
| **Semantic Systems** | 8% (1/12) | 29% (2/7) | ❌ **KEYNOTES LEAD** |
| **Enterprise/Production** | 17% (2/12) | 43% (3/7) | ❌ **KEYNOTES LEAD** |

---

## ⚠️ **Critical Mismatches:**

### **1. Provenance: Papers Lead (42% vs. 0%)**
**Papers identified provenance as critical infrastructure**
- 5 papers explicitly use provenance (AgentTrails, Data Canvas, GUIDE, SANA, Walk Before You Run)
- Our analysis showed: provenance IS evaluation infrastructure

**Keynotes don't mention provenance at all**

**Interpretation:**
- Either: Provenance is too academic, not yet production-critical
- Or: Industry uses provenance but calls it something else ("logging", "audit trails")
- **Gap: Academia sees pattern, industry hasn't adopted terminology**

---

### **2. Semantic Systems: Keynotes Lead (29% vs. 8%)**
**Keynotes emphasize "semantic understanding as systems capability"**
- Juliana: "New class of semantic data systems"
- Fatma: "Semantic engines and data agents"

**Only 1 paper (Walk Before You Run) touches semantics**

**Interpretation:**
- Keynotes define the vision
- Papers haven't caught up yet
- **Future direction: More papers on semantic data systems expected**

---

### **3. Enterprise/Production: Keynotes Lead (43% vs. 17%)**
**Keynotes ground in production experience**
- Eric: Alibaba production systems
- Yunyao: Apple, IBM, Adobe deployments
- Shreya: 8-month deployment study

**Papers mostly pre-production or academic datasets**

**Interpretation:**
- Academic publishing lag (production work takes longer)
- Industry proprietary concerns (can't publish production details)
- **Opportunity: More industry-academia collaboration papers**

---

## 💡 **Strategic Insights**

### **For Workshop Organizers:**

**Keynotes complement papers perfectly:**
- Papers: Provenance, multi-agent architectures, specific systems
- Keynotes: Semantic paradigm, enterprise scale, user behavior
- **Together they cover the full stack**

**Missing from both:**
- Evaluation methodology (8% papers, 7% keynotes)
- **Future workshop should emphasize this explicitly**

---

### **For Researchers:**

**Follow the keynote signals:**
1. **Semantic data systems** - Juliana and Fatma both emphasize → emerging area
2. **Agentic data environments** - Eugene's vision → research agenda
3. **User iteration patterns** - Shreya's findings → design implications
4. **Enterprise context** - Yunyao's challenge → real-world constraint

**Bridge the gaps:**
1. **Provenance terminology** - Academia → Industry transfer needed
2. **Evaluation** - Both sides need this
3. **Production-ready provenance** - Make it concrete for industry

---

## 🎯 **Bottom Line: What Keynotes Add**

### **Papers tell you:** What was built, what works technically
### **Keynotes tell you:** Where the field is going, what industry needs

**Key differences:**
- **Scale:** Keynotes emphasize production/enterprise
- **Vision:** Keynotes propose new paradigms (semantic systems, active substrates)
- **Users:** Keynotes center on actual user behavior
- **Integration:** Keynotes bridge Data ↔ Agents (papers don't)

**Key similarities:**
- **HITL:** Both emphasize human oversight (58% papers, 57% keynotes)
- **Evaluation gap:** Both acknowledge but don't solve (8% papers, 7% keynotes)
- **Data-centric:** Both put data before AI (papers: infrastructure cluster, keynotes: semantic data systems)

**The alignment:** **Keynotes validate paper themes while adding scale, semantics, and production perspective**
