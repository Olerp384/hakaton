"""Utilities for cloning Git repositories into temporary workspaces."""

from __future__ import annotations

import os
import subprocess
import tempfile
from typing import Optional


def clone_repo(repo_url: str, branch: Optional[str] = None) -> str:
    """Clone the given git repo into a temporary directory and return the local path.

    A temporary workspace directory is created and the repository is cloned into it.
    If a branch or tag is provided, that ref is checked out. A RuntimeError is raised
    on any git failure with stderr included for easier debugging.
    """
    workspace = tempfile.mkdtemp(prefix="self-deploy-")
    target_path = os.path.join(workspace, "repo")

    clone_cmd = ["git", "clone"]
    if branch:
        clone_cmd.extend(["--branch", branch, "--single-branch"])
    clone_cmd.extend([repo_url, target_path])

    try:
        subprocess.run(clone_cmd, check=True, capture_output=True, text=True)
        if branch:
            subprocess.run(
                ["git", "-C", target_path, "checkout", branch],
                check=True,
                capture_output=True,
                text=True,
            )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Failed to clone repository '{repo_url}'"
            f"{' at ' + branch if branch else ''}: {exc.stderr or exc}"
        ) from exc

    return target_path
