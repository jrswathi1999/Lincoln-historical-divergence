"""
Part 3: LLM Judge & Statistical Validation

Main script that:
1. Loads event extractions from Part 2
2. Groups by event and matches Lincoln vs others
3. Uses LLM Judge to compare accounts
4. Calculates statistical validation metrics
5. Saves results
"""

import json
import sys
from pathlib import Path
from typing import List, Dict
from tqdm import tqdm

# Add project root to path
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root))

from src.llm_judge.llm_judge import LLMJudge
from src.llm_judge.comparator import ExtractionComparator
from src.llm_judge.statistics import calculate_consistency_metrics, calculate_variance


def load_extractions(extractions_file: Path) -> List[Dict]:
    """Load event extractions from Part 2."""
    try:
        with open(extractions_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] Extractions file not found: {extractions_file}")
        print("Please run Part 2 first to generate event_extractions.json")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in {extractions_file}: {e}")
        sys.exit(1)


def save_results(results: List[Dict], output_file: Path):
    """Save judge results to JSON file."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Saved judge results to: {output_file}")


def save_statistics(metrics: Dict, output_file: Path):
    """Save statistical validation metrics to JSON file."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    print(f"[OK] Saved statistics to: {output_file}")


def main():
    """Main execution function."""
    print("=" * 70)
    print("ML Evals Engineer - Lincoln Project")
    print("Part 3: LLM Judge & Statistical Validation")
    print("=" * 70)
    
    # Paths
    project_root = Path(__file__).parent.parent.parent
    extractions_file = project_root / "data" / "extracted" / "event_extractions.json"
    results_file = project_root / "data" / "judge_results" / "judge_comparisons.json"
    stats_file = project_root / "data" / "judge_results" / "statistical_validation.json"
    
    # Step 1: Load extractions
    print("\n[STEP 1] Loading event extractions from Part 2...")
    extractions = load_extractions(extractions_file)
    print(f"[OK] Loaded {len(extractions)} extractions")
    
    # Step 2: Group and create comparison pairs
    print("\n[STEP 2] Creating comparison pairs (Lincoln vs Others)...")
    comparator = ExtractionComparator(extractions)
    pairs = comparator.create_comparison_pairs()
    print(f"[OK] Created {len(pairs)} comparison pairs")
    
    if not pairs:
        print("[WARNING] No comparison pairs found!")
        print("Make sure Part 2 extracted both Lincoln's accounts and others' accounts.")
        sys.exit(1)
    
    # Group pairs by event for better progress tracking
    pairs_by_event = {}
    for pair in pairs:
        event_id = pair['event_id']
        if event_id not in pairs_by_event:
            pairs_by_event[event_id] = []
        pairs_by_event[event_id].append(pair)
    
    print(f"\n[INFO] Comparison pairs by event:")
    for event_id, event_pairs in pairs_by_event.items():
        print(f"  - {event_pairs[0]['event_name']}: {len(event_pairs)} pairs")
    
    # Step 3: Initialize LLM Judge
    print("\n[STEP 3] Initializing LLM Judge...")
    judge = LLMJudge(model="gpt-4o-mini")
    if not judge.client:
        print("[ERROR] LLM Judge not available. Please set OPENAI_API_KEY in .env file")
        sys.exit(1)
    print("[OK] LLM Judge initialized")
    
    # Step 4: Run comparisons
    print("\n[STEP 4] Running LLM Judge comparisons...")
    print("This may take a while depending on the number of pairs...")
    
    all_results = []
    failed_count = 0
    
    # Process by event for better progress tracking
    for event_id, event_pairs in pairs_by_event.items():
        event_name = event_pairs[0]['event_name']
        print(f"\n{'=' * 70}")
        print(f"Processing Event: {event_name}")
        print(f"{'=' * 70}")
        
        for pair in tqdm(event_pairs, desc=f"  Comparing {event_name}"):
            result = judge.compare_accounts(
                event_name=pair['event_name'],
                lincoln_extraction=pair['lincoln_extraction'],
                other_extraction=pair['other_extraction']
            )
            
            if result:
                # Convert Pydantic model to dict for JSON serialization
                result_dict = {
                    'event_id': pair['event_id'],
                    'event_name': pair['event_name'],
                    'lincoln_author': pair['lincoln_author'],
                    'other_author': pair['other_author'],
                    'lincoln_source': pair['lincoln_source'],
                    'other_source': pair['other_source'],
                    'consistency_score': result.consistency_score,
                    'contradiction_type': {
                        'type': result.contradiction_type.type,
                        'explanation': result.contradiction_type.explanation
                    },
                    'reasoning': result.reasoning,
                    'key_differences': result.key_differences,
                    'key_similarities': result.key_similarities
                }
                all_results.append(result_dict)
            else:
                failed_count += 1
    
    print(f"\n[OK] Completed {len(all_results)} comparisons")
    if failed_count > 0:
        print(f"[WARNING] {failed_count} comparisons failed")
    
    # Step 5: Calculate statistics
    print("\n[STEP 5] Calculating statistical validation metrics...")
    metrics = calculate_consistency_metrics(all_results)
    
    print("\n" + "=" * 70)
    print("Statistical Validation Summary")
    print("=" * 70)
    print(f"Total Comparisons: {metrics['total_comparisons']}")
    print(f"Average Consistency Score: {metrics['average_consistency']:.2f}")
    print(f"Score Range: {metrics['consistency_range']}")
    print(f"Standard Deviation: {metrics['score_statistics']['std_dev']:.2f}")
    print("\nContradiction Distribution:")
    for ct_type, count in metrics['contradiction_distribution'].items():
        print(f"  - {ct_type}: {count}")
    
    # Step 6: Save results
    print("\n[STEP 6] Saving results...")
    save_results(all_results, results_file)
    save_statistics(metrics, stats_file)
    
    # Final summary
    print("\n" + "=" * 70)
    print("PART 3 COMPLETE - Summary")
    print("=" * 70)
    print(f"[OK] Judge comparisons: {len(all_results)}")
    print(f"[OK] Results saved to: {results_file}")
    print(f"[OK] Statistics saved to: {stats_file}")
    print("\nNext: Review the results and statistical validation metrics")
    print("=" * 70)


if __name__ == "__main__":
    main()


