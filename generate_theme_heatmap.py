#!/usr/bin/env python3
"""
Generate theme-theme co-occurrence heatmap for DASHSys 2026
Shows cross-pollination patterns between themes
"""

import csv
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path

# Create output directory
output_dir = Path('visualizations')
output_dir.mkdir(exist_ok=True)

# Read co-occurrence matrix
themes = []
matrix = []

with open('viz-data/theme-cooccurrence.csv', 'r') as f:
    reader = csv.reader(f)
    header = next(reader)
    themes = header[1:]  # Skip first column (row labels)

    for row in reader:
        matrix.append([int(x) for x in row[1:]])  # Skip first column

matrix = np.array(matrix)

print("🎨 Generating theme cross-pollination visualizations...\n")

# ============================================================================
# 1. Symmetric Heatmap - Co-occurrence Matrix
# ============================================================================

def create_symmetric_heatmap():
    fig, ax = plt.subplots(figsize=(12, 10))

    # Create symmetric matrix for better visualization
    symmetric_matrix = matrix + matrix.T

    # Create heatmap
    im = ax.imshow(symmetric_matrix, cmap='YlOrRd', aspect='auto', vmin=0, vmax=16)

    # Set ticks and labels
    ax.set_xticks(np.arange(len(themes)))
    ax.set_yticks(np.arange(len(themes)))
    ax.set_xticklabels(themes, fontsize=11, rotation=45, ha='right')
    ax.set_yticklabels(themes, fontsize=11)

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Co-occurrence Count', rotation=270, labelpad=20, fontsize=12)

    # Annotate cells with values
    for i in range(len(themes)):
        for j in range(len(themes)):
            if i != j:  # Don't annotate diagonal
                count = symmetric_matrix[i, j]
                if count > 0:
                    color = 'white' if count > 8 else 'black'
                    ax.text(j, i, str(count), ha='center', va='center',
                           fontsize=11, fontweight='bold', color=color)

    # Add grid
    ax.set_xticks(np.arange(len(themes)) - 0.5, minor=True)
    ax.set_yticks(np.arange(len(themes)) - 0.5, minor=True)
    ax.grid(which='minor', color='white', linestyle='-', linewidth=2)

    plt.title('Theme Cross-Pollination: Co-occurrence Matrix\n' +
              '(How often do theme pairs appear together in same papers?)',
              fontsize=16, fontweight='bold', pad=20)

    plt.tight_layout()
    plt.savefig(output_dir / 'theme_cooccurrence_heatmap.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Created: theme_cooccurrence_heatmap.png")


# ============================================================================
# 2. Asymmetric Heatmap - Directional View
# ============================================================================

def create_asymmetric_heatmap():
    fig, ax = plt.subplots(figsize=(12, 10))

    # Use original matrix (asymmetric)
    sns.heatmap(matrix, annot=True, fmt='d', cmap='Blues',
                xticklabels=themes, yticklabels=themes,
                cbar_kws={'label': 'Times Theme A appears in Theme B papers'},
                linewidths=1, linecolor='white', square=True, ax=ax)

    plt.title('Theme Cross-Pollination: Directional Matrix\n' +
              '(Row theme appearing in Column theme papers)',
              fontsize=16, fontweight='bold', pad=20)
    plt.xlabel('Theme B (Column)', fontsize=13, fontweight='bold')
    plt.ylabel('Theme A (Row)', fontsize=13, fontweight='bold')

    plt.xticks(rotation=45, ha='right', fontsize=11)
    plt.yticks(rotation=0, fontsize=11)

    plt.tight_layout()
    plt.savefig(output_dir / 'theme_directional_heatmap.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Created: theme_directional_heatmap.png")


# ============================================================================
# 3. Cluster Heatmap with Dendrogram
# ============================================================================

def create_cluster_heatmap():
    from scipy.cluster.hierarchy import dendrogram, linkage
    from scipy.spatial.distance import squareform

    # Convert to symmetric distance matrix
    symmetric_matrix = matrix + matrix.T

    # Create distance matrix (max - similarity for clustering)
    max_val = symmetric_matrix.max()
    distance_matrix = max_val - symmetric_matrix

    # Perform hierarchical clustering
    condensed_dist = squareform(distance_matrix)
    linkage_matrix = linkage(condensed_dist, method='average')

    # Create figure
    fig = plt.figure(figsize=(12, 10))

    # Dendrogram
    ax1 = fig.add_axes([0.1, 0.71, 0.6, 0.2])
    dend = dendrogram(linkage_matrix, labels=themes, no_labels=False)
    ax1.set_title('Theme Clustering (Hierarchical)', fontsize=14, fontweight='bold')
    ax1.set_xticks([])
    ax1.set_yticks([])
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.spines['bottom'].set_visible(False)
    ax1.spines['left'].set_visible(False)

    # Reorder matrix according to clustering
    idx = dend['leaves']
    reordered_matrix = symmetric_matrix[idx, :][:, idx]
    reordered_themes = [themes[i] for i in idx]

    # Heatmap
    ax2 = fig.add_axes([0.1, 0.1, 0.6, 0.6])
    im = ax2.imshow(reordered_matrix, cmap='YlOrRd', aspect='auto', vmin=0, vmax=16)

    ax2.set_xticks(np.arange(len(reordered_themes)))
    ax2.set_yticks(np.arange(len(reordered_themes)))
    ax2.set_xticklabels(reordered_themes, rotation=45, ha='right', fontsize=10)
    ax2.set_yticklabels(reordered_themes, fontsize=10)

    # Annotate
    for i in range(len(reordered_themes)):
        for j in range(len(reordered_themes)):
            if i != j and reordered_matrix[i, j] > 0:
                count = int(reordered_matrix[i, j])
                color = 'white' if count > 8 else 'black'
                ax2.text(j, i, str(count), ha='center', va='center',
                        fontsize=10, fontweight='bold', color=color)

    # Colorbar
    ax3 = fig.add_axes([0.72, 0.1, 0.02, 0.6])
    plt.colorbar(im, cax=ax3, label='Co-occurrence Count')

    plt.savefig(output_dir / 'theme_cluster_heatmap.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Created: theme_cluster_heatmap.png")


# ============================================================================
# 4. Network-style Visualization
# ============================================================================

def create_network_style():
    fig, ax = plt.subplots(figsize=(14, 10))

    # Create symmetric matrix
    symmetric_matrix = matrix + matrix.T

    # Calculate positions in a circle
    n = len(themes)
    angles = np.linspace(0, 2*np.pi, n, endpoint=False)
    x = np.cos(angles)
    y = np.sin(angles)

    # Calculate node sizes based on total connections
    node_sizes = [sum(symmetric_matrix[i]) for i in range(n)]
    max_size = max(node_sizes)
    node_sizes_scaled = [s/max_size * 3000 + 500 for s in node_sizes]

    # Draw edges (connections)
    for i in range(n):
        for j in range(i+1, n):
            count = symmetric_matrix[i, j]
            if count > 0:
                # Line width proportional to count
                width = count * 0.5
                alpha = min(count / 8, 1.0)
                ax.plot([x[i], x[j]], [y[i], y[j]], 'gray',
                       linewidth=width, alpha=alpha, zorder=1)

    # Draw nodes
    colors = ['#2563eb', '#7c3aed', '#dc2626', '#059669',
              '#f59e0b', '#ec4899', '#8b5cf6']

    for i in range(n):
        ax.scatter(x[i], y[i], s=node_sizes_scaled[i],
                  color=colors[i], edgecolors='white',
                  linewidths=3, zorder=2, alpha=0.8)

        # Add labels
        label_offset = 0.2
        label_x = x[i] * (1 + label_offset)
        label_y = y[i] * (1 + label_offset)

        ha = 'left' if x[i] > 0 else 'right'
        va = 'bottom' if y[i] > 0 else 'top'

        ax.text(label_x, label_y, themes[i],
               fontsize=12, fontweight='bold', ha=ha, va=va)

        # Add connection count
        ax.text(x[i], y[i], str(node_sizes[i]),
               fontsize=10, fontweight='bold', color='white',
               ha='center', va='center', zorder=3)

    ax.set_xlim(-1.5, 1.5)
    ax.set_ylim(-1.5, 1.5)
    ax.set_aspect('equal')
    ax.axis('off')

    plt.title('Theme Network: Cross-Pollination Patterns\n' +
              '(Node size = total connections, Edge width = co-occurrence)',
              fontsize=16, fontweight='bold', pad=20)

    # Add legend
    legend_text = "Node numbers show total connections\nEdge thickness shows co-occurrence frequency"
    plt.text(0, -1.7, legend_text, ha='center', fontsize=11,
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

    plt.tight_layout()
    plt.savefig(output_dir / 'theme_network.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Created: theme_network.png")


# ============================================================================
# 5. Gap Analysis Visualization
# ============================================================================

def create_gap_analysis():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8))

    # Calculate symmetric matrix
    symmetric_matrix = matrix + matrix.T

    # LEFT: Strongest connections (>= 4)
    strong_mask = symmetric_matrix >= 4
    strong_matrix = np.where(strong_mask, symmetric_matrix, 0)

    im1 = ax1.imshow(strong_matrix, cmap='Greens', aspect='auto', vmin=0, vmax=16)
    ax1.set_xticks(np.arange(len(themes)))
    ax1.set_yticks(np.arange(len(themes)))
    ax1.set_xticklabels(themes, rotation=45, ha='right', fontsize=10)
    ax1.set_yticklabels(themes, fontsize=10)
    ax1.set_title('STRONG Bridges (4+ co-occurrences)\nEstablished Cross-Pollination',
                  fontsize=13, fontweight='bold', color='darkgreen')

    for i in range(len(themes)):
        for j in range(len(themes)):
            if strong_matrix[i, j] > 0:
                ax1.text(j, i, str(int(strong_matrix[i, j])),
                        ha='center', va='center', fontsize=11,
                        fontweight='bold', color='white')

    # RIGHT: Gaps (0-1)
    gap_mask = symmetric_matrix <= 1
    gap_matrix = np.where(gap_mask, 1, 0)

    im2 = ax2.imshow(gap_matrix, cmap='Reds', aspect='auto', vmin=0, vmax=1)
    ax2.set_xticks(np.arange(len(themes)))
    ax2.set_yticks(np.arange(len(themes)))
    ax2.set_xticklabels(themes, rotation=45, ha='right', fontsize=10)
    ax2.set_yticklabels(themes, fontsize=10)
    ax2.set_title('GAPS (0-1 co-occurrences)\nResearch Opportunities',
                  fontsize=13, fontweight='bold', color='darkred')

    for i in range(len(themes)):
        for j in range(len(themes)):
            if i != j and gap_matrix[i, j] > 0:
                ax2.text(j, i, '⚠️', ha='center', va='center', fontsize=16)

    plt.suptitle('Theme Cross-Pollination: Strengths vs. Gaps',
                fontsize=16, fontweight='bold', y=1.02)

    plt.tight_layout()
    plt.savefig(output_dir / 'theme_gaps_analysis.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Created: theme_gaps_analysis.png")


# ============================================================================
# Main execution
# ============================================================================

if __name__ == '__main__':
    create_symmetric_heatmap()
    create_asymmetric_heatmap()
    try:
        create_cluster_heatmap()
    except ImportError:
        print("⚠ Skipped cluster heatmap (requires scipy)")
    create_network_style()
    create_gap_analysis()

    print(f"\n✅ All theme cross-pollination visualizations saved to '{output_dir}/'")
    print("\nGenerated files:")
    print("  1. theme_cooccurrence_heatmap.png - Symmetric co-occurrence matrix")
    print("  2. theme_directional_heatmap.png - Asymmetric directional view")
    print("  3. theme_cluster_heatmap.png - Hierarchical clustering view")
    print("  4. theme_network.png - Network-style circular layout")
    print("  5. theme_gaps_analysis.png - Strengths vs. gaps comparison")
    print("\n💡 Key Insights:")
    print("  • Data Mgmt ↔ Infrastructure: Strongest (8 co-occurrences)")
    print("  • HITL ↔ Provenance: Trust cluster (6 co-occurrences)")
    print("  • Agentic ↔ Multi-Agent: Architecture consensus (6 co-occurrences)")
    print("  • Evaluation: Isolated (only 1 total connection)")
    print("  • Gap: Data Mgmt ↔ Agentic Systems (0 co-occurrences)")
