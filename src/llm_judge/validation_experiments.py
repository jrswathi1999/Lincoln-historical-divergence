"""
Part 3B: Statistical Validation Experiments

Implements the three required validation experiments:
1. Prompt Robustness (Ablation Study)
2. Self-Consistency (Reliability)
3. Inter-Rater Agreement (Cohen's Kappa)
"""

import json
import time
import statistics
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
import sys

# Add project root to path
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root))

from src.llm_judge.llm_judge import LLMJudge
from src.llm_judge.statistics import calculate_cohens_kappa, calculate_variance


class PromptStrategy:
    """Different prompt strategies for ablation study."""
    
    ZERO_SHOT = "zero_shot"  # Current prompt (no examples, no CoT)
    CHAIN_OF_THOUGHT = "chain_of_thought"  # Add step-by-step reasoning
    FEW_SHOT = "few_shot"  # Add examples before the task


def load_judge_results(results_file: Path) -> List[Dict]:
    """Load existing judge results."""
    try:
        with open(results_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] Results file not found: {results_file}")
        return []


def load_extractions(extractions_file: Path) -> List[Dict]:
    """Load event extractions."""
    try:
        with open(extractions_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] Extractions file not found: {extractions_file}")
        return []


class ValidationJudge(LLMJudge):
    """Extended judge with different prompt strategies."""
    
    def __init__(self, model: str = "gpt-4o-mini", api_key: Optional[str] = None, 
                 prompt_strategy: str = PromptStrategy.ZERO_SHOT, temperature: float = 0.3):
        super().__init__(model=model, api_key=api_key)
        self.prompt_strategy = prompt_strategy
        self.temperature = temperature
    
    def _load_prompt_template(self) -> str:
        """Load prompt template based on strategy."""
        script_dir = Path(__file__).parent
        
        if self.prompt_strategy == PromptStrategy.ZERO_SHOT:
            # Use default prompt
            return super()._load_prompt_template()
        elif self.prompt_strategy == PromptStrategy.CHAIN_OF_THOUGHT:
            # Load CoT prompt
            prompt_file = script_dir / "judge_prompt_cot.txt"
            if prompt_file.exists():
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                # Generate CoT prompt dynamically
                base_prompt = super()._load_prompt_template()
                cot_instruction = """
IMPORTANT: Before providing your final answer, think through your reasoning step-by-step:
1. First, identify all factual claims in both accounts
2. Compare each claim for consistency
3. Identify any contradictions and classify them
4. Consider omissions (information in one account but not the other)
5. Calculate the consistency score based on your analysis
6. Provide your final evaluation

Now proceed with your step-by-step analysis:
"""
                return base_prompt.replace("INSTRUCTIONS:", cot_instruction + "\nINSTRUCTIONS:")
        elif self.prompt_strategy == PromptStrategy.FEW_SHOT:
            # Load few-shot prompt
            prompt_file = script_dir / "judge_prompt_fewshot.txt"
            if prompt_file.exists():
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                # Generate few-shot prompt dynamically
                base_prompt = super()._load_prompt_template()
                examples = """
EXAMPLES:

Example 1:
Event: Fort Sumter Decision
Account 1 Claims: ["Lincoln decided to resupply", "Date: April 12, 1861"]
Account 2 Claims: ["Lincoln decided to resupply", "Date: April 12, 1861"]
Result: consistency_score=95, contradiction_type="None" (perfect alignment)

Example 2:
Event: Gettysburg Address
Account 1 Claims: ["Speech was 272 words", "Date: November 19, 1863"]
Account 2 Claims: ["Speech was 300 words", "Date: November 19, 1863"]
Result: consistency_score=85, contradiction_type="Factual" (minor factual difference in word count)

Example 3:
Event: Election Night 1860
Account 1 Claims: ["Lincoln was at home", "Heard results by telegram"]
Account 2 Claims: ["Lincoln was at home"]
Result: consistency_score=70, contradiction_type="Omission" (Account 2 missing detail about telegram)

Now evaluate the following:

"""
                return examples + "\n" + base_prompt
        else:
            return super()._load_prompt_template()
    
    def compare_accounts(self, event_name: str, lincoln_extraction: Dict, 
                        other_extraction: Dict) -> Optional[object]:
        """Override to use custom temperature."""
        if not self.client:
            return None
        
        # Extract information
        lincoln_author = lincoln_extraction.get('author', 'Abraham Lincoln')
        lincoln_claims = lincoln_extraction.get('claims', [])
        lincoln_temporal = lincoln_extraction.get('temporal_details', {})
        lincoln_tone = lincoln_extraction.get('tone', 'Unknown')
        
        other_author = other_extraction.get('author', 'Unknown')
        other_claims = other_extraction.get('claims', [])
        other_temporal = other_extraction.get('temporal_details', {})
        other_tone = other_extraction.get('tone', 'Unknown')
        
        # Load and format prompt
        template = self._load_prompt_template()
        prompt = template.format(
            event_name=event_name,
            lincoln_author=lincoln_author,
            lincoln_claims=self._format_claims(lincoln_claims),
            lincoln_temporal=self._format_temporal(lincoln_temporal),
            lincoln_tone=lincoln_tone,
            other_author=other_author,
            other_claims=self._format_claims(other_claims),
            other_temporal=self._format_temporal(other_temporal),
            other_tone=other_tone
        )
        
        max_retries = 3
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                from src.llm_judge.models import JudgeResult
                result: JudgeResult = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an expert historian evaluating historiographical divergence between accounts of historical events. Be objective, fair, and focus on factual consistency."},
                        {"role": "user", "content": prompt}
                    ],
                    response_model=JudgeResult,
                    temperature=self.temperature,  # Use custom temperature
                )
                return result
            except Exception as e:
                error_str = str(e)
                if 'rate_limit' in error_str.lower() or '429' in error_str:
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)
                        time.sleep(wait_time)
                        continue
                    else:
                        return None
                else:
                    if attempt == 0:
                        print(f"  [ERROR] Judge comparison failed: {type(e).__name__}")
                    return None
        
        return None


