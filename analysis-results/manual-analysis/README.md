# Manual Analysis Results

Generated with:

```sh
python3 scripts/compute_manual_analysis_results.py
```

Current run:

- Finished repositories loaded: 12
- Sampled files loaded: 56
- Files used for correlations: 49
- Not-relevant files are kept in `file_rows.csv`, but excluded from correlations by default.

## Main Files

- `file_rows.csv`: one row per sampled file, including batch, repository, primitive category, file labels, and all 14 question answers.
- `repo_rows.csv`: one row per finished repository, including repository-level labels.
- `question_counts_by_batch.csv`: true/false counts per question, per batch and overall.
- `label_counts_by_batch.csv`: counts for categories and file-level labels, per batch and overall.

## Pearson / Phi Outputs

For binary variables, Pearson correlation is equivalent to the phi coefficient. Values are computed on analyzable files by default. Blank `pearson_r` values mean the coefficient could not be computed, usually because one variable was constant.

- `question_pearson_matrix.csv`: matrix form for correlations between the 14 question answers.
- `question_pearson_long.csv`: long-form version of the same question-question correlations.
- `question_vs_category_pearson.csv`: question answers versus repository primitive category.
- `question_vs_file_structure_pearson.csv`: question answers versus file-level structure labels.
- `question_vs_file_role_pearson.csv`: question answers versus file-level role labels.
- `question_vs_file_importance_pearson.csv`: question answers versus file-level importance labels.
- `file_structure_vs_category_pearson.csv`: file-level structure labels versus repository primitive category.
- `file_role_vs_category_pearson.csv`: file-level role labels versus repository primitive category.
- `file_structure_vs_file_role_pearson.csv`: file-level structure labels versus file-level role labels.
- `repo_structure_vs_category_pearson.csv`: repository-level structure labels versus primitive category.
- `repo_role_vs_category_pearson.csv`: repository-level role labels versus primitive category.
- `repo_importance_vs_category_pearson.csv`: repository-level importance labels versus primitive category.

## Line-Reference Overlap

- `question_line_overlap.csv`: true question pairs that share at least one cited line reference in the same sampled file. This is useful for checking whether roles and structures are supported by the same code locations rather than only appearing in the same file.

## Rerun After Batch 5

After batch 5 is finished and `batches.json` plus the repo templates are updated, rerun:

```sh
python3 scripts/compute_manual_analysis_results.py
```

To include `not_relevant` files in the Pearson calculations too:

```sh
python3 scripts/compute_manual_analysis_results.py --include-not-relevant
```
