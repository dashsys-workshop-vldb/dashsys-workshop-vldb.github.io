# DASHSys 2026 Welcome Address
## 10-Minute Opening Remarks

**Speaker Notes:** Total time: 10 minutes (~1 min per slide)

---

## **SLIDE 1: Welcome** 
### *Title Slide with Workshop Logo*

**Visual:** 
- Workshop title: "DASHSys 2026: Workshop on Data-AI Systems"
- Subtitle: "Co-located with VLDB 2026, Boston, MA"
- Date and location
- Background: Boston skyline or workshop venue

**Speaking Points (1 min):**

> "Good morning, everyone! Welcome to DASHSys 2026 - the inaugural Workshop on Data-AI Systems.
>
> I'm thrilled to see such an incredible turnout today. We have researchers from across academia and industry, from Google, Adobe, Alibaba, MIT, Columbia, NYU, and institutions around the world.
>
> Today is special. Not just because we're launching a new workshop, but because of *how* this workshop came to be. Let me share that story with you."

---

## **SLIDE 2: The Convergence Story**
### *Three Circles → One: The Birth of DASHSys*

**Visual:**
- Three overlapping circles labeled "DAIS", "DAAS", "DASH"
- Arrow pointing to merged circle: "DASHSys"
- Timeline: "2023-2025: Three workshops → 2026: One unified workshop"

**Text on slide:**
- **DAIS**: Data and AI Systems
- **DAAS**: Data Management for Agentic AI Systems  
- **DASH**: Data Systems with Human-in-the-loop AI
- **→ DASHSys**: Data-AI Systems (unified)

**Speaking Points (1.5 min):**

> "This workshop emerged from a remarkable convergence. Three separate workshops—DAIS, DAAS, and DASH—were all proposed for VLDB 2026.
>
> Each had different names, different organizers, different submission portals. But when the program committee reviewed them, they noticed something striking: **the papers could have been submitted to any of the three**. The themes overlapped. The problems overlapped. The community was thinking in parallel.
>
> Rather than fragment the community, VLDB asked us to merge. And that merger tells us something profound: **this is where the field is heading**. Not data systems *or* AI systems, but their integration.
>
> The fact that three independent groups arrived at the same conclusion tells us this isn't a niche—it's a **fundamental shift** in how we think about data infrastructure.
>
> So today isn't just a workshop. It's a milestone—the moment when data systems and AI systems formally recognized they need each other."

---

## **SLIDE 3: By the Numbers**
### *Acceptance Statistics*

**Visual:**
- Clean infographic with numbers
- Use visualizations from our analysis

**Stats to show:**

```
📊 PAPER SUBMISSIONS & ACCEPTANCE

Total Submissions: 35 papers
├─ Regular Track: 23 papers
│  ├─ Long Papers (8 min): 4 accepted (17.4%)
│  └─ Short Papers (4 min): 8 accepted (34.8%)
└─ System Track: 12 papers
   └─ Competition Winners: 2 systems (16.7%)

Overall Acceptance Rate: 40.0%

🏆 WINNERS:
• 1st: IBM Research Zurich
• 2nd: Princeton University
```

**Speaking Points (1 min):**

> "Let's talk about what you'll see today.
>
> We received **35 submissions**—remarkable for a first-year workshop. This confirms the demand for this space.
>
> We accepted **12 regular papers**: 4 long papers at 8 minutes each, and 8 short papers at 4 minutes. That's a **40% acceptance rate**—selective, but we wanted to capture the breadth of the emerging field.
>
> We also ran a **systems track competition**—teams building actual question-answering agents over real enterprise data. Two teams stood out: IBM Research Zurich took first place, and Princeton took second. You'll see both systems demonstrated today.
>
> Quality was high. Acceptance was competitive. And the papers tell a fascinating story about where this field is going—which I want to share with you now."

---

## **SLIDE 4: Today's Program**
### *Schedule Overview*

**Visual:**
- Clean timeline graphic
- Highlight key sessions

**Text on slide:**
```
📅 TODAY'S SCHEDULE

09:00-09:10  Welcome & Opening Remarks (now!)
09:10-10:30  Keynote Session 1 (Eric Zhu, Fatma Özcan)
10:30-11:00  Coffee Break + Posters
11:00-12:30  Paper Session 1: Long Papers (4 papers × 8 min)
12:30-14:00  Lunch Break
14:00-15:30  Keynote Session 2 (Omar Khattab, Eugene Wu)
15:30-16:00  Coffee Break + Posters  
16:00-17:15  Paper Session 2: Short Papers (8 papers × 4 min)
17:15-18:00  Panel Discussion + Closing

🎯 Papers: 4 long (8 min) + 8 short (4 min) oral presentations
📋 Posters: All 12 papers + 2 system demos during breaks
```

**Speaking Points (1 min):**

