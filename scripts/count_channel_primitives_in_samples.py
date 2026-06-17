#!/usr/bin/env python3
"""Count channel primitive creation sites in sampled manual-analysis files.

Run from anywhere:

    python3 scripts/count_channel_primitives_in_samples.py --root "/Users/mare/Downloads/awesome-rust 2"

Outputs:
    analysis-results/manual-analysis/channel_primitive_counts_in_sampled_files.csv
    analysis-results/manual-analysis/channel_primitive_summary.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


PRIMITIVE_PATTERNS = {
    "std_mpsc": [
        r"\bstd::sync::mpsc::channel\s*\(",
        r"\bstd::sync::mpsc::sync_channel\s*\(",
        r"\bstd_mpsc::channel\s*\(",
        r"\bstd_mpsc::sync_channel\s*\(",
    ],
    "tokio_mpsc": [
        r"\btokio::sync::mpsc::channel\s*\(",
        r"\btokio::sync::mpsc::unbounded_channel\s*\(",
        r"(?<!::)\bmpsc::channel\s*\(",
        r"(?<!::)\bmpsc::unbounded_channel\s*\(",
    ],
    "tokio_broadcast": [
        r"\btokio::sync::broadcast::channel\s*\(",
        r"(?<!::)\bbroadcast::channel\s*\(",
    ],
    "tokio_watch": [
        r"\btokio::sync::watch::channel\s*\(",
        r"(?<!::)\bwatch::channel\s*\(",
    ],
    "tokio_oneshot": [
        r"\btokio::sync::oneshot::channel\s*\(",
        r"(?<!::)\boneshot::channel\s*\(",
    ],
    "futures_mpsc": [
        r"\bfutures::channel::mpsc::channel\s*\(",
        r"\bfutures::channel::mpsc::unbounded\s*\(",
    ],
    "futures_oneshot": [
        r"\bfutures::channel::oneshot::channel\s*\(",
    ],
    "crossbeam_channel": [
        r"\bcrossbeam_channel::bounded\s*\(",
        r"\bcrossbeam_channel::unbounded\s*\(",
    ],
    "async_channel": [
        r"\basync_channel::bounded\s*\(",
        r"\basync_channel::unbounded\s*\(",
    ],
    "flume": [
        r"\bflume::bounded\s*\(",
        r"\bflume::unbounded\s*\(",
    ],
    "async_priority_channel": [
        r"\basync_priority_channel::bounded\s*\(",
        r"\basync_priority_channel::unbounded\s*\(",
    ],
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def batches_path(root: Path) -> Path:
    nested = root / "manual-analysis-templates" / "batches.json"
    if nested.exists():
        return nested
    return root / "batches.json"


def manual_template_path(root: Path, batch_no: int, repo: str, manual_file: str | None) -> Path:
    copied = root / "manual-analysis-templates" / f"batch{batch_no}__{repo.replace('/', '__')}__manual-analysis-template.json"
    if copied.exists():
        return copied

    if manual_file:
        return root / "repos" / repo / manual_file
    return root / "repos" / repo / "manual-analysis-template.json"


def git_show(repo_dir: Path, commit: str, file_path: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_dir), "show", f"{commit}:{file_path}"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def count_patterns(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for primitive, patterns in PRIMITIVE_PATTERNS.items():
        counts[primitive] = sum(len(re.findall(pattern, text)) for pattern in patterns)
    return counts


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, default=Path("analysis-results/manual-analysis"))
    parser.add_argument("--include-not-relevant", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    out_dir = args.out if args.out.is_absolute() else root / args.out
    batches = read_json(batches_path(root))

    file_rows: list[dict[str, Any]] = []
    summary = Counter()

    for batch in batches["batches"]:
        for repo_entry in batch["repositories"]:
            if repo_entry.get("analysis_status") != "finished":
                continue

            repo = repo_entry["repo"]
            repo_dir = root / "repos" / repo
            manual_file = repo_entry.get("manual_analysis_file") or "manual-analysis-template.json"
            template_path = manual_template_path(root, batch["batch"], repo, manual_file)
            if not template_path.exists():
                continue

            template = read_json(template_path)
            analysis = template["repo_analysis"]
            commit = analysis["github_commit"]

            for index, sampled in enumerate(analysis.get("sampled_files", []), start=1):
                sample_status = sampled.get("sample_status", "")
                try:
                    text = git_show(repo_dir, commit, sampled["file"])
                    counts = count_patterns(text)
                    error = ""
                except subprocess.CalledProcessError as exc:
                    counts = {primitive: 0 for primitive in PRIMITIVE_PATTERNS}
                    error = exc.stderr.strip()

                row = {
                    "batch": batch["batch"],
                    "repo": repo,
                    "category": repo_entry["category"],
                    "sample_index": index,
                    "file": sampled.get("file", ""),
                    "sample_status": sample_status,
                    "error": error,
                }
                row.update(counts)
                row["total_channel_creation_sites"] = sum(counts.values())
                file_rows.append(row)

                if args.include_not_relevant or sample_status == "analyzable":
                    summary.update(counts)

    summary_rows = [
        {"primitive": primitive, "count": summary[primitive]}
        for primitive in PRIMITIVE_PATTERNS
    ]
    summary_rows.append({"primitive": "total_channel_creation_sites", "count": sum(summary.values())})

    write_csv(out_dir / "channel_primitive_counts_in_sampled_files.csv", file_rows)
    write_csv(out_dir / "channel_primitive_summary.csv", summary_rows)

    print(f"Wrote primitive counts to {out_dir}")
    print(f"sampled_files_loaded: {len(file_rows)}")
    print(f"include_not_relevant: {str(args.include_not_relevant).lower()}")
    for row in summary_rows:
        print(f"{row['primitive']}: {row['count']}")


if __name__ == "__main__":
    main()