def experiment_1_prompt_robustness(sample_pairs: List[Dict], output_dir: Path) -> Dict:
    """
    Experiment 1: Prompt Robustness (Ablation Study)
    
    Compare 3 prompt strategies on the same sample pairs.
    """
    print("\n" + "=" * 70)
    print("EXPERIMENT 1: Prompt Robustness (Ablation Study)")
    print("=" * 70)
    print(f"Testing {len(sample_pairs)} sample pairs with 3 prompt strategies...")
    
    strategies = [
        PromptStrategy.ZERO_SHOT,
        PromptStrategy.CHAIN_OF_THOUGHT,
        PromptStrategy.FEW_SHOT
    ]
    
    results_by_strategy = {}
    
    for strategy in strategies:
        print(f"\n[STRATEGY] {strategy.replace('_', ' ').title()}...")
        judge = ValidationJudge(model="gpt-4o-mini", prompt_strategy=strategy, temperature=0.3)
        
        strategy_results = []
        for i, pair in enumerate(sample_pairs):
            print(f"  Processing pair {i+1}/{len(sample_pairs)}...", end='\r')
            result = judge.compare_accounts(
                event_name=pair['event_name'],
                lincoln_extraction=pair['lincoln_extraction'],
                other_extraction=pair['other_extraction']
            )
            if result:
                strategy_results.append({
                    'pair_id': f"{pair['event_id']}_{pair['lincoln_author']}_{pair['other_author']}",
                    'consistency_score': result.consistency_score,
                    'contradiction_type': result.contradiction_type.type
                })
            time.sleep(0.5)  # Rate limiting
        
        results_by_strategy[strategy] = strategy_results
        print(f"\n  [OK] Completed {len(strategy_results)} comparisons")
    
    # Calculate statistics for each strategy
    strategy_stats = {}
    for strategy, results in results_by_strategy.items():
        scores = [r['consistency_score'] for r in results]
        if scores:
            strategy_stats[strategy] = {
                'mean': statistics.mean(scores),
                'std_dev': statistics.stdev(scores) if len(scores) > 1 else 0.0,
                'variance': statistics.variance(scores) if len(scores) > 1 else 0.0,
                'min': min(scores),
                'max': max(scores),
                'count': len(scores)
            }
    
    # Compare stability (lower std_dev = more stable)
    stability_ranking = sorted(
        strategy_stats.items(),
        key=lambda x: x[1]['std_dev']
    )
    
    experiment_results = {
        'experiment': 'prompt_robustness',
        'sample_size': len(sample_pairs),
        'strategies_tested': strategies,
        'results_by_strategy': results_by_strategy,
        'statistics_by_strategy': strategy_stats,
        'stability_ranking': [
            {'strategy': s, 'std_dev': stats['std_dev']}
            for s, stats in stability_ranking
        ],
        'most_stable': stability_ranking[0][0] if stability_ranking else None
    }
    
    # Save results
    output_file = output_dir / "experiment_1_prompt_robustness.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(experiment_results, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 70)
    print("EXPERIMENT 1 RESULTS:")
    print("=" * 70)
    for strategy, stats in strategy_stats.items():
        print(f"\n{strategy.replace('_', ' ').title()}:")
        print(f"  Mean Score: {stats['mean']:.2f}")
        print(f"  Std Dev: {stats['std_dev']:.2f}")
        print(f"  Range: {stats['min']}-{stats['max']}")
    
    print(f"\nMost Stable Strategy: {experiment_results['most_stable']}")
    print(f"Results saved to: {output_file}")
    
    return experiment_results