> "Here's how today flows.
>
> Right after this, we have **two keynote speakers**: Eric Zhu from Alibaba on building agent applications at scale, and Fatma Özcan from Google on 100x efficiency gains in semantic engines.
>
> At 11am, our **long papers session**—four 8-minute talks on deep technical contributions. These set the research agenda.
>
> After lunch, **two more keynotes**: Omar Khattab from MIT on qualitative learning for AI systems, and Eugene Wu from Columbia on what he calls 'agentic data environments.'
>
> At 4pm, **eight short papers**—4 minutes each, rapid fire, showing emerging ideas and systems.
>
> Throughout the day, **all authors will be at posters** during coffee breaks. That's where the real conversations happen—grab the authors, ask questions, make connections.
>
> We end at 5:15 with a **panel discussion** bringing all our keynote speakers together.
>
> But before we start—I want to show you what these papers, as a collection, tell us about the field."

---

## **SLIDE 5: Paper Themes - The Field's Structure**
### *Show theme distribution visualization*

**Visual:**
- Use `theme_distribution_stacked.png` or pie chart
- Show the 4 main themes with percentages

**Text on slide:**
```
🎯 FOUR CORE THEMES

42%  Data Management for Agentic Systems
     Building the infrastructure agents need

25%  Agentic Systems for Data Management  
     Agents that help manage and discover data

42%  Human-Centered & Human-in-the-Loop
     Keeping humans in control

8%   Evaluation, Reliability & Learning
     How to measure and trust these systems
```

**Speaking Points (1.5 min):**

> "When we analyzed the 12 accepted papers, four themes emerged.
>
> **42% focus on data management FOR agents**—GitLake, Data Canvas, Structured State Management. These papers recognize that agents need different data infrastructure than traditional applications. They're building the plumbing: version control for data, provenance tracking, bounded state management.
>
> **25% focus on agents FOR data management**—ASMR, GUIDE, multi-agent frameworks. These use agents to *help us* manage data: generating schemas, discovering datasets, orchestrating workflows.
>
> Notice those first two themes? They're **bidirectional**. Data systems for agents, agents for data systems. That's the integration I mentioned.
>
> **42%—nearly half—emphasize human-in-the-loop**. Not 'humans OR agents' but 'humans AND agents.' Walk Before You Run, AgentTrails, Be Fair!—these papers put human oversight at the center. The message is clear: **automation without human oversight is deployment without guardrails**.
>
> And here's the sobering one: only **8%** focus on evaluation. One paper—SANA—on how to actually *measure* whether these systems work. That's our biggest gap, and our biggest opportunity."

---

## **SLIDE 6: The Hidden Structure**
### *Theme Cross-Pollination Heatmap*

**Visual:**
- Use `theme_cooccurrence_heatmap.png` or network diagram
- Highlight the strongest connections

**Text on slide:**
```
💫 HOW THEMES CONNECT

Strongest Bridges:
🔵 Data Mgmt ↔ Infrastructure (8×)
🟢 HITL ↔ Provenance (6×)  
🟣 Agentic ↔ Multi-Agent (6×)

Universal Connectors:
⭐ HITL: 11 connections (everywhere)
⭐ Provenance: 10 connections (integration layer)

Critical Gap:
⚠️  Data ↔ Agentic (0×) - They don't talk yet!
```

**Speaking Points (1.5 min):**

> "But here's what gets really interesting. We didn't just categorize papers—we looked at how themes **cross-pollinate**.
>
> *[Point to heatmap]* This shows which themes appear together in the same papers.
>
> The **strongest connection?** Data Management and Infrastructure—they appear together **8 times**. They're essentially the same thing. You can't build agent infrastructure without rethinking data management.
>
> Second strongest: **HITL and Provenance**—6 papers. Here's why: you can't have human oversight without provenance. Humans need to see what the agent did to review it. These aren't separate features—they're **co-dependent**.
>
> Third: **Agentic Systems and Multi-Agent**—6 papers. When researchers build agent systems, they're defaulting to multi-agent architectures. Specialized agents, not monoliths. That's a design consensus forming in real-time.
>
> Notice the **two stars**? HITL appears in papers across *every* theme. Provenance appears in 5 of 12 papers. These aren't features—they're **universal infrastructure requirements**.
>
> And the **gap?** Look at that zero. Data Management and Agentic Systems—they don't co-occur. Papers pick one side or the other, not both. That's our missing bridge, and that's where the next breakthrough will come from."

---

## **SLIDE 7: Keynotes - Industry Meets Academia**
### *Seven Speakers, One Message*

**Visual:**
- Photos of 7 keynote speakers in a grid
- Their affiliations below

