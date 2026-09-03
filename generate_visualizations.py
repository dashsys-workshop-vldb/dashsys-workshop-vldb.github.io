#!/usr/bin/env python3
"""
Generate visualizations for DASHSys 2026 workshop paper analysis
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path

# Set style
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")

# Create output directory
output_dir = Path('visualizations')
output_dir.mkdir(exist_ok=True)

# ============================================================================
# 1. STACKED BAR CHART - Theme Distribution by Paper Length
# ============================================================================

def create_stacked_bar():
    themes = ['Data Management\nfor Agentic Systems\n(42%)',
              'Agentic Systems\nfor Data Management\n(25%)',
              'Evaluation &\nReliability\n(8%)',
              'Human-Centered &\nHuman-in-Loop\n(42%)']
    long_papers = [1, 1, 1, 1]
    short_papers = [4, 2, 0, 4]

    x = np.arange(len(themes))
    width = 0.6

    fig, ax = plt.subplots(figsize=(12, 7))

    # Create bars
    p1 = ax.bar(x, long_papers, width, label='Long Papers (8 min)',
                color='#2563eb', edgecolor='white', linewidth=2)
    p2 = ax.bar(x, short_papers, width, bottom=long_papers,
                label='Short Papers (4 min)', color='#93c5fd',
                edgecolor='white', linewidth=2)

    # Styling
    ax.set_ylabel('Number of Papers', fontsize=13, fontweight='bold')
    ax.set_title('DASHSys 2026: Theme Distribution by Paper Length',
                 fontsize=16, fontweight='bold', pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(themes, fontsize=11)
    ax.legend(fontsize=11, loc='upper right')
    ax.set_ylim(0, 6)
    ax.grid(axis='y', alpha=0.3, linestyle='--')

    # Add value labels
    for i in range(len(themes)):
        total = long_papers[i] + short_papers[i]
        # Total on top
        ax.text(i, total + 0.15, str(total), ha='center',
                fontweight='bold', fontsize=13)
        # Long papers count
        if long_papers[i] > 0:
            ax.text(i, long_papers[i]/2, str(long_papers[i]),
                    ha='center', color='white', fontweight='bold', fontsize=10)
        # Short papers count
        if short_papers[i] > 0:
            ax.text(i, long_papers[i] + short_papers[i]/2, str(short_papers[i]),
                    ha='center', color='white', fontweight='bold', fontsize=10)

    plt.tight_layout()
    plt.savefig(output_dir / 'theme_distribution_stacked.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Created: theme_distribution_stacked.png")


# ============================================================================
# 2. HEATMAP - Paper × Theme Coverage
# ============================================================================

def create_heatmap():
    df = pd.read_csv('viz-data/paper-theme-matrix.csv')
    df_plot = df.set_index('Paper').drop(columns=['Type'])

    # Rename columns for display
    df_plot.columns = ['Data\nMgmt', 'Agentic\nSys', 'Eval', 'HITL',
                       'Infra', 'Multi-\nAgent', 'Prov']

    # Shorten paper names
    short_names = [
        'GitLake',
        'Walk Before Run',
        'Structured State',
        'Data Canvas',
        'ASMR',
        'Multi-agent Fwk',
        'GUIDE',
        'SANA',
        'Resource Rational',
        'Be Fair!',
        'AgentTrails',
        'Conflicts',
    ]
    df_plot.index = short_names

    # Create heatmap
    fig, ax = plt.subplots(figsize=(10, 10))

    sns.heatmap(df_plot, annot=True, cmap='RdYlGn', center=1,
                cbar_kws={'label': 'Coverage (0=None, 1=Secondary, 2=Primary)'},
                linewidths=1, linecolor='white', fmt='d',
                square=True, ax=ax, vmin=0, vmax=2)

    plt.title('DASHSys 2026: Paper Coverage Across Themes and Insights',
              fontsize=16, fontweight='bold', pad=20)
    plt.xlabel('Themes & Cross-Cutting Insights', fontsize=13, fontweight='bold')
    plt.ylabel('Accepted Papers', fontsize=13, fontweight='bold')
    plt.xticks(rotation=0, fontsize=11)
    plt.yticks(rotation=0, fontsize=10)

    plt.tight_layout()
    plt.savefig(output_dir / 'paper_theme_heatmap.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Created: paper_theme_heatmap.png")


# ============================================================================
# 3. HORIZONTAL BAR - Cross-Cutting Insights
# ============================================================================

def create_cross_cutting_bars():
    insights = ['HITL Dominant', 'Infrastructure\nFoundation',
                'Provenance\nTracking', 'Multi-Agent\nArchitectures',
                'Evaluation\nMethodology']
    counts = [7, 5, 5, 3, 1]
    percentages = [58, 42, 42, 25, 8]

    colors = ['#059669', '#2563eb', '#7c3aed', '#f59e0b', '#dc2626']

    fig, ax = plt.subplots(figsize=(12, 6))

    y_pos = np.arange(len(insights))
    bars = ax.barh(y_pos, counts, color=colors, edgecolor='white', linewidth=2)

    # Add value labels
    for i, (count, pct) in enumerate(zip(counts, percentages)):
        ax.text(count + 0.15, i, f'{count} papers ({pct}%)',
                va='center', fontweight='bold', fontsize=11)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(insights, fontsize=12)
    ax.invert_yaxis()
    ax.set_xlabel('Number of Papers', fontsize=13, fontweight='bold')
    ax.set_title('DASHSys 2026: Cross-Cutting Insights Across Accepted Papers',
                 fontsize=16, fontweight='bold', pad=20)
    ax.set_xlim(0, 8)
    ax.grid(axis='x', alpha=0.3, linestyle='--')

    plt.tight_layout()
    plt.savefig(output_dir / 'cross_cutting_insights.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Created: cross_cutting_insights.png")


# ============================================================================
# 4. RADAR CHART - Cross-Cutting Themes by Category
# ============================================================================

def create_radar_chart():
    categories = ['HITL\nIntegration', 'Infrastructure\nFocus',
                  'Evaluation\nMethodology', 'Multi-Agent\nArchitecture',
                  'Provenance\nTracking']

    # Normalized scores (0-5 scale based on paper counts)
    data_mgmt = [2, 5, 1, 0, 3]
    agentic_sys = [1, 0, 0, 3, 1]
    evaluation = [0, 0, 5, 0, 5]
    hitl = [5, 0, 0, 0, 2]

    # Complete the circle
    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
    data_mgmt = data_mgmt + data_mgmt[:1]
    agentic_sys = agentic_sys + agentic_sys[:1]
    evaluation = evaluation + evaluation[:1]
    hitl = hitl + hitl[:1]
    angles = angles + angles[:1]

    # Plot
    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection='polar'))

    ax.plot(angles, data_mgmt, 'o-', linewidth=2.5, label='Data Mgmt (5)', color='#2563eb')
    ax.fill(angles, data_mgmt, alpha=0.2, color='#2563eb')

    ax.plot(angles, agentic_sys, 's-', linewidth=2.5, label='Agentic Sys (3)', color='#7c3aed')
    ax.fill(angles, agentic_sys, alpha=0.2, color='#7c3aed')

    ax.plot(angles, evaluation, '^-', linewidth=2.5, label='Evaluation (1)', color='#dc2626')
    ax.fill(angles, evaluation, alpha=0.2, color='#dc2626')

    ax.plot(angles, hitl, 'd-', linewidth=2.5, label='HITL (5)', color='#059669')
    ax.fill(angles, hitl, alpha=0.2, color='#059669')

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, size=11, fontweight='bold')
    ax.set_ylim(0, 5)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_yticklabels(['1', '2', '3', '4', '5'], size=9)
    ax.set_title('Cross-Cutting Themes by Paper Category\\n(Relative Strength)',
                 size=16, fontweight='bold', pad=30)
    ax.legend(loc='upper right', bbox_to_anchor=(1.35, 1.15), fontsize=11)
    ax.grid(True, linestyle='--', alpha=0.5)

    plt.tight_layout()
    plt.savefig(output_dir / 'radar_chart.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Created: radar_chart.png")


# ============================================================================
# 5. PIE CHART - Simple Theme Distribution
# ============================================================================

def create_pie_chart():
    themes = ['Data Management\nfor Agentic Systems',
              'Agentic Systems\nfor Data Management',
              'Evaluation &\nReliability',
              'Human-Centered &\nHuman-in-Loop']
    sizes = [5, 3, 1, 5]
    colors = ['#2563eb', '#7c3aed', '#dc2626', '#059669']
    explode = (0.05, 0.05, 0.1, 0.05)  # Explode evaluation slice

    fig, ax = plt.subplots(figsize=(10, 8))

    wedges, texts, autotexts = ax.pie(sizes, explode=explode, labels=themes,
                                        colors=colors, autopct='%1.0f%%',
                                        startangle=90, textprops={'fontsize': 11},
                                        pctdistance=0.85)

    # Make percentage text bold and white
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontweight('bold')
        autotext.set_fontsize(13)

    # Make labels bold
    for text in texts:
        text.set_fontweight('bold')

    ax.set_title('DASHSys 2026: Theme Distribution (12 Accepted Papers)',
                 fontsize=16, fontweight='bold', pad=20)

    # Add center circle for donut chart effect
    centre_circle = plt.Circle((0, 0), 0.70, fc='white')
    ax.add_artist(centre_circle)

    # Add center text
    ax.text(0, 0, '12\nPapers', ha='center', va='center',
            fontsize=20, fontweight='bold', color='#333')

    plt.tight_layout()
    plt.savefig(output_dir / 'theme_distribution_pie.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Created: theme_distribution_pie.png")


# ============================================================================
# 6. GROUPED BAR - Long vs Short by Theme
# ============================================================================

def create_grouped_bar():
    themes = ['Data Mgmt', 'Agentic Sys', 'Evaluation', 'HITL']
    long_papers = [1, 1, 1, 1]
    short_papers = [4, 2, 0, 4]

    x = np.arange(len(themes))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 7))

    bars1 = ax.bar(x - width/2, long_papers, width, label='Long Papers (8 min)',
                   color='#2563eb', edgecolor='white', linewidth=2)
    bars2 = ax.bar(x + width/2, short_papers, width, label='Short Papers (4 min)',
                   color='#93c5fd', edgecolor='white', linewidth=2)

    ax.set_ylabel('Number of Papers', fontsize=13, fontweight='bold')
    ax.set_title('Paper Length Distribution Across Themes',
                 fontsize=16, fontweight='bold', pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(themes, fontsize=12)
    ax.legend(fontsize=11)
    ax.set_ylim(0, 5)
    ax.grid(axis='y', alpha=0.3, linestyle='--')

    # Add value labels
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                        f'{int(height)}', ha='center', va='bottom',
                        fontweight='bold', fontsize=10)

    plt.tight_layout()
    plt.savefig(output_dir / 'paper_length_by_theme.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Created: paper_length_by_theme.png")


# ============================================================================
# Main execution
# ============================================================================

if __name__ == '__main__':
    print("\n🎨 Generating visualizations for DASHSys 2026...\n")

    create_stacked_bar()
    create_heatmap()
    create_cross_cutting_bars()
    create_radar_chart()
    create_pie_chart()
    create_grouped_bar()

    print(f"\n✅ All visualizations saved to '{output_dir}/' directory")
    print("\nGenerated files:")
    print("  1. theme_distribution_stacked.png")
    print("  2. paper_theme_heatmap.png")
    print("  3. cross_cutting_insights.png")
    print("  4. radar_chart.png")
    print("  5. theme_distribution_pie.png")
    print("  6. paper_length_by_theme.png")
