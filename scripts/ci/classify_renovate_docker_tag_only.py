#!/usr/bin/env python3
"""Classify a pull request as a Renovate Docker image tag-only change."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

RENOVATE_AUTHOR = "renovate[bot]"
SERVICE_FILE_RE = re.compile(r"^ansible/group_vars/all/services/[A-Za-z0-9][A-Za-z0-9_.-]*\.ya?ml$")
GIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{40,64}$")
IMAGE_LINE_RE = re.compile(
    r"^(?P<prefix> *image: +)"
    r"(?P<quote>['\"]?)"
    r"(?P<repository>[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*)"
    r":(?P<tag>[A-Za-z0-9_][A-Za-z0-9_.-]{0,127})"
    r"(?:@(?P<digest>sha256:[a-f0-9]{64}))?"
    r"(?P=quote)(?P<suffix> *(?:\r?\n)?)$"
)


@dataclass(frozen=True)
class Classification:
    renovate_docker_tag_only: bool
    changed_files: tuple[str, ...] = ()
    comparison_base: str = ""
    reason: str = ""


@dataclass(frozen=True)
class ImageReference:
    prefix: str
    quote: str
    repository: str
    tag: str
    digest: str | None
    suffix: str


def _run_git(repository: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", *args],
        cwd=repository,
        check=True,
        capture_output=True,
    ).stdout


def _parse_image_line(line: str) -> ImageReference | None:
    match = IMAGE_LINE_RE.fullmatch(line)
    if match is None:
        return None
    return ImageReference(**match.groupdict())


def _is_tag_only_file_change(base_content: str, head_content: str) -> bool:
    base_lines = base_content.splitlines(keepends=True)
    head_lines = head_content.splitlines(keepends=True)
    if len(base_lines) != len(head_lines):
        return False

    found_image_change = False
    for base_line, head_line in zip(base_lines, head_lines, strict=True):
        if base_line == head_line:
            continue

        base_image = _parse_image_line(base_line)
        head_image = _parse_image_line(head_line)
        if base_image is None or head_image is None:
            return False
        if (
            base_image.prefix != head_image.prefix
            or base_image.quote != head_image.quote
            or base_image.repository != head_image.repository
            or base_image.suffix != head_image.suffix
        ):
            return False
        if (base_image.tag, base_image.digest) == (head_image.tag, head_image.digest):
            return False
        found_image_change = True

    return found_image_change


def _modified_files(repository: Path, comparison_base: str, head_sha: str) -> tuple[str, ...] | None:
    raw_status = _run_git(
        repository,
        "diff",
        "--name-status",
        "-z",
        "--no-renames",
        comparison_base,
        head_sha,
        "--",
    )
    fields = raw_status.decode("utf-8").split("\0")
    if fields[-1:] == [""]:
        fields.pop()
    if not fields or len(fields) % 2 != 0:
        return None

    changed_files: list[str] = []
    for status, path in zip(fields[::2], fields[1::2], strict=True):
        if status != "M" or SERVICE_FILE_RE.fullmatch(path) is None:
            return None
        changed_files.append(path)

    return tuple(changed_files)


def classify(
    *,
    event_name: str,
    pr_author: str,
    base_sha: str,
    head_sha: str,
    repository: Path,
) -> Classification:
    """Return true only for a proven Renovate service image tag-only diff."""
    if event_name != "pull_request":
        return Classification(False, reason="event is not pull_request")
    if pr_author != RENOVATE_AUTHOR:
        return Classification(False, reason="pull request author is not Renovate")
    if GIT_SHA_RE.fullmatch(base_sha) is None or GIT_SHA_RE.fullmatch(head_sha) is None:
        return Classification(False, reason="base or head SHA is malformed")

    try:
        comparison_base = _run_git(repository, "merge-base", base_sha, head_sha).decode("ascii").strip()
        if GIT_SHA_RE.fullmatch(comparison_base) is None:
            return Classification(False, reason="merge base is malformed")

        changed_files = _modified_files(repository, comparison_base, head_sha)
        if not changed_files:
            return Classification(False, reason="diff has no eligible modified service files")

        for path in changed_files:
            base_content = _run_git(repository, "show", f"{comparison_base}:{path}").decode("utf-8")
            head_content = _run_git(repository, "show", f"{head_sha}:{path}").decode("utf-8")
            if not _is_tag_only_file_change(base_content, head_content):
                return Classification(False, reason=f"{path} contains a non-image or non-tag change")
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError, ValueError) as error:
        return Classification(False, reason=f"unable to inspect diff: {type(error).__name__}")

    return Classification(True, changed_files, comparison_base)


def _emit_github_outputs(classification: Classification) -> None:
    value = str(classification.renovate_docker_tag_only).lower()
    print(f"renovate_docker_tag_only={value}")
    if classification.renovate_docker_tag_only:
        print(f"comparison_base={classification.comparison_base}")
        print("changed_files<<RENOVATE_DOCKER_CHANGED_FILES")
        print("\n".join(classification.changed_files))
        print("RENOVATE_DOCKER_CHANGED_FILES")
    else:
        print("comparison_base=")
        print("changed_files=")
        print(f"classification_reason={classification.reason}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-name", default="")
    parser.add_argument("--pr-author", default="")
    parser.add_argument("--base-sha", default="")
    parser.add_argument("--head-sha", default="")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)

    classification = classify(
        event_name=args.event_name,
        pr_author=args.pr_author,
        base_sha=args.base_sha,
        head_sha=args.head_sha,
        repository=args.repository,
    )
    _emit_github_outputs(classification)
    if not classification.renovate_docker_tag_only:
        print(f"Renovate Docker fast path disabled: {classification.reason}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