**Text on slide:**
```
🎤 SEVEN VISIONARIES

Industry:
• Eric Zhu (Alibaba) - AutoGen, QwenPaw
• Fatma Özcan (Google) - 100x efficiency
• Yunyao Li (Adobe) - Enterprise AI at scale

Academia:
• Eugene Wu (Columbia) - Agentic data environments
• Juliana Freire (NYU) - Semantic data systems  
• Omar Khattab (MIT) - DSPy, qualitative learning
• Shreya Shankar (Berkeley→CMU) - What users actually do

Common Thread: Data systems and agents must co-evolve
```

**Speaking Points (1.5 min):**

> "You're going to hear from seven speakers today—three from industry, four from academia. But here's what's remarkable: **they're saying the same thing from different angles**.
>
> **Eric Zhu** built AutoGen at Microsoft, now builds QwenPaw at Alibaba. He'll tell you agents need 'OS-like foundations'—structured infrastructure, not just prompts.
>
> **Fatma Özcan** at Google will show you **100x** cost and latency reductions through proxy models. Not 10%—100x. But only if you architect the data systems correctly.
>
> **Eugene Wu** at Columbia will introduce 'agentic data environments'—his thesis is that **data systems must become active substrates that provide safety**, not passive stores.
>
> **Juliana Freire** at NYU will talk about 'semantic data systems'—elevating semantic understanding to a first-class systems capability. LLMs alone don't solve data problems; you need LLMs plus algorithms plus human expertise.
>
> **Shreya Shankar** will share something sobering: we've been building for the **wrong assumptions**. We assume users arrive with well-specified queries. They don't. She'll show you 1,173 real queries from an 8-month deployment—watch what happens when theory meets reality.
>
> Here's the pattern: **Every keynote is about integration**. Not data OR agents. Data AND agents, together.
>
> That's validation. When academia and industry converge independently, you know you're onto something fundamental."

---

## **SLIDE 8: Panel - The Hard Questions**
### *Closing Discussion*

**Visual:**
- Panel format graphic showing 5 speakers + moderator
- Question marks or thought bubbles

**Text on slide:**
```
💬 PANEL DISCUSSION (5:15-6:00 PM)

Moderator: [Name]

Panelists:
• Eric Zhu, Fatma Özcan, Eugene Wu,
  Juliana Freire, Yunyao Li

Topics:
❓ What abstractions are fundamentally broken?
❓ How do we evaluate compound systems?
❓ What's the right level of human oversight?
❓ Where is production 5 years ahead of research?
❓ What should PhD students work on?

Plus: YOUR questions from the audience
```

**Speaking Points (1 min):**

> "We're ending with a panel—all our industry keynote speakers plus Eugene and Juliana from academia.
>
> We're not doing 'future directions' or polite consensus. We're asking **hard questions**:
>
> - What fundamental abstractions are **broken** in today's systems?
> - How do we evaluate systems whose behavior *emerges* from interactions between models, algorithms, tools, and humans?
> - Eugene will argue data systems should provide safety. Yunyao will talk about enterprise context. I want to see them debate: **whose responsibility is agent safety**—the data layer or the application layer?
> - Where is industry 5 years ahead of academia, and vice versa?
>
> And most importantly: **your questions**. We'll save 20 minutes for audience questions. If a paper sparked an idea, if a keynote raised a concern, if you see a gap no one's talking about—that's what panels are for.
>
> Bring your hard questions. This is the venue for them."

---

## **SLIDE 9: What Makes This Workshop Different**
### *Our Values & Vision*

**Visual:**
- Three pillars or values displayed prominently

**Text on slide:**
```
🌟 THE DASHSys DIFFERENCE

1️⃣  Integration, Not Separation
    Papers bridge data systems ↔ AI systems
    Not "which side wins" but "how they work together"

2️⃣  Human-in-the-Loop is Non-Negotiable  
    58% of papers include HITL
    Not automation vs. oversight—automation WITH oversight

3️⃣  Production Reality Meets Research Vision
    Industry speakers + academic depth
    Systems track tests ideas on real data
    Gap analysis → research agenda

🎯 We're not just publishing papers.
   We're defining how data systems evolve for an agentic era.
```

**Speaking Points (1 min):**

> "Let me tell you what makes this workshop different.
>
> **First: integration is the default.** Most venues force you to pick a side—are you a data systems person or an AI person? Here, the best papers are **both**. Data Canvas, ASMR, SANA—these don't fit cleanly into SIGMOD or NeurIPS. They need both. That's why this workshop exists.
>
> **Second: human-in-the-loop is non-negotiable.** 58% of accepted papers include HITL. That's not a coincidence—that's a value. We're not building systems to replace humans. We're building systems that make humans more capable. Automation without oversight isn't innovation—it's risk.
>
> **Third: we bridge production and research.** Our keynotes have deployed systems to billions of users—Apple, Google, Adobe, Alibaba. Our papers propose fundamental new abstractions. Put them in the same room, and you get two things: research grounded in real constraints, and industry learning what's possible.
>
> This isn't just another workshop. This is where the data systems community **chooses its future**."

