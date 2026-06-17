# Manual Analysis Results

Generated with:

```sh
python3 scripts/compute_manual_analysis_results.py --root .
```

Current run after batch 5:

- Finished repositories loaded: 20
- Sampled files loaded: 87
- Analyzable files loaded: 76
- Not-relevant files loaded: 11
- Files used for correlations: 76
- Not-relevant files are kept in `file_rows.csv`, but excluded from counts and correlations by default.

## Main Files

- `file_rows.csv`: one row per sampled file, including batch, repository, primitive category, sample status, and all 14 question answers.
- `question_counts_by_batch.csv`: true/false counts per question, per batch and overall. Counts are based on analyzable files.
- `run_summary.csv`: summary of the current run.

## Pearson / Phi Outputs

For binary variables, Pearson correlation is equivalent to the phi coefficient. Values are computed on analyzable files by default. Blank values mean the coefficient could not be computed, usually because one variable was constant.

- `question_pearson_matrix.csv`: matrix form for correlations between the 14 question answers.
- `question_vs_category_pearson_matrix.csv`: matrix form for correlations between question answers and repository primitive category.

## Primitive Count Outputs

Generated with:

```sh
python3 scripts/count_channel_primitives_in_samples.py --root .
```

- `channel_primitive_counts_in_sampled_files.csv`: primitive counts per sampled file.
- `channel_primitive_summary.csv`: combined primitive counts across analyzable sampled files.

## Rerunning

To regenerate the manual-analysis results:

```sh
python3 scripts/compute_manual_analysis_results.py --root .
```

To include `not_relevant` files in the Pearson calculations too:

```sh
python3 scripts/compute_manual_analysis_results.py --root . --include-not-relevant
```

To rerun primitive counting from source, clone the analysed repositories under `repos/<owner>/<repo>/` first, then run:

```sh
python3 scripts/count_channel_primitives_in_samples.py --root .
```
