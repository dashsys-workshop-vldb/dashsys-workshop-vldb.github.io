# DASHSys 2026 Workshop - Visualization Resources

## 📊 Complete Visualization Package

This directory contains comprehensive analysis and visualization resources for the DASHSys 2026 VLDB Workshop accepted papers.

---

## 📁 Files Created

### 📈 Analysis Documents
1. **`paper-theme-analysis.md`** - Comprehensive theme mapping and insights
2. **`provenance-evaluation-connection.md`** - Deep dive on provenance as evaluation infrastructure
3. **`wordcloud-analysis.md`** - Word frequency analysis and insights
4. **`visualization-recommendations.md`** - Detailed visualization guide with code

### 📊 Data Files (in `viz-data/`)
1. **`theme-distribution.csv`** - Theme breakdown with paper counts
2. **`paper-theme-matrix.csv`** - Paper × Theme coverage matrix
3. **`cross-cutting-insights.csv`** - Cross-cutting themes
4. **`sankey-flows.csv`** - Flow data for Sankey diagrams
5. **`wordcloud-data.csv`** - Word frequencies for word clouds

### 🎨 Generation Scripts
1. **`generate_visualizations.py`** - Creates 6 chart types
2. **`generate_wordcloud.py`** - Creates 4 word cloud variants

---

## 🚀 Quick Start

### Option 1: Generate Visualizations (requires Python libraries)

```bash
# Install dependencies
pip install pandas matplotlib seaborn wordcloud

# Generate all charts
python3 generate_visualizations.py

# Generate word clouds
python3 generate_wordcloud.py
```

**Output:** 10 PNG files in `visualizations/` directory

### Option 2: Use Online Tools (no coding required)

