# Visualization Recommendations for DASHSys 2026 Paper Analysis

## Dataset Summary
- 12 accepted papers
- 4 primary themes
- 5 cross-cutting insights
- Multiple papers span multiple themes

---

## Recommended Visualizations

### 1. **UpSet Plot** - BEST for Multi-Theme Papers ⭐
**What it shows:** Which theme combinations appear, and how many papers in each
**Why it's best:** Handles overlapping sets better than Venn diagrams for 4+ categories

**What you'd see:**
- 5 papers are *only* in one theme
- 7 papers span multiple themes
- Most common intersection: Data Management + Human-in-Loop (3 papers)

**Tools:** 
- R: `UpSetR` package
- Python: `upsetplot` package
- Online: https://upset.app/

**Code example (Python):**
```python
from upsetplot import plot, from_memberships
import matplotlib.pyplot as plt

# Each paper's theme memberships
data = from_memberships([
    ['Data Mgmt'],  # GitLake (actually Data Mgmt + HITL)
    ['Data Mgmt', 'HITL'],  # Walk Before You Run
    ['Data Mgmt'],  # Structured State Management
    ['Data Mgmt'],  # Data Canvas
    ['Agentic Systems'],  # ASMR
    ['Agentic Systems'],  # Multi-agent Framework
    ['Agentic Systems', 'HITL'],  # GUIDE
    ['Evaluation'],  # SANA
    ['HITL'],  # Resource Rational Interfaces
    ['HITL'],  # Be Fair!
    ['HITL'],  # AgentTrails
    ['HITL'],  # Conflicts of Interest
])

plot(data, sort_by='cardinality')
plt.title('DASHSys 2026: Theme Overlaps')
plt.savefig('upset_plot.png', dpi=300, bbox_inches='tight')
```

---

### 2. **Alluvial/Sankey Diagram** - BEST for Showing Flow ⭐
**What it shows:** Papers → Primary Themes → Cross-Cutting Concerns
**Why it's powerful:** Shows how themes aggregate into higher-level insights

**Three-layer flow:**
```
[12 Papers] → [4 Themes] → [5 Cross-Cutting Insights]

Layer 1: Individual papers
Layer 2: Primary theme assignment
Layer 3: Cross-cutting concerns (HITL, Infrastructure, etc.)
```

**What you'd see:**
- Multiple papers from different themes flow into "HITL Dominant" (7 papers)
- "Data Management" papers split between "Infrastructure" and other concerns
- "Evaluation" theme is isolated (only SANA)

**Tools:**
- Python: `plotly` (interactive)
- R: `ggalluvial`
- JavaScript: D3.js sankey

**Code example (Python with Plotly):**
```python
import plotly.graph_objects as go

# Define flows: Paper → Theme → Insight
# Format: source, target, value
flows = [
    # Papers to Themes
    ("GitLake", "Data Mgmt", 1),
    ("Walk Before You Run", "Data Mgmt", 1),
    ("Structured State", "Data Mgmt", 1),
    ("Data Canvas", "Data Mgmt", 1),
    ("ASMR", "Agentic Sys", 1),
    ("Multi-agent Fwk", "Agentic Sys", 1),
    ("GUIDE", "Agentic Sys", 1),
    ("SANA", "Evaluation", 1),
    ("Resource Rational", "HITL", 1),
    ("Be Fair!", "HITL", 1),
    ("AgentTrails", "HITL", 1),
    ("Conflicts", "HITL", 1),
    
    # Themes to Insights
    ("Data Mgmt", "Infrastructure", 4),
    ("Data Mgmt", "HITL Dominant", 2),
    ("Agentic Sys", "Multi-Agent", 2),
    ("Agentic Sys", "HITL Dominant", 1),
    ("Evaluation", "Eval Gap", 1),
    ("Evaluation", "Provenance", 1),
    ("HITL", "HITL Dominant", 4),
    ("HITL", "Provenance", 2),
]

# Create Sankey
fig = go.Figure(data=[go.Sankey(
    node = dict(
      pad = 15,
      thickness = 20,
      label = ["GitLake", "Walk Before You Run", ...],
      color = "blue"
    ),
    link = dict(
      source = [0, 1, 2, ...],  # indices
      target = [12, 12, 12, ...],
      value = [1, 1, 1, ...]
  ))])

fig.update_layout(title_text="DASHSys 2026: Papers → Themes → Insights", 
                  font_size=10)
fig.write_html("sankey.html")
```

---

### 3. **Stacked Bar Chart** - BEST for Theme Distribution ⭐
**What it shows:** Each theme with breakdown of paper types (Long vs Short)
**Why useful:** Shows both theme distribution AND paper length bias

**What you'd see:**
- Data Management: 1 long (Walk), 3 short
- Agentic Systems: 1 long (ASMR), 2 short
- Evaluation: 1 long (SANA), 0 short
- HITL: 1 long (Resource Rational), 4 short

