"""
Generate Charts for Part 3 Report

Creates visual charts from judge results data:
1. Score Distribution Histogram
2. Contradiction Type Pie Chart
3. Consistency by Event Bar Chart
4. Score Distribution Box Plot
"""

import json
from pathlib import Path
from typing import Dict, List
import sys

# Add project root to path
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root))

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: matplotlib not installed. Install with: pip install matplotlib")


def load_json_file(file_path: Path) -> Dict:
    """Load JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def generate_score_distribution_histogram(results: List[Dict], output_dir: Path):
    """Generate histogram of consistency scores."""
    if not MATPLOTLIB_AVAILABLE:
        return None
    
    scores = [r.get('consistency_score', 0) for r in results if isinstance(r, dict)]
    
    if not scores:
        return None
    
    plt.figure(figsize=(10, 6))
    plt.hist(scores, bins=20, edgecolor='black', alpha=0.7, color='steelblue')
    plt.xlabel('Consistency Score', fontsize=12, fontweight='bold')
    plt.ylabel('Number of Comparisons', fontsize=12, fontweight='bold')
    plt.title('Distribution of Consistency Scores', fontsize=14, fontweight='bold')
    plt.grid(axis='y', alpha=0.3)
    
    # Add mean line
    mean_score = sum(scores) / len(scores)
    plt.axvline(mean_score, color='red', linestyle='--', linewidth=2, label=f'Mean: {mean_score:.2f}')
    plt.legend()
    
    output_file = output_dir / "score_distribution.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    return output_file


def generate_contradiction_type_pie_chart(stats: Dict, output_dir: Path):
    """Generate pie chart of contradiction types."""
    if not MATPLOTLIB_AVAILABLE:
        return None
    
    contradiction_dist = stats.get('contradiction_distribution', {})
    if not contradiction_dist:
        return None
    
    labels = list(contradiction_dist.keys())
    sizes = list(contradiction_dist.values())
    colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#ffeaa7']
    
    plt.figure(figsize=(10, 8))
    plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=colors[:len(labels)])
    plt.title('Contradiction Type Distribution', fontsize=14, fontweight='bold')
    plt.axis('equal')
    
    output_file = output_dir / "contradiction_types.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    return output_file


def generate_consistency_by_event_bar_chart(results: List[Dict], output_dir: Path):
    """Generate bar chart comparing consistency scores by event."""
    if not MATPLOTLIB_AVAILABLE:
        return None
    
    # Group by event
    from collections import defaultdict
    event_scores = defaultdict(list)
    
    for result in results:
        if isinstance(result, dict):
            event_name = result.get('event_name', 'Unknown')
            score = result.get('consistency_score', 0)
            event_scores[event_name].append(score)
    
    if not event_scores:
        return None
    
    # Calculate means
    events = []
    means = []
    std_devs = []
    
    for event_name, scores in sorted(event_scores.items()):
        if scores:
            events.append(event_name)
            means.append(sum(scores) / len(scores))
            std_devs.append((sum((x - sum(scores)/len(scores))**2 for x in scores) / len(scores))**0.5 if len(scores) > 1 else 0)
    
    plt.figure(figsize=(12, 6))
    x_pos = np.arange(len(events))
    bars = plt.bar(x_pos, means, yerr=std_devs, capsize=5, alpha=0.7, color='steelblue', edgecolor='black')
    plt.xlabel('Event', fontsize=12, fontweight='bold')
    plt.ylabel('Average Consistency Score', fontsize=12, fontweight='bold')
    plt.title('Average Consistency Score by Event', fontsize=14, fontweight='bold')
    plt.xticks(x_pos, events, rotation=45, ha='right')
    plt.grid(axis='y', alpha=0.3)
    plt.ylim(0, 100)
    
    # Add value labels on bars
    for i, (bar, mean) in enumerate(zip(bars, means)):
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{mean:.1f}',
                ha='center', va='bottom', fontweight='bold')
    
    output_file = output_dir / "consistency_by_event.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    return output_file


def generate_score_distribution_box_plot(results: List[Dict], output_dir: Path):
    """Generate box plot showing score distribution by event."""
    if not MATPLOTLIB_AVAILABLE:
        return None
    
    # Group by event
    from collections import defaultdict
    event_scores = defaultdict(list)
    
    for result in results:
        if isinstance(result, dict):
            event_name = result.get('event_name', 'Unknown')
            score = result.get('consistency_score', 0)
            event_scores[event_name].append(score)
    
    if not event_scores:
        return None
    
    events = []
    score_lists = []
    
    for event_name, scores in sorted(event_scores.items()):
        if scores:
            events.append(event_name)
            score_lists.append(scores)
    
    plt.figure(figsize=(12, 6))
    bp = plt.boxplot(score_lists, labels=events, patch_artist=True)
    
    # Color the boxes
    colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#ffeaa7']
    for patch, color in zip(bp['boxes'], colors[:len(bp['boxes'])]):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    
    plt.xlabel('Event', fontsize=12, fontweight='bold')
    plt.ylabel('Consistency Score', fontsize=12, fontweight='bold')
    plt.title('Consistency Score Distribution by Event (Box Plot)', fontsize=14, fontweight='bold')
    plt.xticks(rotation=45, ha='right')
    plt.grid(axis='y', alpha=0.3)
    plt.ylim(0, 100)
    
    output_file = output_dir / "score_distribution_boxplot.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    return output_file


def generate_all_charts(output_dir: Path = None):
    """Generate all charts and return paths."""
    if not MATPLOTLIB_AVAILABLE:
        print("[WARNING] matplotlib not available. Install with: pip install matplotlib")
        return {}
    
    if output_dir is None:
        project_root = Path(__file__).parent.parent.parent
        output_dir = project_root / "reports" / "charts"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load data
    project_root = Path(__file__).parent.parent.parent
    results_file = project_root / "data" / "judge_results" / "judge_comparisons.json"
    stats_file = project_root / "data" / "judge_results" / "statistical_validation.json"
    
    results = load_json_file(results_file)
    stats = load_json_file(stats_file)
    
    if not results:
        print("[ERROR] No judge results found. Run Part 3 main script first.")
        return {}
    
    chart_paths = {}
    
    print("Generating charts...")
    
    # Generate charts
    if isinstance(results, list):
        chart1 = generate_score_distribution_histogram(results, output_dir)
        if chart1:
            chart_paths['score_distribution'] = chart1
            print(f"  [OK] Score distribution histogram: {chart1.name}")
        
        chart2 = generate_consistency_by_event_bar_chart(results, output_dir)
        if chart2:
            chart_paths['consistency_by_event'] = chart2
            print(f"  [OK] Consistency by event: {chart2.name}")
        
        chart3 = generate_score_distribution_box_plot(results, output_dir)
        if chart3:
            chart_paths['score_boxplot'] = chart3
            print(f"  [OK] Score distribution box plot: {chart3.name}")
    
    if stats:
        chart4 = generate_contradiction_type_pie_chart(stats, output_dir)
        if chart4:
            chart_paths['contradiction_types'] = chart4
            print(f"  [OK] Contradiction types pie chart: {chart4.name}")
    
    print(f"\n[OK] Generated {len(chart_paths)} charts in {output_dir}")
    
    return chart_paths


if __name__ == "__main__":
    chart_paths = generate_all_charts()
    if chart_paths:
        print("\nGenerated charts:")
        for name, path in chart_paths.items():
            print(f"  - {name}: {path}")

