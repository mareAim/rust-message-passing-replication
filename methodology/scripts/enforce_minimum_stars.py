#!/usr/bin/env python3
import argparse
import json
import sys


def enforce_min_stars(
    data: dict,
    min_stars: int,
    exempt_categories: set[str],
    drop_empty: bool = False,
) -> dict:
    result = {}

    for category, repos in data.items():
        if category in exempt_categories:
            result[category] = repos
            continue

        filtered = {
            repo: stars
            for repo, stars in repos.items()
            if stars >= min_stars
        }

        if filtered or not drop_empty:
            result[category] = filtered

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Filter repos by minimum star count in a JSON file."
    )
    parser.add_argument("input", help="Input JSON file")
    parser.add_argument(
        "-o", "--output",
        help="Output JSON file (defaults to stdout)"
    )
    parser.add_argument(
        "-m", "--min-stars",
        type=int,
        required=True,
        help="Minimum star count threshold"
    )
    parser.add_argument(
        "-e", "--exempt",
        action="append",
        default=[],
        help="Category to exempt (can be used multiple times)"
    )
    parser.add_argument(
        "--drop-empty",
        action="store_true",
        help="Drop categories that end up empty after filtering"
    )

    args = parser.parse_args()

    if args.min_stars < 0:
        raise ValueError("--min-stars must be >= 0")

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    output = enforce_min_stars(
        data=data,
        min_stars=args.min_stars,
        exempt_categories=set(args.exempt),
        drop_empty=args.drop_empty,
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
            f.write("\n")
    else:
        json.dump(output, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