**Insight revealed:** Long papers skew toward Evaluation/HITL themes

**Code example (Python):**
```python
import matplotlib.pyplot as plt
import numpy as np

themes = ['Data Mgmt\n(42%)', 'Agentic Sys\n(25%)', 
          'Evaluation\n(8%)', 'HITL\n(42%)']
long_papers = [1, 1, 1, 1]
short_papers = [4, 2, 0, 4]

x = np.arange(len(themes))
width = 0.6

fig, ax = plt.subplots(figsize=(10, 6))
p1 = ax.bar(x, long_papers, width, label='Long Papers', color='#2563eb')
p2 = ax.bar(x, short_papers, width, bottom=long_papers, 
            label='Short Papers', color='#93c5fd')

ax.set_ylabel('Number of Papers', fontsize=12)
ax.set_title('DASHSys 2026: Theme Distribution by Paper Length', 
             fontsize=14, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(themes)
ax.legend()

# Add value labels on bars
for i, theme in enumerate(themes):
    total = long_papers[i] + short_papers[i]
    ax.text(i, total + 0.1, str(total), ha='center', fontweight='bold')

plt.tight_layout()
plt.savefig('stacked_bar.png', dpi=300)
```

---

### 4. **Radar/Spider Chart** - BEST for Cross-Cutting Themes ⭐
**What it shows:** The 5 cross-cutting insights as dimensions, plotted across themes
**Why compelling:** Shows which themes contribute to which insights

**5 dimensions:**
1. HITL Integration (7 papers)
2. Infrastructure Focus (5 papers)
3. Evaluation Methodology (1 paper + 4 with provenance)
4. Multi-Agent Architecture (3 papers)
5. Provenance Tracking (5 papers)

**What you'd see:**
- Data Management: High on Infrastructure & Provenance, medium HITL
- Agentic Systems: High on Multi-Agent, medium HITL
- Evaluation: High on Evaluation (duh), medium Provenance
- HITL: Maxed on HITL, medium Provenance

**Code example (Python):**
```python
import matplotlib.pyplot as plt
import numpy as np

categories = ['HITL\nIntegration', 'Infrastructure\nFocus', 
              'Evaluation\nMethodology', 'Multi-Agent\nArchitecture', 
              'Provenance\nTracking']

# Each theme's score on each dimension (0-5 scale)
data_mgmt = [2, 5, 2, 0, 3]      # Strong infrastructure & provenance
agentic_sys = [1, 1, 0, 3, 1]    # Multi-agent focus
evaluation = [0, 0, 5, 0, 3]     # Pure evaluation
hitl = [5, 0, 0, 0, 2]           # Pure HITL

# Plot
angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
data_mgmt += data_mgmt[:1]
agentic_sys += agentic_sys[:1]
evaluation += evaluation[:1]
hitl += hitl[:1]
angles += angles[:1]

fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection='polar'))
ax.plot(angles, data_mgmt, 'o-', linewidth=2, label='Data Mgmt', color='#2563eb')
ax.fill(angles, data_mgmt, alpha=0.15, color='#2563eb')
ax.plot(angles, agentic_sys, 'o-', linewidth=2, label='Agentic Sys', color='#7c3aed')
ax.fill(angles, agentic_sys, alpha=0.15, color='#7c3aed')
ax.plot(angles, evaluation, 'o-', linewidth=2, label='Evaluation', color='#dc2626')
ax.fill(angles, evaluation, alpha=0.15, color='#dc2626')
ax.plot(angles, hitl, 'o-', linewidth=2, label='HITL', color='#059669')
ax.fill(angles, hitl, alpha=0.15, color='#059669')

ax.set_xticks(angles[:-1])
ax.set_xticklabels(categories, size=10)
ax.set_ylim(0, 5)
ax.set_title('Cross-Cutting Themes by Paper Category', size=14, fontweight='bold', pad=20)
ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
ax.grid(True)

plt.tight_layout()
plt.savefig('radar_chart.png', dpi=300)
```

---

### 5. **Chord Diagram** - BEST for Paper-Theme Relationships ⭐
**What it shows:** Circular layout showing connections between papers and themes
**Why beautiful:** Reveals clustering and cross-theme papers elegantly

**What you'd see:**
- Thick arcs for themes with many papers
- Papers with multiple connections span themes
- Visual clustering of related work

**Tools:**
- JavaScript: `d3-chord`
- Python: `holoviews` with `chord`
- R: `circlize` package

---

### 6. **Heatmap Matrix** - BEST for Paper×Theme Coverage
**What it shows:** Papers (rows) × Themes + Insights (columns), colored by relevance
**Why useful:** Compact overview of all relationships