def experiment_2_self_consistency(sample_pairs: List[Dict], output_dir: Path, num_runs: int = 5) -> Dict:
    """
    Experiment 2: Self-Consistency (Reliability)
    
    Run the same comparison 5 times with temperature > 0.
    Calculate standard deviation of scores.
    """
    print("\n" + "=" * 70)
    print("EXPERIMENT 2: Self-Consistency (Reliability)")
    print("=" * 70)
    print(f"Running each of {len(sample_pairs)} pairs {num_runs} times with temperature=0.7...")
    
    judge = ValidationJudge(model="gpt-4o-mini", temperature=0.7)  # Higher temperature for variability
    
    all_pair_results = []
    
    for pair_idx, pair in enumerate(sample_pairs):
        print(f"\n[PAIR {pair_idx+1}/{len(sample_pairs)}] {pair['event_name']}...")
        pair_scores = []
        
        for run in range(num_runs):
            print(f"  Run {run+1}/{num_runs}...", end='\r')
            result = judge.compare_accounts(
                event_name=pair['event_name'],
                lincoln_extraction=pair['lincoln_extraction'],
                other_extraction=pair['other_extraction']
            )
            if result:
                pair_scores.append(result.consistency_score)
            time.sleep(0.5)  # Rate limiting
        
        if pair_scores:
            pair_stats = {
                'pair_id': f"{pair['event_id']}_{pair['lincoln_author']}_{pair['other_author']}",
                'event_name': pair['event_name'],
                'scores': pair_scores,
                'mean': statistics.mean(pair_scores),
                'std_dev': statistics.stdev(pair_scores) if len(pair_scores) > 1 else 0.0,
                'variance': statistics.variance(pair_scores) if len(pair_scores) > 1 else 0.0,
                'min': min(pair_scores),
                'max': max(pair_scores),
                'range': max(pair_scores) - min(pair_scores)
            }
            all_pair_results.append(pair_stats)
            print(f"  Mean: {pair_stats['mean']:.2f}, Std Dev: {pair_stats['std_dev']:.2f}, Range: {pair_stats['range']}")
    
    # Overall statistics
    all_std_devs = [r['std_dev'] for r in all_pair_results]
    all_ranges = [r['range'] for r in all_pair_results]
    
    experiment_results = {
        'experiment': 'self_consistency',
        'sample_size': len(sample_pairs),
        'num_runs_per_pair': num_runs,
        'temperature': 0.7,
        'pair_results': all_pair_results,
        'overall_statistics': {
            'mean_std_dev': statistics.mean(all_std_devs) if all_std_devs else 0.0,
            'mean_range': statistics.mean(all_ranges) if all_ranges else 0.0,
            'max_std_dev': max(all_std_devs) if all_std_devs else 0.0,
            'min_std_dev': min(all_std_devs) if all_std_devs else 0.0,
            'judge_reliability': 'high' if statistics.mean(all_std_devs) < 5 else 'medium' if statistics.mean(all_std_devs) < 10 else 'low'
        }
    }
    
    # Save results
    output_file = output_dir / "experiment_2_self_consistency.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(experiment_results, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 70)
    print("EXPERIMENT 2 RESULTS:")
    print("=" * 70)
    print(f"Mean Std Dev across all pairs: {experiment_results['overall_statistics']['mean_std_dev']:.2f}")
    print(f"Mean Range across all pairs: {experiment_results['overall_statistics']['mean_range']:.2f}")
    print(f"Judge Reliability: {experiment_results['overall_statistics']['judge_reliability']}")
    print(f"Results saved to: {output_file}")
    
    return experiment_results


