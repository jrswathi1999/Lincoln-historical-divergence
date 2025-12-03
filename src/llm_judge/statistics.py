"""
Statistical Validation for LLM Judge

Computes reliability metrics to validate the judge's consistency:
- Cohen's Kappa (inter-rater agreement if multiple runs)
- Variance/Standard Deviation (consistency across runs)
- Score distribution analysis
"""

from typing import List, Dict
import statistics
from collections import Counter


def calculate_cohens_kappa(ratings1: List[int], ratings2: List[int]) -> float:
    """
    Calculate Cohen's Kappa for inter-rater agreement.
    
    Args:
        ratings1: First set of ratings (0-100 scores)
        ratings2: Second set of ratings (0-100 scores)
        
    Returns:
        Cohen's Kappa value (-1 to 1, where 1 is perfect agreement)
    """
    if len(ratings1) != len(ratings2):
        raise ValueError("Ratings must have same length")
    
    # Convert to categorical (bins: 0-25, 26-50, 51-75, 76-100)
    def categorize(score):
        if score <= 25:
            return 'low'
        elif score <= 50:
            return 'medium-low'
        elif score <= 75:
            return 'medium-high'
        else:
            return 'high'
    
    cats1 = [categorize(r) for r in ratings1]
    cats2 = [categorize(r) for r in ratings2]
    
    # Calculate observed agreement
    n = len(cats1)
    observed_agreement = sum(1 for c1, c2 in zip(cats1, cats2) if c1 == c2) / n
    
    # Calculate expected agreement (chance agreement)
    cat_counts1 = Counter(cats1)
    cat_counts2 = Counter(cats2)
    expected_agreement = sum(
        (cat_counts1[cat] / n) * (cat_counts2[cat] / n)
        for cat in set(cats1 + cats2)
    )
    
    # Cohen's Kappa
    if expected_agreement == 1:
        return 1.0
    
    kappa = (observed_agreement - expected_agreement) / (1 - expected_agreement)
    return kappa


def calculate_variance(scores: List[int]) -> Dict[str, float]:
    """
    Calculate variance and standard deviation of consistency scores.
    
    Args:
        scores: List of consistency scores (0-100)
        
    Returns:
        Dictionary with variance, std_dev, mean, min, max
    """
    if not scores:
        return {
            'mean': 0.0,
            'variance': 0.0,
            'std_dev': 0.0,
            'min': 0,
            'max': 0,
            'count': 0
        }
    
    return {
        'mean': statistics.mean(scores),
        'variance': statistics.variance(scores) if len(scores) > 1 else 0.0,
        'std_dev': statistics.stdev(scores) if len(scores) > 1 else 0.0,
        'min': min(scores),
        'max': max(scores),
        'count': len(scores)
    }


def analyze_contradiction_distribution(results: List[Dict]) -> Dict[str, int]:
    """
    Analyze distribution of contradiction types.
    
    Args:
        results: List of judge results with contradiction_type
        
    Returns:
        Dictionary with counts for each contradiction type
    """
    contradiction_types = []
    for result in results:
        if isinstance(result, dict):
            ct = result.get('contradiction_type', {})
            if isinstance(ct, dict):
                ct_type = ct.get('type', 'Unknown')
            else:
                ct_type = str(ct)
        else:
            ct_type = 'Unknown'
        contradiction_types.append(ct_type)
    
    return dict(Counter(contradiction_types))


def calculate_consistency_metrics(results: List[Dict]) -> Dict:
    """
    Calculate overall consistency metrics for the judge.
    
    Args:
        results: List of judge result dictionaries
        
    Returns:
        Dictionary with various consistency metrics
    """
    scores = []
    for result in results:
        if isinstance(result, dict):
            score = result.get('consistency_score', 0)
            if isinstance(score, (int, float)):
                scores.append(int(score))
    
    score_stats = calculate_variance(scores)
    contradiction_dist = analyze_contradiction_distribution(results)
    
    return {
        'score_statistics': score_stats,
        'contradiction_distribution': contradiction_dist,
        'total_comparisons': len(results),
        'average_consistency': score_stats['mean'],
        'consistency_range': f"{score_stats['min']}-{score_stats['max']}"
    }


