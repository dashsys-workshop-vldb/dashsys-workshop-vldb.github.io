#!/usr/bin/env python3
"""
Generate word clouds from DASHSys 2026 paper abstracts
Requires: pip install wordcloud matplotlib
"""

try:
    from wordcloud import WordCloud
    import matplotlib.pyplot as plt
    from pathlib import Path
    import csv
except ImportError:
    print("❌ Missing required libraries.")
    print("Install with: pip install wordcloud matplotlib")
    print("\nAlternatively, use the CSV data with online tools:")
    print("  - wordclouds.com")
    print("  - wordart.com")
    print("  - voyant-tools.org")
    exit(1)

# Create output directory
output_dir = Path('visualizations')
output_dir.mkdir(exist_ok=True)

# Load word frequency data
word_freq = {}
theme_words = {'Data': {}, 'Agent': {}, 'Human': {}, 'Infrastructure': {}, 'Evaluation': {}}

with open('viz-data/wordcloud-data.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        word = row['word']
        freq = int(row['frequency'])
        theme = row['theme']

        word_freq[word] = freq
        if theme in theme_words:
            theme_words[theme][word] = freq

print("🎨 Generating word clouds...\n")

# ============================================================================
# 1. Overall Word Cloud
# ============================================================================

def create_overall_wordcloud():
    wordcloud = WordCloud(
        width=1600,
        height=800,
        background_color='white',
        colormap='viridis',
        relative_scaling=0.5,
        min_font_size=10
    ).generate_from_frequencies(word_freq)

    plt.figure(figsize=(20, 10))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis('off')
    plt.title('DASHSys 2026: Overall Vocabulary from Accepted Papers',
              fontsize=24, fontweight='bold', pad=20)
    plt.tight_layout(pad=0)
    plt.savefig(output_dir / 'wordcloud_overall.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Created: wordcloud_overall.png")

# ============================================================================
# 2. Theme-Based Word Clouds
# ============================================================================

def create_theme_wordclouds():
    colors = {
        'Data': 'Blues',
        'Agent': 'Purples',
        'Human': 'Greens',
        'Infrastructure': 'Oranges',
        'Evaluation': 'Reds'
    }

    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    axes = axes.flatten()

    for idx, (theme, words) in enumerate(theme_words.items()):
        if not words:
            continue

        wordcloud = WordCloud(
            width=800,
            height=600,
            background_color='white',
            colormap=colors[theme],
            relative_scaling=0.5,
            min_font_size=10
        ).generate_from_frequencies(words)

        axes[idx].imshow(wordcloud, interpolation='bilinear')
        axes[idx].axis('off')
        axes[idx].set_title(f'{theme} Terms', fontsize=16, fontweight='bold')

    # Hide the last subplot if odd number
    axes[5].axis('off')

    plt.suptitle('DASHSys 2026: Word Clouds by Theme',
                 fontsize=20, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_dir / 'wordcloud_by_theme.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Created: wordcloud_by_theme.png")

# ============================================================================
# 3. Circular Word Cloud (Data-Centric)
# ============================================================================

def create_circular_wordcloud():
    from PIL import Image
    import numpy as np

    # Create circular mask
    x, y = np.ogrid[:800, :800]
    mask = (x - 400) ** 2 + (y - 400) ** 2 > 390 ** 2
    mask = 255 * mask.astype(int)

    wordcloud = WordCloud(
        width=800,
        height=800,
        background_color='white',
        colormap='plasma',
        mask=mask,
        relative_scaling=0.5,
        min_font_size=10,
        contour_width=3,
        contour_color='steelblue'
    ).generate_from_frequencies(word_freq)

    plt.figure(figsize=(12, 12))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis('off')
    plt.title('DASHSys 2026: Key Concepts (Circular Layout)',
              fontsize=20, fontweight='bold', pad=20)
    plt.tight_layout(pad=0)
    plt.savefig(output_dir / 'wordcloud_circular.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Created: wordcloud_circular.png")

# ============================================================================
# 4. Comparison Cloud (Top 20 vs Rest)
# ============================================================================

def create_comparison_wordcloud():
    # Top 20 words
    top_words = dict(sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:20])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 8))

    # Top 20
    wc1 = WordCloud(
        width=800, height=600,
        background_color='white',
        colormap='cool',
        relative_scaling=0.5
    ).generate_from_frequencies(top_words)

    ax1.imshow(wc1, interpolation='bilinear')
    ax1.axis('off')
    ax1.set_title('Most Frequent Terms (Top 20)', fontsize=16, fontweight='bold')

    # Remaining words
    rest_words = {k: v for k, v in word_freq.items() if k not in top_words}
    wc2 = WordCloud(
        width=800, height=600,
        background_color='white',
        colormap='warm',
        relative_scaling=0.5
    ).generate_from_frequencies(rest_words)

    ax2.imshow(wc2, interpolation='bilinear')
    ax2.axis('off')
    ax2.set_title('Supporting Terms', fontsize=16, fontweight='bold')

    plt.suptitle('DASHSys 2026: Core vs. Supporting Vocabulary',
                 fontsize=20, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_dir / 'wordcloud_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Created: wordcloud_comparison.png")

# ============================================================================
# Main execution
# ============================================================================

if __name__ == '__main__':
    create_overall_wordcloud()
    create_theme_wordclouds()
    create_circular_wordcloud()
    create_comparison_wordcloud()

    print(f"\n✅ All word clouds saved to '{output_dir}/' directory")
    print("\nGenerated files:")
    print("  1. wordcloud_overall.png - All terms")
    print("  2. wordcloud_by_theme.png - Separated by theme")
    print("  3. wordcloud_circular.png - Circular layout")
    print("  4. wordcloud_comparison.png - Top 20 vs rest")
    print("\n💡 Tip: Upload viz-data/wordcloud-data.csv to wordclouds.com")
    print("   for more customization options!")