def experiment_3_inter_rater_agreement(manual_labels_file: Path, 
                                       sample_pairs: List[Dict], 
                                       output_dir: Path) -> Dict:
    """
    Experiment 3: Inter-Rater Agreement (Cohen's Kappa)
    
    Compare LLM Judge with manual labels.
    """
    print("\n" + "=" * 70)
    print("EXPERIMENT 3: Inter-Rater Agreement (Cohen's Kappa)")
    print("=" * 70)
    
    # Load manual labels
    if not manual_labels_file.exists():
        print(f"[WARNING] Manual labels file not found: {manual_labels_file}")
        print("Creating template for manual labeling...")
        create_manual_labeling_template(sample_pairs[:10], manual_labels_file)
        print(f"Please manually label the pairs in: {manual_labels_file}")
        print("Then run this experiment again.")
        return {}
    
    with open(manual_labels_file, 'r', encoding='utf-8') as f:
        manual_labels = json.load(f)
    
    print(f"Loaded {len(manual_labels)} manual labels")
    
    # Get LLM predictions for the same pairs
    judge = ValidationJudge(model="gpt-4o-mini", temperature=0.3)
    
    llm_predictions = []
    manual_ratings = []
    
    for label_entry in manual_labels:
        pair_id = label_entry.get('pair_id')
        manual_score = label_entry.get('consistency_score')
        manual_category = label_entry.get('category')  # 'Consistent' or 'Contradictory'
        
        # Find matching pair
        matching_pair = None
        for pair in sample_pairs:
            pair_id_check = f"{pair['event_id']}_{pair['lincoln_author']}_{pair['other_author']}"
            if pair_id_check == pair_id:
                matching_pair = pair
                break
        
        if matching_pair and manual_score is not None:
            # Get LLM prediction
            result = judge.compare_accounts(
                event_name=matching_pair['event_name'],
                lincoln_extraction=matching_pair['lincoln_extraction'],
                other_extraction=matching_pair['other_extraction']
            )
            
            if result:
                llm_score = result.consistency_score
                llm_category = 'Consistent' if llm_score >= 50 else 'Contradictory'
                
                llm_predictions.append(llm_score)
                manual_ratings.append(manual_score)
                
                time.sleep(0.5)  # Rate limiting
    
    if len(llm_predictions) < 2:
        print("[ERROR] Need at least 2 labeled pairs for Cohen's Kappa")
        return {}
    
    # Calculate Cohen's Kappa
    kappa = calculate_cohens_kappa(manual_ratings, llm_predictions)
    
    # Also calculate correlation
    if len(llm_predictions) > 1:
        correlation = statistics.correlation(manual_ratings, llm_predictions) if hasattr(statistics, 'correlation') else None
    else:
        correlation = None
    
    experiment_results = {
        'experiment': 'inter_rater_agreement',
        'sample_size': len(llm_predictions),
        'cohens_kappa': kappa,
        'correlation': correlation,
        'human_alignment': 'excellent' if kappa > 0.75 else 'good' if kappa > 0.6 else 'moderate' if kappa > 0.4 else 'poor',
        'manual_ratings': manual_ratings,
        'llm_predictions': llm_predictions
    }
    
    # Save results
    output_file = output_dir / "experiment_3_inter_rater_agreement.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(experiment_results, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 70)
    print("EXPERIMENT 3 RESULTS:")
    print("=" * 70)
    print(f"Cohen's Kappa: {kappa:.3f}")
    if correlation:
        print(f"Correlation: {correlation:.3f}")
    print(f"Human Alignment: {experiment_results['human_alignment']}")
    print(f"Results saved to: {output_file}")
    
    return experiment_results