**For Charts:**
- Upload CSV files to [Flourish](https://flourish.studio)
- Use [RAWGraphs](https://rawgraphs.io) for Sankey/Alluvial diagrams
- Try [Datawrapper](https://datawrapper.de) for clean bar charts

**For Word Clouds:**
- Upload `wordcloud-data.csv` to [WordClouds.com](https://wordclouds.com)
- Try [Wordle](http://wordle.net) for classic style
- Use [Voyant Tools](https://voyant-tools.org) for academic analysis

---

## 📊 Recommended Visualization Set

### For a Workshop Presentation:

**Slide 1: Theme Overview**
→ Use: **Stacked Bar Chart** (`theme_distribution_stacked.png`)
- Shows 4 themes with long/short paper breakdown
- Clear percentages
- Easy to understand

**Slide 2: Cross-Cutting Insights**
→ Use: **Horizontal Bar Chart** (`cross_cutting_insights.png`)
- 5 key insights
- Shows HITL dominance (58%)
- Highlights evaluation gap

**Slide 3: Paper-Theme Relationships**
→ Use: **Heatmap Matrix** (`paper_theme_heatmap.png`)
- All 12 papers × 7 dimensions
- Shows primary vs. secondary themes
- Reveals multi-theme papers

**Slide 4: Theme Characteristics**
→ Use: **Radar Chart** (`radar_chart.png`)
- 5 cross-cutting dimensions
- Shows each theme's profile
- Beautiful, distinctive

**Slide 5: Vocabulary Analysis**
→ Use: **Word Cloud** (`wordcloud_overall.png`)
- Visual summary of key terms
- DATA dominant
- Shows field vocabulary

---

## 🎯 Key Insights Visualized

### 1. Theme Distribution
```
Data Management:    5 papers (42%) ████████████
Agentic Systems:    3 papers (25%) ███████
Evaluation:         1 paper  (8%)  ██
HITL:              5 papers (42%) ████████████
```

### 2. Cross-Cutting Themes
```
HITL Dominant:      7 papers (58%) ██████████████
Infrastructure:     5 papers (42%) ██████████
Provenance:         5 papers (42%) ██████████
Multi-Agent:        3 papers (25%) ██████
Evaluation:         1 paper  (8%)  ██
```

### 3. Top Words from Abstracts
```
data        ████████████████████████████ (28)
agent       ██████████ (10)
agents      ██████████ (10)
agentic     ██████ (6)
provenance  ██████ (6)
schema      ██████ (6)
framework   ██████ (6)
discovery   █████ (5)
```

---

## 📝 Key Findings

### ✅ What the Visualizations Reveal:

1. **HITL is Not Optional** (58% of papers)
   - Even infrastructure papers include human oversight
   - Field values augmentation over automation

2. **Provenance Emerges as Core Concern** (42% of papers)
   - AgentTrails, Data Canvas, GUIDE, SANA, Walk Before You Run
   - Indirectly enables evaluation (as analyzed in detail)

3. **Evaluation is Underrepresented** (8%)
   - Only SANA explicitly advances evaluation methodology
   - Gap opportunity for future work

4. **Multi-Agent Architectures Dominate**
   - ASMR (2 agents), GUIDE (6 agents), Multi-agent Framework
   - Trend: Specialized > Monolithic

5. **Data-Centric, Not AI-Centric**
   - "DATA" appears 28 times vs. "AGENT" 20 times
   - Focus on infrastructure, not model hype
   - Missing terms: "GPT" (0), "neural" (0), "autonomous" (0)

---

## 🎨 Visualization Types Available

### Standard Charts:
✓ Stacked Bar Chart - Theme distribution by paper length
✓ Grouped Bar Chart - Long vs. short papers
✓ Horizontal Bar Chart - Cross-cutting insights
✓ Pie/Donut Chart - Theme distribution
✓ Heatmap Matrix - Paper × Theme coverage
✓ Radar/Spider Chart - Cross-cutting dimensions

### Advanced Visualizations:
✓ Sankey/Alluvial Diagram - Papers → Themes → Insights flow
✓ UpSet Plot - Theme overlaps (better than Venn for 4+ sets)
✓ Chord Diagram - Paper-theme relationships
✓ Bubble Chart - Theme importance + characteristics

### Word Clouds:
✓ Overall vocabulary
✓ Theme-specific clouds
✓ Circular layout
✓ Comparison (top 20 vs. rest)

---

## 💡 Usage Recommendations

### For Academic Papers:
- **Heatmap** for comprehensive overview
- **Radar chart** for theme characterization
- **Word cloud** as qualitative supplement

### For Presentations:
- **Stacked bar** for quick overview
- **Sankey** for showing relationships
- **Radar** for visual impact

### For Posters:
- **Large word cloud** as centerpiece
- **Pie chart** for proportions
- **Icons + numbers** for key stats

### For Workshop Website:
- **Interactive Sankey** (use Flourish)
- **Heatmap with tooltips**
- **Clickable word cloud** linking to papers

---

## 🔧 Customization Options

### Colors by Theme:
- Data Management: `#2563eb` (Blue)
- Agentic Systems: `#7c3aed` (Purple)  
- Evaluation: `#dc2626` (Red)
- HITL: `#059669` (Green)
- Infrastructure: `#f59e0b` (Orange)

### Fonts:
- Titles: Inter, 16-20pt, Bold
- Labels: Inter, 11-13pt, Regular
- Values: Inter, 10-12pt, Bold

### Export Specs:
- **For papers:** 300 DPI, PNG or PDF
- **For slides:** 150 DPI, PNG
- **For web:** 96 DPI, PNG or SVG

---

## 📚 Additional Resources

### Learn More:
- `paper-theme-analysis.md` - Full theme breakdown
- `provenance-evaluation-connection.md` - Provenance deep dive
- `wordcloud-analysis.md` - Vocabulary analysis

### Tools Documentation:
- `visualization-recommendations.md` - Detailed guide with code examples

### Raw Data:
- All CSV files in `viz-data/` can be used with any tool

---

## 🎯 Next Steps

### For Workshop Organizers:
1. Choose 3-5 visualizations for website
2. Generate high-res versions (300 DPI)
3. Add interactive versions using Flourish
4. Update README with visual summary

### For Future Workshops:
1. **Track changes** - Compare 2026 vs. 2027 themes
2. **Benchmark growth** - Track paper counts by theme
3. **Vocabulary evolution** - Monitor emerging terms
4. **Citation network** - Add paper influence viz

### For Researchers:
1. **Gap analysis** - Identify underexplored areas
2. **Trend prediction** - Extrapolate theme trajectories
3. **Collaboration map** - Visualize author networks
4. **Impact tracking** - Monitor real-world adoption

---

## 📞 Questions?

If you need:
- Different chart types
- Custom color schemes
- Interactive versions
- Additional analysis

Let me know and I can generate more variations!

---

**Generated:** 2026-09-03  
**Workshop:** DASHSys 2026 @ VLDB  
**Papers Analyzed:** 12 accepted papers (4 long, 8 short)
