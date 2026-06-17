#!/usr/bin/env python3
import argparse
import json
import sys


def enforce_max_repos(data: dict, max_per_category: int, exempt_categories: set[str]) -> dict:
    result = {}

    for category, repos in data.items():
        if category in exempt_categories:
            result[category] = repos
            continue

        limited_items = list(repos.items())[:max_per_category]
        result[category] = dict(limited_items)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Limit the number of repos per category in a JSON file."
    )
    parser.add_argument("input", help="Input JSON file")
    parser.add_argument(
        "-o", "--output",
        help="Output JSON file. Defaults to stdout."
    )
    parser.add_argument(
        "-m", "--max-repos",
        type=int,
        required=True,
        help="Maximum repos per category"
    )
    parser.add_argument(
        "-e", "--exempt",
        action="append",
        default=[],
        help="Category to exempt. Can be passed multiple times."
    )

    args = parser.parse_args()

    if args.max_repos < 0:
        raise ValueError("--max-repos must be >= 0")

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    output = enforce_max_repos(
        data=data,
        max_per_category=args.max_repos,
        exempt_categories=set(args.exempt),
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