---

## **SLIDE 10: Thank You & Let's Begin!**
### *Closing with Energy*

**Visual:**
- Energetic, forward-looking graphic
- Workshop logo
- "DASHSys 2026" prominently
- Hashtag: #DASHSys2026

**Text on slide:**
```
🚀 THANK YOU!

📸  Share your insights: #DASHSys2026
📋  Posters: Coffee breaks (10:30 & 15:30)
💬  Panel Q&A: Submit questions anytime
🤝  Connect: Authors at posters, speakers after talks

Workshop Website: dashsys-workshop-vldb.github.io
Proceedings: VLDB Workshop Volume

Let's build the future of data-AI systems—together.

Next up: Keynote 1 - Eric Zhu (Alibaba)
"Surfing the Jagged Frontier: Practical Lessons in Building Agent Applications"
```

**Speaking Points (1 min):**

> "Before I hand over to our first keynote speaker—three quick things.
>
> **First: engage.** Don't just sit and listen. Posters are during coffee breaks—grab authors, debate ideas, challenge assumptions. The hallway track is as valuable as the scheduled track.
>
> **Second: share.** If something resonates, tweet it. Tag #DASHSys2026. This is a new workshop—your amplification helps the community find each other.
>
> **Third: question everything.** Panel discussion at 5:15. If you think we're missing something, if you disagree with a speaker, if you see a gap—write it down, bring it to the panel. The best workshops are the ones where the audience teaches us something we didn't know.
>
> We have an incredible day ahead. Four deep research papers. Eight rapid-fire short papers. Seven world-class speakers. A panel that won't pull punches. And a room full of people who believe data systems and AI systems need to evolve together.
>
> **Three years ago, three separate workshops proposed the same idea independently.**
>
> **Today, we're one community.**
>
> **Tomorrow, we define what data systems look like in an agentic world.**
>
> Thank you. Let's begin.
>
> *[Pause, then with energy]:* Please welcome our first keynote speaker—**Eric Zhu from Alibaba**, on 'Surfing the Jagged Frontier: Practical Lessons in Building Agent Applications'!"

---

## **TIMING BREAKDOWN:**

- Slide 1 (Welcome): 1:00
- Slide 2 (Convergence Story): 1:30
- Slide 3 (Statistics): 1:00
- Slide 4 (Program): 1:00
- Slide 5 (Paper Themes): 1:30
- Slide 6 (Cross-Pollination): 1:30
- Slide 7 (Keynotes): 1:30
- Slide 8 (Panel): 1:00
- Slide 9 (What Makes Us Different): 1:00
- Slide 10 (Thank You): 1:00

**Total: 12:00 minutes**

*Adjust by speaking faster/slower or condensing slides 5-6 into one if needed for 10 min target.*

---

## **BACKUP SLIDES** (if time allows or for Q&A):

### **Backup 1: Research Opportunities**
```
🔬 WHERE THE FIELD IS HEADING

Three Frontier Areas:

1. Bridging the Gap: Data ↔ Agent Integration
   Papers: 0% coverage | Keynotes: 43% coverage
   → Opportunity: How should data systems change for agents?

2. Evaluation for Compound Systems
   Papers: 8% coverage | Keynotes: 7% coverage  
   → Opportunity: How to measure emergent behavior?

3. Provenance as Infrastructure
   Papers: 42% coverage | Keynotes: 0% coverage
   → Opportunity: Productionize academic insights
```

### **Backup 2: Word Cloud**
*Show wordcloud from keynotes + papers*
```
What the Field Talks About:
• DATA (37 mentions)
• SYSTEMS (22)
• AGENTS (15)
• SEMANTIC (14)

What's Missing:
• "Autonomous" (0) → We say "agentic" instead
• "AI" (minimal) → We're systems-first
• "Provenance" in keynotes (0) → Gap to bridge
```

---

## **VISUAL DESIGN NOTES:**

**Color Palette:**
- Data Management: Blue (#2563eb)
- Agentic Systems: Purple (#7c3aed)
- Evaluation: Red (#dc2626)
- HITL: Green (#059669)
- Infrastructure: Orange (#f59e0b)

**Typography:**
- Headlines: Bold, 40-48pt
- Body: 24-28pt (readable from back of room)
- Emphasis: Color + bold, not ALL CAPS

**Images:**
- Use the generated visualizations (heatmap, network diagram, bar charts)
- High contrast for projector readability
- Minimal text per slide (speaking points in notes, not on slides)

**Energy Level:**
- Start warm (Slide 1-2)
- Build to enthusiastic (Slide 5-7)  
- End HIGH ENERGY (Slide 9-10)
- Hand off to keynote with excitement