def create_manual_labeling_template(sample_pairs: List[Dict], output_file: Path):
    """Create a template file for manual labeling."""
    template_entries = []
    
    for pair in sample_pairs:
        pair_id = f"{pair['event_id']}_{pair['lincoln_author']}_{pair['other_author']}"
        template_entries.append({
            'pair_id': pair_id,
            'event_name': pair['event_name'],
            'lincoln_author': pair['lincoln_author'],
            'other_author': pair['other_author'],
            'lincoln_claims': pair['lincoln_extraction'].get('claims', [])[:3],  # First 3 claims
            'other_claims': pair['other_extraction'].get('claims', [])[:3],
            'consistency_score': None,  # Fill in: 0-100
            'category': None,  # Fill in: 'Consistent' or 'Contradictory'
            'notes': ''  # Optional notes
        })
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(template_entries, f, indent=2, ensure_ascii=False)
    
    print(f"Created manual labeling template: {output_file}")
    print("Please fill in 'consistency_score' (0-100) and 'category' ('Consistent' or 'Contradictory') for each pair")


def run_all_experiments(sample_size: int = 20):
    """Run all three validation experiments."""
    project_root = Path(__file__).parent.parent.parent
    
    # Paths
    extractions_file = project_root / "data" / "extracted" / "event_extractions.json"
    results_file = project_root / "data" / "judge_results" / "judge_comparisons.json"
    output_dir = project_root / "data" / "judge_results" / "validation_experiments"
    manual_labels_file = project_root / "data" / "judge_results" / "manual_labels.json"
    
    # Load data
    print("Loading data...")
    extractions = load_extractions(extractions_file)
    
    # Create sample pairs from existing results or generate new ones
    existing_results = load_judge_results(results_file)
    
    # Create sample pairs from extractions
    from src.llm_judge.comparator import ExtractionComparator
    comparator = ExtractionComparator(extractions)
    all_pairs = comparator.create_comparison_pairs()
    
    if len(all_pairs) == 0:
        print(f"[ERROR] No comparison pairs found!")
        print("Make sure Part 2 extracted both Lincoln's accounts and others' accounts.")
        return
    
    if len(all_pairs) >= sample_size:
        sample_pairs = all_pairs[:sample_size]
    else:
        sample_pairs = all_pairs
        print(f"[WARNING] Only {len(all_pairs)} pairs available, using all of them instead of {sample_size}")
    
    print(f"Using {len(sample_pairs)} sample pairs for experiments")
    
    # Run experiments
    exp1_results = experiment_1_prompt_robustness(sample_pairs[:10], output_dir)  # Use 10 for speed
    exp2_results = experiment_2_self_consistency(sample_pairs[:10], output_dir, num_runs=5)
    exp3_results = experiment_3_inter_rater_agreement(manual_labels_file, sample_pairs[:10], output_dir)
    
    # Summary
    print("\n" + "=" * 70)
    print("ALL EXPERIMENTS COMPLETE")
    print("=" * 70)
    print(f"Results saved to: {output_dir}")
    print("\nNext: Generate the report using generate_report.py")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run statistical validation experiments")
    parser.add_argument("--sample-size", type=int, default=20, help="Number of sample pairs to use")
    args = parser.parse_args()
    
    run_all_experiments(sample_size=args.sample_size)

