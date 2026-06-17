#!/usr/bin/env python3
"""Compute manual-analysis counts and Pearson/phi correlation outputs.

Run from the awesome-rust 2 directory:

    python3 scripts/compute_manual_analysis_results.py

By default this reads finished repositories from batches.json, loads each
repo-local manual-analysis-template.json, and writes CSV files to:

    analysis-results/manual-analysis/
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


QUESTION_NAMES = {
    "q01_clear_receiver_owner": "Receiver ownership",
    "q02_sender_cloning": "Sender sharing",
    "q03_receiver_loop": "Receiver loop",
    "q04_mailbox_pattern": "Mailbox",
    "q05_fan_in": "Fan-in",
    "q06_fan_out": "Fan-out",
    "q07_worker_queue": "Worker queue",
    "q08_shutdown_signal": "Shutdown/readiness/cancellation",
    "q09_data_transport": "Data transport",
    "q10_command_messages": "Command messages",
    "q11_notification_messages": "Notification/signals",
    "q12_background_dispatch": "Background dispatch",
    "q13_cross_thread_usage": "Cross-thread",
    "q14_cross_async_task_usage": "Cross-async-task",
}


def answer_to_number(value: Any) -> int | None:
    if value is True:
        return 1
    if value is False:
        return 0
    return None


def pearson(xs: list[int | float | None], ys: list[int | float | None]) -> tuple[int, float | None, str]:
    pairs = [(float(x), float(y)) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 2:
        return n, None, "too_few_rows"

    x_vals = [p[0] for p in pairs]
    y_vals = [p[1] for p in pairs]
    mean_x = sum(x_vals) / n
    mean_y = sum(y_vals) / n
    dx = [x - mean_x for x in x_vals]
    dy = [y - mean_y for y in y_vals]
    denom_x = math.sqrt(sum(x * x for x in dx))
    denom_y = math.sqrt(sum(y * y for y in dy))
    if denom_x == 0 or denom_y == 0:
        return n, None, "constant_variable"
    return n, sum(x * y for x, y in zip(dx, dy)) / (denom_x * denom_y), ""


def format_pearson(value: float | None) -> str:
    return "" if value is None else f"{value:.2f}"


def repo_path(root: Path, repo: str, manual_file: str | None) -> Path:
    if manual_file:
        candidate = root / "repos" / repo / manual_file
    else:
        candidate = root / "repos" / repo / "manual-analysis-template.json"
    return candidate


def load_rows(root: Path, include_pending: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    batches = json.loads((root / "batches.json").read_text())
    file_rows: list[dict[str, Any]] = []
    repo_rows: list[dict[str, Any]] = []

    for batch in batches["batches"]:
        batch_no = batch["batch"]
        for repo_entry in batch["repositories"]:
            if not include_pending and repo_entry.get("analysis_status") != "finished":
                continue

            manual_path = repo_path(root, repo_entry["repo"], repo_entry.get("manual_analysis_file"))
            if not manual_path.exists():
                continue

            template = json.loads(manual_path.read_text())
            analysis = template["repo_analysis"]
            summary = analysis.get("repo_summary", {})

            repo_row = {
                "batch": batch_no,
                "repo": repo_entry["repo"],
                "category": repo_entry["category"],
                "rank_in_category": repo_entry.get("rank_in_category", ""),
                "usage": repo_entry.get("usage", ""),
                "manual_analysis_file": str(manual_path.relative_to(root)),
            }
            repo_rows.append(repo_row)

            for index, sampled in enumerate(analysis.get("sampled_files", []), start=1):
                answers = {a["id"]: answer_to_number(a.get("answer")) for a in sampled.get("answers", [])}
                answer_text = {
                    a["id"]: "true" if a.get("answer") is True else "false" if a.get("answer") is False else "missing"
                    for a in sampled.get("answers", [])
                }
                row = {
                    **repo_row,
                    "sample_index": index,
                    "file": sampled.get("file", ""),
                    "line_count": sampled.get("line_count", ""),
                    "sample_status": sampled.get("sample_status", ""),
                }
                for qid in QUESTION_NAMES:
                    row[qid] = answers.get(qid)
                    row[f"{qid}_answer"] = answer_text.get(qid, "missing")
                file_rows.append(row)

    return file_rows, repo_rows


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        seen = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    seen.add(key)
                    keys.append(key)
        fieldnames = keys
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def one_hot_values(rows: list[dict[str, Any]], column: str, prefix: str) -> dict[str, list[int]]:
    values = sorted({str(row.get(column, "")) for row in rows if row.get(column, "") != ""})
    return {
        f"{prefix}:{value}": [1 if row.get(column) == value else 0 for row in rows]
        for value in values
    }


def question_vectors(rows: list[dict[str, Any]]) -> dict[str, list[int | None]]:
    return {qid: [row.get(qid) for row in rows] for qid in QUESTION_NAMES}


def long_correlations(left: dict[str, list[Any]], right: dict[str, list[Any]], same_side: bool = False) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    left_items = list(left.items())
    right_items = list(right.items())
    for i, (left_name, xs) in enumerate(left_items):
        for j, (right_name, ys) in enumerate(right_items):
            if same_side and j <= i:
                continue
            n, r, note = pearson(xs, ys)
            out.append(
                {
                    "left": left_name,
                    "right": right_name,
                    "n": n,
                    "pearson_r": format_pearson(r),
                    "note": note,
                }
            )
    return out


def matrix(rows: list[dict[str, Any]], row_key: str = "left", col_key: str = "right", value_key: str = "pearson_r") -> list[dict[str, Any]]:
    row_names = sorted({row[row_key] for row in rows})
    col_names = sorted({row[col_key] for row in rows})
    values = {(row[row_key], row[col_key]): row[value_key] for row in rows}
    out = []
    for row_name in row_names:
        row = {"": row_name}
        for col_name in col_names:
            row[col_name] = values.get((row_name, col_name), "")
        out.append(row)
    return out


def symmetric_question_matrix(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    names = list(QUESTION_NAMES)
    values: dict[tuple[str, str], str] = {}
    for row in rows:
        left = row["left"]
        right = row["right"]
        value = row["pearson_r"]
        values[(left, right)] = value
        values[(right, left)] = value

    out = []
    for left in names:
        row = {"": left}
        for right in names:
            row[right] = "" if left == right else values.get((left, right), "")
        out.append(row)
    return out


def question_counts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counters: dict[tuple[Any, str], Counter[str]] = defaultdict(Counter)
    for row in rows:
        batch = row["batch"]
        for qid in QUESTION_NAMES:
            value = row.get(f"{qid}_answer", "missing")
            counters[(batch, qid)][value] += 1
            counters[("all", qid)][value] += 1

    out = []
    for (batch, qid), counter in sorted(counters.items(), key=lambda item: (str(item[0][0]), item[0][1])):
        out.append(
            {
                "batch": batch,
                "question_id": qid,
                "question_name": QUESTION_NAMES[qid],
                "true": counter["true"],
                "false": counter["false"],
                "missing": counter["missing"],
                "total": sum(counter.values()),
            }
        )
    return out


def label_counts(rows: list[dict[str, Any]], columns: list[str]) -> list[dict[str, Any]]:
    out = []
    for column in columns:
        counters: dict[Any, Counter[str]] = defaultdict(Counter)
        for row in rows:
            value = str(row.get(column, ""))
            counters[row["batch"]][value] += 1
            counters["all"][value] += 1
        for batch, counter in sorted(counters.items(), key=lambda item: str(item[0])):
            for value, count in sorted(counter.items()):
                out.append({"batch": batch, "label_column": column, "label_value": value, "count": count})
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, default=Path("analysis-results/manual-analysis"))
    parser.add_argument("--include-pending", action="store_true")
    parser.add_argument("--include-not-relevant", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    out_dir = args.out if args.out.is_absolute() else root / args.out
    file_rows_all, repo_rows = load_rows(root, include_pending=args.include_pending)
    file_rows_for_corr = (
        file_rows_all
        if args.include_not_relevant
        else [row for row in file_rows_all if row.get("sample_status") == "analyzable"]
    )

    base_fields = [
        "batch",
        "repo",
        "category",
        "rank_in_category",
        "usage",
        "sample_index",
        "file",
        "line_count",
        "sample_status",
    ]
    question_fields = [field for qid in QUESTION_NAMES for field in (qid, f"{qid}_answer")]
    write_csv(out_dir / "file_rows.csv", file_rows_all, base_fields + question_fields)
    write_csv(out_dir / "question_counts_by_batch.csv", question_counts(file_rows_for_corr))

    q_vectors = question_vectors(file_rows_for_corr)
    q_long = long_correlations(q_vectors, q_vectors, same_side=True)
    write_csv(out_dir / "question_pearson_matrix.csv", symmetric_question_matrix(q_long))

    category_vectors = one_hot_values(file_rows_for_corr, "category", "category")
    question_category = long_correlations(q_vectors, category_vectors)
    question_category_matrix = matrix(question_category)
    write_csv(out_dir / "question_vs_category_pearson_matrix.csv", question_category_matrix)

    summary = [
        {"metric": "finished_repositories_loaded", "value": len(repo_rows)},
        {"metric": "sampled_files_loaded", "value": len(file_rows_all)},
        {"metric": "analyzable_files_loaded", "value": len(file_rows_for_corr)},
        {
            "metric": "not_relevant_files_loaded",
            "value": sum(1 for row in file_rows_all if row.get("sample_status") != "analyzable"),
        },
        {"metric": "files_used_for_correlations", "value": len(file_rows_for_corr)},
        {"metric": "include_not_relevant_for_correlations", "value": str(args.include_not_relevant).lower()},
        {"metric": "output_directory", "value": str(out_dir)},
    ]
    write_csv(out_dir / "run_summary.csv", summary, ["metric", "value"])
    print(f"Wrote manual-analysis outputs to {out_dir}")
    for row in summary:
        print(f"{row['metric']}: {row['value']}")


if __name__ == "__main__":
    main()
