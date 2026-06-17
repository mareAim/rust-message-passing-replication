#!/usr/bin/env python3
"""Rank repositories per message-passing category by usage, then stars."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_INPUT = "all-repos.json"
DEFAULT_STARS = "lookup_stars.json"
CATEGORIES = (
    "mpsc",
    "mpmc_pub_sub",
    "mpmc_competing_consumers",
    "oneshot",
)
USAGE_PRIORITY = {
    "UNUSED": 0,
    "USED_SPARINGLY": 1,
    "INSTRUMENTAL_TO_ARCHITECTURE": 2,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Rank the top repositories for each message-passing category using "
            "usage priority first and GitHub stars second."
        )
    )
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT,
        help=f"Path to the review data JSON array (default: {DEFAULT_INPUT}).",
    )
    parser.add_argument(
        "--stars",
        default=DEFAULT_STARS,
        help=f"Path to the repo->stars JSON object (default: {DEFAULT_STARS}).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional number of repos to emit per category. Emits all repos when omitted.",
    )
    parser.add_argument(
        "--output",
        help="Optional path for the ranked JSON output. Prints to stdout when omitted.",
    )
    parser.add_argument(
        "--unique-repos",
        action="store_true",
        help=(
            "When used with --limit, assign each repository to at most one category "
            "within the emitted window by globally maximizing usage quality, then "
            "per-category ranking quality."
        ),
    )
    return parser.parse_args()


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_reviews(path: str) -> list[dict[str, Any]]:
    data = load_json(path)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array.")

    reviews: list[dict[str, Any]] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"{path}[{index}] must be an object.")

        repository_name = item.get("repository_name")
        if not isinstance(repository_name, str) or not repository_name.strip():
            raise ValueError(f"{path}[{index}].repository_name must be a non-empty string.")

        for category in CATEGORIES:
            usage = item.get(category)
            if usage not in USAGE_PRIORITY:
                raise ValueError(
                    f"{path}[{index}].{category} must be one of "
                    f"{', '.join(USAGE_PRIORITY)}; got {usage!r}."
                )

        reviews.append(item)

    return reviews


def load_stars(path: str) -> dict[str, int]:
    data = load_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")

    stars_by_repo: dict[str, int] = {}
    for repo, stars in data.items():
        if not isinstance(repo, str) or not repo.strip():
            raise ValueError(f"{path} contains an invalid repository key: {repo!r}.")
        if not isinstance(stars, int):
            raise ValueError(f"{path}[{repo!r}] must be an integer star count.")
        stars_by_repo[repo] = stars

    return stars_by_repo


def build_rankings(
    reviews: list[dict[str, Any]],
    stars_by_repo: dict[str, int],
    limit: int | None,
    unique_repos: bool = False,
) -> dict[str, dict[str, dict[str, Any]]]:
    if unique_repos:
        if limit is None:
            raise ValueError("--unique-repos requires --limit.")
        return build_unique_rankings(reviews, stars_by_repo, limit)

    rankings: dict[str, dict[str, dict[str, Any]]] = {}

    for category in CATEGORIES:
        ranked_reviews = sorted(
            reviews,
            key=lambda review: ranking_sort_key(review, category, stars_by_repo),
        )

        category_output: dict[str, dict[str, Any]] = {}
        selected_reviews = ranked_reviews if limit is None else ranked_reviews[:limit]
        for review in selected_reviews:
            repo = review["repository_name"]
            category_output[repo] = {
                "stars": stars_by_repo[repo],
                "usage": review[category],
            }

        rankings[category] = category_output

    return rankings


def ranking_sort_key(
    review: dict[str, Any],
    category: str,
    stars_by_repo: dict[str, int],
) -> tuple[int, int, str]:
    repo = review["repository_name"]
    return (
        -USAGE_PRIORITY[review[category]],
        -stars_by_repo[repo],
        repo.lower(),
    )


def build_unique_rankings(
    reviews: list[dict[str, Any]],
    stars_by_repo: dict[str, int],
    limit: int,
) -> dict[str, dict[str, dict[str, Any]]]:
    total_slots = len(CATEGORIES) * limit
    ranking_positions = build_ranking_positions(reviews, stars_by_repo)
    max_rank_score = len(reviews)
    max_total_rank_score = total_slots * max_rank_score

    # The optimizer treats quality as a lexicographic objective:
    # 1. maximize INSTRUMENTAL selections
    # 2. then maximize USED_SPARINGLY selections
    # 3. then maximize category-specific ranking quality
    # Large mixed-radix bonuses let us preserve that ordering with integer scores.
    used_bonus = max_total_rank_score + 1
    instrumental_bonus = (total_slots + 1) * used_bonus

    ordered_reviews = sorted(reviews, key=lambda review: review["repository_name"].lower())
    zero_state = (0,) * len(CATEGORIES)
    target_state = (limit,) * len(CATEGORIES)

    best_scores: dict[tuple[int, ...], int] = {zero_state: 0}
    backtrack: list[dict[tuple[int, ...], tuple[tuple[int, ...], int | None]]] = []

    for review in ordered_reviews:
        next_scores = dict(best_scores)
        step_backtrack = {
            state: (state, None)
            for state in best_scores
        }

        for state, score in best_scores.items():
            for category_index, category in enumerate(CATEGORIES):
                if state[category_index] >= limit:
                    continue

                next_state = (
                    state[:category_index]
                    + (state[category_index] + 1,)
                    + state[category_index + 1 :]
                )
                candidate_score = score + unique_assignment_score(
                    review,
                    category,
                    ranking_positions,
                    max_rank_score,
                    used_bonus,
                    instrumental_bonus,
                )
                current_best = next_scores.get(next_state)
                if current_best is None or candidate_score > current_best:
                    next_scores[next_state] = candidate_score
                    step_backtrack[next_state] = (state, category_index)

        backtrack.append(step_backtrack)
        best_scores = next_scores

    final_state = target_state if target_state in best_scores else max(best_scores, key=best_scores.get)
    selected_reviews: dict[str, list[dict[str, Any]]] = {category: [] for category in CATEGORIES}

    state = final_state
    for review, step_backtrack in zip(reversed(ordered_reviews), reversed(backtrack)):
        previous_state, category_index = step_backtrack[state]
        if category_index is not None:
            selected_reviews[CATEGORIES[category_index]].append(review)
        state = previous_state

    rankings: dict[str, dict[str, dict[str, Any]]] = {}
    for category in CATEGORIES:
        category_output: dict[str, dict[str, Any]] = {}
        for review in sorted(
            selected_reviews[category],
            key=lambda current_review: ranking_sort_key(current_review, category, stars_by_repo),
        ):
            repo = review["repository_name"]
            category_output[repo] = {
                "stars": stars_by_repo[repo],
                "usage": review[category],
            }

        rankings[category] = category_output

    return rankings


def build_ranking_positions(
    reviews: list[dict[str, Any]],
    stars_by_repo: dict[str, int],
) -> dict[str, dict[str, int]]:
    positions: dict[str, dict[str, int]] = {}
    for category in CATEGORIES:
        ranked_reviews = sorted(
            reviews,
            key=lambda review: ranking_sort_key(review, category, stars_by_repo),
        )
        positions[category] = {
            review["repository_name"]: index
            for index, review in enumerate(ranked_reviews, start=1)
        }

    return positions


def unique_assignment_score(
    review: dict[str, Any],
    category: str,
    ranking_positions: dict[str, dict[str, int]],
    max_rank_score: int,
    used_bonus: int,
    instrumental_bonus: int,
) -> int:
    usage = review[category]
    rank_score = max_rank_score - ranking_positions[category][review["repository_name"]] + 1
    if usage == "INSTRUMENTAL_TO_ARCHITECTURE":
        return instrumental_bonus + rank_score
    if usage == "USED_SPARINGLY":
        return used_bonus + rank_score
    return rank_score


def validate_star_coverage(reviews: list[dict[str, Any]], stars_by_repo: dict[str, int]) -> None:
    missing = sorted(
        review["repository_name"]
        for review in reviews
        if review["repository_name"] not in stars_by_repo
    )
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Missing star counts for repositories: {joined}")


def main() -> int:
    args = parse_args()
    if args.limit is not None and args.limit <= 0:
        raise ValueError("--limit must be a positive integer.")

    reviews = load_reviews(args.input)
    stars_by_repo = load_stars(args.stars)
    validate_star_coverage(reviews, stars_by_repo)
    rankings = build_rankings(reviews, stars_by_repo, args.limit, unique_repos=args.unique_repos)

    payload = json.dumps(rankings, indent=2)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI error path
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
