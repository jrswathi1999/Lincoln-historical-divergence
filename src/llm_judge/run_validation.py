"""
Run Part 3B: Statistical Validation Experiments and Generate Report

This script:
1. Runs the three required validation experiments
2. Generates the comprehensive report

Usage:
    python -m src.llm_judge.run_validation [--sample-size N] [--skip-experiments] [--skip-report]
    OR
    python src/llm_judge/run_validation.py [--sample-size N] [--skip-experiments] [--skip-report]
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root))

from src.llm_judge.validation_experiments import run_all_experiments
from src.llm_judge.generate_report import generate_markdown_report


def main():
    parser = argparse.ArgumentParser(
        description="Run Part 3B validation experiments and generate report"
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=20,
        help="Number of sample pairs to use for experiments (default: 20)"
    )
    parser.add_argument(
        "--skip-experiments",
        action="store_true",
        help="Skip running experiments (use existing results)"
    )
    parser.add_argument(
        "--skip-report",
        action="store_true",
        help="Skip generating report"
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("Part 3B: Statistical Validation Experiments & Report Generation")
    print("=" * 70)
    
    # Run experiments
    if not args.skip_experiments:
        print("\n[STEP 1] Running validation experiments...")
        print("Note: This will make API calls and may take some time.")
        print("      Experiments use a sample of pairs for efficiency.")
        try:
            run_all_experiments(sample_size=args.sample_size)
        except KeyboardInterrupt:
            print("\n[INTERRUPTED] Experiments stopped by user.")
            print("You can run with --skip-experiments to generate report from existing results.")
            sys.exit(1)
        except Exception as e:
            print(f"\n[ERROR] Experiments failed: {e}")
            print("You can run with --skip-experiments to generate report from existing results.")
            sys.exit(1)
    else:
        print("\n[SKIP] Skipping experiments (using existing results)")
    
    # Generate report
    if not args.skip_report:
        print("\n[STEP 2] Generating comprehensive report...")
        report_file = project_root / "reports" / "FINAL_REPORT.md"
        try:
            generate_markdown_report(report_file)
            print(f"\n[SUCCESS] Report generated: {report_file}")
        except Exception as e:
            print(f"\n[ERROR] Report generation failed: {e}")
            sys.exit(1)
    else:
        print("\n[SKIP] Skipping report generation")
    
    print("\n" + "=" * 70)
    print("COMPLETE")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Review the report: reports/FINAL_REPORT.md")
    print("2. Check experiment results: data/judge_results/validation_experiments/")
    print("3. For manual labeling: Edit data/judge_results/manual_labels.json")
    print("   Then run: python -m src.llm_judge.run_validation --skip-experiments")
    print("   Then run experiment 3 separately")


if __name__ == "__main__":
    main()

