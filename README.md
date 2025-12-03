# ML Evaluation Engineer - Lincoln Project

Automated system to analyze historiographical divergence by comparing Abraham Lincoln's accounts of historical events with those of other authors.

## Project Overview

This project builds an LLM-based evaluation system that:
1. **Acquires** historical documents from Project Gutenberg and Library of Congress
2. **Extracts** structured information about 5 key historical events
3. **Evaluates** consistency between Lincoln's accounts and other authors' accounts
4. **Validates** the evaluation system using statistical methods

## Key Events Analyzed

1. Election Night 1860
2. Fort Sumter Decision
3. Gettysburg Address
4. Second Inaugural Address
5. Ford's Theatre Assassination

## Project Structure

```
memomachine/
├── src/
│   ├── data_acquisition/     # Part 1: Data scraping and normalization
│   ├── event_extraction/     # Part 2: Event extraction using LLM
│   └── llm_judge/            # Part 3: LLM Judge and validation
├── data/
│   ├── raw/                  # Raw scraped documents
│   ├── normalized/           # Normalized JSON datasets
│   ├── extracted/            # Event extraction results
│   └── judge_results/        # Judge comparison results and validation
├── reports/
│   ├── FINAL_REPORT.md       # Comprehensive analysis report
│   └── charts/               # Visualization charts
└── requirements.txt          # Python dependencies
```

## Setup

### Prerequisites

- Python 3.10 or higher
- OpenAI API key (for LLM calls)

### Installation

1. **Clone the repository** (or navigate to project directory)

2. **Create a virtual environment**:
```bash
python -m venv venv
```

3. **Activate the virtual environment**:
   - Windows (PowerShell): `.\venv\Scripts\Activate.ps1`
   - Windows (CMD): `venv\Scripts\activate.bat`
   - Linux/Mac: `source venv/bin/activate`

4. **Install dependencies**:
```bash
pip install -r requirements.txt
```

5. **Set up environment variables**:
   Create a `.env` file in the project root:
```
OPENAI_API_KEY=your_api_key_here
```

## Usage

### Part 1: Data Acquisition & Normalization

Scrapes and normalizes documents from Project Gutenberg and Library of Congress.

```bash
python src/data_acquisition/main.py
```

**Output**: 
- `data/raw/gutenberg/` - Raw Project Gutenberg books
- `data/raw/loc/` - Raw Library of Congress documents
- `data/normalized/gutenberg_dataset.json` - Normalized Gutenberg dataset
- `data/normalized/loc_dataset.json` - Normalized LoC dataset

**Note**: LoC documents require separate normalization:
```bash
python src/data_acquisition/normalize_loc_documents.py
```

### Part 2: Event Extraction

Extracts structured information about the 5 key events from all documents.

```bash
python src/event_extraction/main.py
```

**Output**: 
- `data/extracted/event_extractions.json` - All event extractions

**Features**:
- Handles long documents with chunking and keyword filtering
- Parallel processing for faster extraction
- Incremental saving (resume if interrupted)

### Part 3: LLM Judge & Statistical Validation

Compares accounts and validates the judge system.

#### Step 1: Run Judge Comparisons

```bash
python src/llm_judge/main.py
```

**Output**: 
- `data/judge_results/judge_comparisons.json` - All comparison results
- `data/judge_results/statistical_validation.json` - Statistical summary

#### Step 2: Run Validation Experiments

```bash
python -m src.llm_judge.run_validation --sample-size 20
```

This runs three validation experiments:
1. **Prompt Robustness**: Compares 3 prompt strategies
2. **Self-Consistency**: Tests reliability across multiple runs
3. **Inter-Rater Agreement**: Requires manual labeling (see below)

**Output**: 
- `data/judge_results/validation_experiments/` - Experiment results

#### Step 3: Manual Labeling (Experiment 3)

1. Edit `data/judge_results/manual_labels.json`
2. Fill in `consistency_score` (0-100) and `category` ("Consistent" or "Contradictory") for each pair
3. Re-run validation:
```bash
python -m src.llm_judge.run_validation --skip-experiments
```

