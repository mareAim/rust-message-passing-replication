# Rust Message Passing Replication Package

This repository contains the replication package for the empirical analysis of message passing in Rust applications.

## Contents

- `manual-analysis-templates/batches.json`: selected repository batches and category metadata.
- `manual-analysis-templates/`: manual-analysis files with true/false answers and line references.
- `scripts/compute_manual_analysis_results.py`: regenerates manual-analysis counts and
  Pearson/phi correlation matrices.
- `scripts/count_channel_primitives_in_samples.py`: counts channel creation sites in sampled
  files.
- `analysis-results/manual-analysis/`: generated CSV files used for the reported results.
- `methodology/scripts/`: scripts used during dataset construction, sampling, classification, and ranking.
- `methodology/intermediate-json/`: intermediate JSON files from repository selection, star lookup, filtering, and category ranking.

## Reproducing Manual-Analysis Results

Run:

```bash
python3 scripts/compute_manual_analysis_results.py --root .
```

This regenerates:

- `file_rows.csv`
- `question_counts_by_batch.csv`
- `question_pearson_matrix.csv`
- `question_vs_category_pearson_matrix.csv`
- `run_summary.csv`

## Reproducing Primitive Counts

The generated primitive-count CSVs are included. To rerun primitive counting from source,
  clone the analysed repositories under:

```text
repos/<owner>/<repo>/
```

The script uses the pinned commit hashes recorded in the manual-analysis templates.

Then run:

```bash
python3 scripts/count_channel_primitives_in_samples.py --root .
```

## Notes

The analysis is based on 20 repositories across five batches. The final analysis uses 76
  analyzable sampled files; 11 sampled files were marked as not relevant.

## Methodology Files

The `methodology/` directory documents the dataset-construction pipeline used before manual analysis. It includes scripts for filtering Awesome Rust repositories, fetching GitHub stars, running the LLM-assisted message-passing review, ranking repositories by category, and selecting sampled files.

The intermediate JSON files are included to show how the selected batches relate to the larger candidate set. The final reported results can be reproduced from `manual-analysis-templates/batches.json`, `manual-analysis-templates/`, and the scripts in `scripts/`.
