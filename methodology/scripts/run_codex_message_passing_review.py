#!/usr/bin/env python3
"""Clone a GitHub repo and run a short Codex message-passing review."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


PROMPT_TEMPLATE = """Investigate the use of message passing patterns in this repository. This will be a cursory glance, not a full investigation.
I only require that you fill out the following form:

{{
    "repository_name": "{repository_name}",
    # Possible categories: "UNUSED", "USED_SPARINGLY", "INSTRUMENTAL_TO_ARCHITECTURE"
    "mpsc": "UNUSED",
    "mpmc_pub_sub": "UNUSED",
    "mpmc_competing_consumers": "UNUSED",
    "oneshot": "UNUSED",
    "other": "Specify here",
    "decision_notes": "Briefly explain the evidence behind your classifications."
}}

Here marking a message passing pattern as UNUSED, represents that the repository did not use the pattern outside of tests or benchmarks.
Marking a pattern as "USED_SPARINGLY", signifies that the pattern was used in some parts of the codebase, but not extensively. use this to indicate for example that  a channel was only used to communicate with a library
INSTRUMENTAL_TO_ARCHITECTURE should be marked when the application uses a message passing pattern as one of it's core patterns. for example to communicate with a database thread, or to distribute work over worker threads. but also to broadcast events for logging and notifications.
if the crate uses a pattern not specified in the template, add it to the other section. only do this when unsure what to do. this is an escape hatch.

Please ensure your investigation concludes swiftly, and does not take up too many tokens.
Write the completed JSON object to a file named `message_passing_review.json` in the repository root.
Your final response should be brief and mention that file was written.

Some keywords to search for;

std::sync::mpsc
tokio::sync::mpsc
tokio::sync::broadcast
tokio::sync::oneshot
tokio::sync::watch
crossbeam_channel
async_channel
futures::channel::mpsc
futures::channel::oneshot
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clone a GitHub repository and run a short Codex message-passing review."
    )
    parser.add_argument(
        "repository",
        help="GitHub repository in owner/repo form or as a GitHub URL.",
    )
    parser.add_argument(
        "--clone-root",
        default="repos",
        help="Directory where repositories will be cloned (default: repos).",
    )
    parser.add_argument(
        "--output",
        help="Optional file to store Codex's final message.",
    )
    parser.add_argument(
        "--model",
        help="Optional Codex model override.",
    )
    parser.add_argument(
        "--codex-bin",
        default="codex",
        help="Codex executable to invoke (default: codex).",
    )
    parser.add_argument(
        "--git-bin",
        default="git",
        help="Git executable to invoke (default: git).",
    )
    parser.add_argument(
        "--reclone",
        action="store_true",
        help="Delete any existing clone before cloning again.",
    )
    return parser.parse_args()


def normalize_repository(value: str) -> str:
    repo = value.strip()
    if not repo:
        raise ValueError("Repository cannot be empty.")

    if repo.startswith(("http://", "https://", "git@github.com:")):
        if repo.startswith("git@github.com:"):
            path = repo.split(":", 1)[1]
        else:
            parsed = urlparse(repo)
            if parsed.netloc not in {"github.com", "www.github.com"}:
                raise ValueError(f"Unsupported GitHub host: {parsed.netloc}")
            path = parsed.path
        parts = [part for part in path.split("/") if part]
        if len(parts) < 2:
            raise ValueError(f"Invalid GitHub repository: {value}")
        owner, name = parts[0], parts[1]
    else:
        parts = [part for part in repo.split("/") if part]
        if len(parts) != 2:
            raise ValueError(f"Repository must look like owner/repo: {value}")
        owner, name = parts

    name = name.removesuffix(".git")
    return f"{owner}/{name}"


def clone_url(owner_repo: str) -> str:
    return f"https://github.com/{owner_repo}.git"


def ensure_executable(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"Required executable not found on PATH: {name}")


def prepare_clone(owner_repo: str, clone_root: Path, git_bin: str, reclone: bool) -> Path:
    owner, repo = owner_repo.split("/", 1)
    destination = clone_root / owner / repo
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists():
        if reclone:
            shutil.rmtree(destination)
        elif (destination / ".git").is_dir():
            return destination
        else:
            raise RuntimeError(
                f"Destination exists and is not a git repository: {destination}"
            )

    cmd = [git_bin, "clone", "--depth", "1", clone_url(owner_repo), str(destination)]
    subprocess.run(cmd, check=True)
    return destination


def build_codex_command(args: argparse.Namespace, repo_dir: Path) -> list[str]:
    cmd = [
        args.codex_bin,
        "exec",
        "--cd",
        str(repo_dir),
        "--sandbox",
        "workspace-write",
        "--color",
        "never",
        "--ephemeral",
    ]
    if args.model:
        cmd.extend(["--model", args.model])
    if args.output:
        cmd.extend(["--output-last-message", args.output])
    cmd.append("-")
    return cmd


def main() -> int:
    args = parse_args()
    owner_repo = normalize_repository(args.repository)
    ensure_executable(args.git_bin)
    ensure_executable(args.codex_bin)

    clone_root = Path(args.clone_root).expanduser().resolve()
    repo_dir = prepare_clone(owner_repo, clone_root, args.git_bin, args.reclone)
    prompt = PROMPT_TEMPLATE.format(repository_name=owner_repo)

    cmd = build_codex_command(args, repo_dir)
    completed = subprocess.run(cmd, input=prompt, text=True)
    return completed.returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"error: command failed with exit code {exc.returncode}: {exc.cmd}", file=sys.stderr)
        raise SystemExit(exc.returncode)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