#### Step 4: Generate Report

The report is automatically generated after validation. To regenerate:

```bash
python src/llm_judge/generate_report.py
```

**Output**: 
- `reports/FINAL_REPORT.md` - Comprehensive report with analysis, charts, and findings
- `reports/charts/` - Visualization charts

## Key Features

### Data Acquisition
- **Project Gutenberg**: Automated scraping of 5 historical books
- **Library of Congress**: API-based scraping with rate limiting
- **Normalization**: Consistent JSON schema across all sources

### Event Extraction
- **Context Window Handling**: Chunking + keyword filtering for long documents
- **Structured Outputs**: Uses `instructor` library with Pydantic models
- **Parallel Processing**: 3 concurrent workers for efficiency
- **Resume Capability**: Incremental saving prevents data loss

### LLM Judge
- **Consistency Scoring**: 0-100 scale for account comparison
- **Contradiction Classification**: Factual, Interpretive, Omission, or None
- **Structured Reasoning**: Detailed explanations for each judgment

### Statistical Validation
- **Prompt Robustness**: Ablation study comparing prompt strategies
- **Self-Consistency**: Reliability testing across multiple runs
- **Inter-Rater Agreement**: Cohen's Kappa for human alignment

## Results Summary

- **Total Comparisons**: 363 pairs analyzed
- **Average Consistency**: 47.71/100
- **Contradiction Types**: 
  - Factual: 142 (39.1%)
  - Omission: 122 (33.6%)
  - Interpretive: 85 (23.4%)
  - None: 14 (3.9%)
- **Human Alignment**: 
  - Cohen's Kappa: -0.250 (poor categorical agreement due to binning effects)
  - Mean Absolute Difference: ~11.5 points (good numeric agreement)
  - Correlation: -0.112 (slight negative correlation)

See `reports/FINAL_REPORT.md` for detailed analysis.

## Technical Details

### LLM Models
- **Model**: GPT-4o-mini
- **Temperature**: 0.3 (for consistency)
- **Structured Outputs**: `instructor` library with Pydantic

### Prompt Engineering
- **Event Extraction**: Zero-shot with detailed instructions and examples
- **LLM Judge**: Zero-shot with comprehensive rubric and examples
- **Validation**: Tested Zero-Shot, Chain-of-Thought, and Few-Shot strategies

### Performance Optimizations
- Parallel processing with ThreadPoolExecutor
- Rate limiting with exponential backoff
- Incremental saving for long-running processes
- Keyword filtering to reduce unnecessary LLM calls

## Troubleshooting

### Rate Limit Errors
- The scripts include automatic retry logic with exponential backoff
- Reduce `max_workers` in parallel processing if needed
- Add delays between batches if rate limits persist

### Missing Data
- Check that Part 1 completed successfully
- Verify API keys are set correctly
- Check network connectivity for web scraping

### Import Errors
- Ensure virtual environment is activated
- Run `pip install -r requirements.txt` again
- Check Python version (3.10+ required)

## File Descriptions

### Data Files
- `gutenberg_dataset.json`: Normalized Project Gutenberg books
- `loc_dataset.json`: Normalized Library of Congress documents
- `event_extractions.json`: Structured event information extracted from all documents
- `judge_comparisons.json`: LLM Judge comparison results
- `statistical_validation.json`: Statistical summary metrics
- `manual_labels.json`: Human labels for validation (fill this in for Experiment 3)

### Code Files
- `src/data_acquisition/`: Scraping and normalization scripts
- `src/event_extraction/`: Event extraction pipeline
- `src/llm_judge/`: LLM Judge and validation experiments

### Report Files
- `reports/FINAL_REPORT.md`: Comprehensive analysis report
- `reports/charts/`: Visualization charts (PNG images)

## Citation

This project was developed as a technical assessment for an ML Evaluation Engineer position, demonstrating:
- Engineering grit (scraping difficult sources)
- Evaluation design (LLM-based extraction and judgment)
- Statistical rigor (validation experiments and metrics)

## License

This project is for assessment purposes only.

