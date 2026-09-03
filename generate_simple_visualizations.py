#!/usr/bin/env python3
"""
Generate visualizations using only matplotlib and numpy (no pandas/seaborn needed)
"""

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Set style
plt.style.use('default')

# Create output directory
output_dir = Path('visualizations')
output_dir.mkdir(exist_ok=True)

print("🎨 Generating visualizations...\n")

# ============================================================================
# 1. STACKED BAR CHART - Theme Distribution by Paper Length
# ============================================================================

def create_stacked_bar():
    themes = ['Data Mgmt\n(42%)', 'Agentic Sys\n(25%)',
              'Evaluation\n(8%)', 'HITL\n(42%)']
    long_papers = [1, 1, 1, 1]
    short_papers = [4, 2, 0, 4]

    x = np.arange(len(themes))
    width = 0.6

    fig, ax = plt.subplots(figsize=(12, 7))

    # Create bars
    p1 = ax.bar(x, long_papers, width, label='Long Papers',
                color='#2563eb', edgecolor='white', linewidth=2)
    p2 = ax.bar(x, short_papers, width, bottom=long_papers,
                label='Short Papers', color='#93c5fd',
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
        ax.text(i, total + 0.15, str(total), ha='center',
                fontweight='bold', fontsize=13)

    plt.tight_layout()
    plt.savefig(output_dir / 'theme_distribution_stacked.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Created: theme_distribution_stacked.png")


# ============================================================================
# 2. HORIZONTAL BAR - Cross-Cutting Insights
# ============================================================================

def create_cross_cutting_bars():
    insights = ['HITL\nDominant', 'Infrastructure\nFoundation',
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
    ax.set_title('Cross-Cutting Insights Across Accepted Papers',
                 fontsize=16, fontweight='bold', pad=20)
    ax.set_xlim(0, 8)
    ax.grid(axis='x', alpha=0.3, linestyle='--')

    plt.tight_layout()
    plt.savefig(output_dir / 'cross_cutting_insights.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Created: cross_cutting_insights.png")


# ============================================================================
# 3. PIE CHART - Theme Distribution
# ============================================================================

def create_pie_chart():
    themes = ['Data Management', 'Agentic Systems', 'Evaluation', 'HITL']
    sizes = [5, 3, 1, 5]
    colors = ['#2563eb', '#7c3aed', '#dc2626', '#059669']
    explode = (0.05, 0.05, 0.1, 0.05)

    fig, ax = plt.subplots(figsize=(10, 8))

    wedges, texts, autotexts = ax.pie(sizes, explode=explode, labels=themes,
                                        colors=colors, autopct='%1.0f%%',
                                        startangle=90, textprops={'fontsize': 12})

    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontweight('bold')
        autotext.set_fontsize(14)

    for text in texts:
        text.set_fontweight('bold')

    ax.set_title('Theme Distribution (12 Accepted Papers)',
                 fontsize=16, fontweight='bold', pad=20)

    plt.tight_layout()
    plt.savefig(output_dir / 'theme_distribution_pie.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Created: theme_distribution_pie.png")


# ============================================================================
# 4. THEME CO-OCCURRENCE HEATMAP
# ============================================================================

def create_theme_heatmap():
    # Theme-theme co-occurrence matrix (from our analysis)
    themes = ['Data\nMgmt', 'Agentic\nSys', 'Eval', 'HITL', 'Infra', 'Multi\nAgent', 'Prov']

    # Symmetric matrix (row i, col j = how often themes i and j appear together)
    matrix = np.array([
        [0,  0,  0,  4,  8,  0,  4],  # Data Mgmt
        [0,  0,  0,  4,  0,  6,  2],  # Agentic Sys
        [0,  0,  0,  0,  0,  0,  2],  # Evaluation
        [4,  4,  0,  0,  4,  4,  6],  # HITL
        [8,  0,  0,  4,  0,  0,  4],  # Infrastructure
        [0,  6,  0,  4,  0,  0,  2],  # Multi-Agent
        [4,  2,  2,  6,  4,  2,  0],  # Provenance
    ])

    fig, ax = plt.subplots(figsize=(12, 10))

    # Create heatmap
    im = ax.imshow(matrix, cmap='YlOrRd', aspect='auto', vmin=0, vmax=8)

    # Set ticks and labels
    ax.set_xticks(np.arange(len(themes)))
    ax.set_yticks(np.arange(len(themes)))
    ax.set_xticklabels(themes, fontsize=11)
    ax.set_yticklabels(themes, fontsize=11)

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Co-occurrence Count', rotation=270, labelpad=20, fontsize=12)

    # Annotate cells with values
    for i in range(len(themes)):
        for j in range(len(themes)):
            if matrix[i, j] > 0:
                color = 'white' if matrix[i, j] > 4 else 'black'
                ax.text(j, i, str(int(matrix[i, j])), ha='center', va='center',
                       fontsize=11, fontweight='bold', color=color)

    # Add grid
    ax.set_xticks(np.arange(len(themes)) - 0.5, minor=True)
    ax.set_yticks(np.arange(len(themes)) - 0.5, minor=True)
    ax.grid(which='minor', color='white', linestyle='-', linewidth=2)

    plt.title('Theme Cross-Pollination: Co-occurrence Matrix\n' +
              'How often do theme pairs appear together?',
              fontsize=16, fontweight='bold', pad=20)

    plt.tight_layout()
    plt.savefig(output_dir / 'theme_cooccurrence_heatmap.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Created: theme_cooccurrence_heatmap.png")


# ============================================================================
# 5. NETWORK DIAGRAM - Theme Connections
# ============================================================================

def create_network_diagram():
    themes = ['Data\nMgmt', 'Agentic\nSys', 'Eval', 'HITL',
              'Infra', 'Multi\nAgent', 'Prov']

    # Total connections per theme
    connections = [8, 6, 1, 11, 8, 6, 10]

    # Co-occurrence matrix
    matrix = np.array([
        [0,  0,  0,  4,  8,  0,  4],
        [0,  0,  0,  4,  0,  6,  2],
        [0,  0,  0,  0,  0,  0,  2],
        [4,  4,  0,  0,  4,  4,  6],
        [8,  0,  0,  4,  0,  0,  4],
        [0,  6,  0,  4,  0,  0,  2],
        [4,  2,  2,  6,  4,  2,  0],
    ])

    fig, ax = plt.subplots(figsize=(14, 10))

    # Calculate positions in a circle
    n = len(themes)
    angles = np.linspace(0, 2*np.pi, n, endpoint=False)
    x = np.cos(angles)
    y = np.sin(angles)

    # Scale node sizes
    max_conn = max(connections)
    node_sizes = [c/max_conn * 3000 + 500 for c in connections]

    # Draw edges
    for i in range(n):
        for j in range(i+1, n):
            count = matrix[i, j]
            if count > 0:
                width = count * 0.5
                alpha = min(count / 8, 1.0)
                ax.plot([x[i], x[j]], [y[i], y[j]], 'gray',
                       linewidth=width, alpha=alpha, zorder=1)

    # Node colors
    colors = ['#2563eb', '#7c3aed', '#dc2626', '#059669',
              '#f59e0b', '#ec4899', '#8b5cf6']

    # Draw nodes
    for i in range(n):
        ax.scatter(x[i], y[i], s=node_sizes[i],
                  color=colors[i], edgecolors='white',
                  linewidths=3, zorder=2, alpha=0.8)

        # Labels
        label_offset = 0.25
        label_x = x[i] * (1 + label_offset)
        label_y = y[i] * (1 + label_offset)

        ha = 'left' if x[i] > 0 else 'right'
        va = 'bottom' if y[i] > 0 else 'top'

        ax.text(label_x, label_y, themes[i],
               fontsize=12, fontweight='bold', ha=ha, va=va)

        # Connection count on node
        ax.text(x[i], y[i], str(connections[i]),
               fontsize=10, fontweight='bold', color='white',
               ha='center', va='center', zorder=3)

    ax.set_xlim(-1.5, 1.5)
    ax.set_ylim(-1.5, 1.5)
    ax.set_aspect('equal')
    ax.axis('off')

    plt.title('Theme Network: Cross-Pollination Patterns\n' +
              'Node size = connections, Edge width = co-occurrence',
              fontsize=16, fontweight='bold', pad=20)

    plt.tight_layout()
    plt.savefig(output_dir / 'theme_network.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Created: theme_network.png")


# ============================================================================
# Main execution
# ============================================================================

if __name__ == '__main__':
    create_stacked_bar()
    create_cross_cutting_bars()
    create_pie_chart()
    create_theme_heatmap()
    create_network_diagram()

    print(f"\n✅ All visualizations saved to '{output_dir}/' directory")
    print("\nGenerated files:")
    print("  1. theme_distribution_stacked.png")
    print("  2. cross_cutting_insights.png")
    print("  3. theme_distribution_pie.png")
    print("  4. theme_cooccurrence_heatmap.png ⭐")
    print("  5. theme_network.png")