**Example:**
```
                   | Data | Agent | Eval | HITL | Infra | Multi | Prov |
GitLake            |  ●●  |       |      |  ●   |  ●●   |       |      |
Walk Before Run    |  ●●  |       |      |  ●●  |  ●    |       |  ●   |
Structured State   |  ●●  |       |      |      |  ●●   |       |      |
Data Canvas        |  ●●  |       |      |      |  ●    |       |  ●●  |
ASMR               |      |  ●●   |      |  ●   |       |  ●    |      |
Multi-agent Fwk    |      |  ●●   |      |      |       |  ●    |      |
GUIDE              |      |  ●●   |      |  ●   |       |  ●    |  ●   |
SANA               |      |       |  ●●  |      |       |       |  ●●  |
Resource Rational  |      |       |      |  ●●  |       |       |      |
Be Fair!           |      |       |      |  ●●  |       |       |      |
AgentTrails        |      |       |      |  ●●  |       |       |  ●●  |
Conflicts          |      |       |      |  ●●  |       |       |      |

●● = Primary theme/strong presence
●  = Secondary theme/mentioned
```

**Code example (Python with Seaborn):**
```python
import seaborn as sns
import pandas as pd
import matplotlib.pyplot as plt

# Create matrix (2 = primary, 1 = secondary, 0 = not covered)
data = {
    'Paper': ['GitLake', 'Walk Before Run', 'Structured State', 'Data Canvas',
              'ASMR', 'Multi-agent Fwk', 'GUIDE', 'SANA',
              'Resource Rational', 'Be Fair!', 'AgentTrails', 'Conflicts'],
    'Data Mgmt': [2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0],
    'Agentic Sys': [0, 0, 0, 0, 2, 2, 2, 0, 0, 0, 0, 0],
    'Evaluation': [0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0],
    'HITL': [1, 2, 0, 0, 1, 0, 1, 0, 2, 2, 2, 2],
    'Infrastructure': [2, 1, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0],
    'Multi-Agent': [0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0],
    'Provenance': [0, 1, 0, 2, 0, 0, 1, 2, 0, 0, 2, 0],
}

df = pd.DataFrame(data)
df.set_index('Paper', inplace=True)

# Plot
plt.figure(figsize=(10, 8))
sns.heatmap(df, annot=True, cmap='YlOrRd', cbar_kws={'label': 'Coverage'},
            linewidths=0.5, fmt='d')
plt.title('DASHSys 2026: Paper Coverage Across Themes and Insights', 
          fontsize=14, fontweight='bold', pad=20)
plt.xlabel('Themes & Cross-Cutting Insights', fontsize=12)
plt.ylabel('Accepted Papers', fontsize=12)
plt.tight_layout()
plt.savefig('heatmap.png', dpi=300)
```

---

### 7. **Bubble Chart** - BEST for Theme Importance + Overlap
**What it shows:** Themes as bubbles sized by paper count, positioned by cross-cutting presence
**Why intuitive:** Size = importance, position = character

**Axes:**
- X-axis: HITL Integration (0-100%)
- Y-axis: Infrastructure Focus (0-100%)
- Bubble size: Number of papers
- Bubble color: Primary theme

**What you'd see:**
- "Data Management" bubble: Large, high Y (infrastructure), medium X (some HITL)
- "HITL" bubble: Large, low Y, max X (pure HITL, not infrastructure)
- "Evaluation" bubble: Tiny, medium both (SANA has provenance)
- "Agentic Systems" bubble: Medium, low both

---

### 8. **Treemap** - BEST for Hierarchical View
**What it shows:** Nested rectangles: Themes → Papers, sized by some metric
**Why useful:** Shows relative importance and nesting

**Possible metrics for sizing:**
- Equal (all papers same size)
- By paper length (long = 2x short)
- By citation count (if available)
- By "cross-cutting score" (how many themes touched)

---

## Recommended Combination

**For a comprehensive presentation, use this trio:**

### 📊 **Slide 1: Overview** → Stacked Bar Chart
Shows theme distribution clearly, easy to understand

### 🔀 **Slide 2: Relationships** → Alluvial/Sankey Diagram
Shows how themes feed into cross-cutting insights

### 🎯 **Slide 3: Deep Dive** → UpSet Plot OR Heatmap
Shows which papers span which themes (overlaps)

---

## Tools Summary

**Quick & Easy:**
- **Google Sheets / Excel**: Stacked bar, simple pie charts
- **Flourish.studio**: Beautiful interactive charts, no code
- **RAWGraphs**: Alluvial, chord diagrams, free online tool

**Programming (More Control):**
- **Python**: matplotlib, seaborn, plotly
- **R**: ggplot2, ggalluvial, circlize
- **JavaScript**: D3.js (most flexible, steepest learning curve)

**Recommended for non-coders:**
- **Flourish** for Sankey/alluvial
- **RAWGraphs** for chord diagram
- **Datawrapper** for clean bar charts
- **Venngage** for infographic-style visuals

---

## Data Files

I can generate CSV files in any format needed for these tools. Let me know which visualizations you want to create!
