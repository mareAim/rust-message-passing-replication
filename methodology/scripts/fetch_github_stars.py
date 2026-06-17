#!/usr/bin/env python3
"""Fetch GitHub star counts for repos grouped by category."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any
from urllib import error, parse, request


DEFAULT_INPUT = "filtered-awesome-rust.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read a JSON object mapping category names to GitHub repos and print "
            "a JSON object mapping each category to repos with star counts, sorted "
            "by stars descending within each category."
        )
    )
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    parser.add_argument("--timeout", type=float, default=20.0)
    return parser.parse_args()


def load_repo_categories(path: str) -> dict[str, list[Any]]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object mapping categories to arrays.")

    for category, items in data.items():
        if not isinstance(category, str):
            raise ValueError(f"Category names must be strings: {category!r}")
        if not isinstance(items, list):
            raise ValueError(f"Category {category!r} must contain a JSON array.")

    return data


def normalize_repo(item: Any) -> str:
    if isinstance(item, dict):
        for key in ("repo", "full_name", "url", "github_url"):
            value = item.get(key)
            if value:
                item = value
                break
        else:
            raise ValueError(f"Unsupported repo object: {item!r}")

    if not isinstance(item, str):
        raise ValueError(f"Unsupported repo entry: {item!r}")

    value = item.strip()
    if not value:
        raise ValueError("Repo entry cannot be empty.")

    if value.startswith(("http://", "https://")):
        parsed = parse.urlparse(value)
        if parsed.netloc not in {"github.com", "www.github.com"}:
            raise ValueError(f"Unsupported GitHub URL: {value}")
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2:
            raise ValueError(f"Invalid GitHub repo URL: {value}")
        owner, repo = parts[0], parts[1]
    else:
        parts = [part for part in value.split("/") if part]
        if len(parts) != 2:
            raise ValueError(f"Repo must look like owner/repo: {value}")
        owner, repo = parts

    repo = repo.removesuffix(".git")
    return f"{owner}/{repo}"


def build_request(owner_repo: str, token: str | None) -> request.Request:
    owner, repo = owner_repo.split("/", 1)
    api_url = (
        "https://api.github.com/repos/"
        f"{parse.quote(owner, safe='')}/{parse.quote(repo, safe='')}"
    )
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "rust-crate-fetcher/star-gathering-script",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return request.Request(api_url, headers=headers)


def fetch_repo(owner_repo: str, token: str | None, timeout: float) -> tuple[str, int] | None:
    req = build_request(owner_repo, token)

    try:
        with request.urlopen(req, timeout=timeout) as response:
            payload = json.load(response)
    except error.HTTPError as exc:
        if exc.code == 404:
            print(f"warning: skipping missing repo {owner_repo}", file=sys.stderr)
            return None

        body = exc.read().decode("utf-8", errors="replace").strip()
        message = f"GitHub API request failed for {owner_repo}: HTTP {exc.code}"
        if body:
            message = f"{message} - {body}"
        raise RuntimeError(message) from exc
    except error.URLError as exc:
        raise RuntimeError(f"Network error while fetching {owner_repo}: {exc.reason}") from exc

    full_name = payload.get("full_name")
    stars = payload.get("stargazers_count")

    if not isinstance(full_name, str) or not isinstance(stars, int):
        raise RuntimeError(f"Unexpected GitHub API response for {owner_repo}: {payload!r}")

    return full_name, stars


def main() -> int:
    args = parse_args()
    categories = load_repo_categories(args.input)
    token = os.environ.get(args.token_env)

    repo_cache: dict[str, tuple[str, int] | None] = {}
    output: dict[str, dict[str, int]] = {}

    for category, raw_items in categories.items():
        stars_by_repo: dict[str, int] = {}
        seen_in_category: set[str] = set()

        for item in raw_items:
            try:
                owner_repo = normalize_repo(item)
            except ValueError as exc:
                print(f"warning: skipping invalid repo entry {item!r}: {exc}", file=sys.stderr)
                continue

            if owner_repo in seen_in_category:
                continue
            seen_in_category.add(owner_repo)

            if owner_repo not in repo_cache:
                repo_cache[owner_repo] = fetch_repo(owner_repo, token, args.timeout)

            repo_result = repo_cache[owner_repo]
            if repo_result is None:
                continue

            full_name, stars = repo_result
            stars_by_repo[full_name] = stars

        sorted_items = sorted(
            stars_by_repo.items(),
            key=lambda entry: (-entry[1], entry[0].lower()),
        )

        output[category] = dict(sorted_items)

    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
