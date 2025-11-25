"""Scan a repository and produce a raw project descriptor."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ProjectDescriptor:
    language: Optional[str] = None
    framework: Optional[str] = None
    build_tool: Optional[str] = None
    tests: List[str] = field(default_factory=list)
    package_manager: Optional[str] = None
    version: Optional[str] = None
    dockerfile_present: bool = False
    has_k8s_manifests: bool = False
    root_path: str = ""
    additional_metadata: Dict[str, Any] = field(default_factory=dict)


TARGET_FILES = {
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "go.mod",
    "package.json",
    "tsconfig.json",
    "pyproject.toml",
    "requirements.txt",
    "pipfile",
    "dockerfile",
    "docker-compose.yml",
}


def _looks_like_k8s_manifest(path: str, filename: str) -> bool:
    """Heuristic to identify Kubernetes manifest files."""
    lower = filename.lower()
    if not lower.endswith((".yml", ".yaml")):
        return False

    k8s_indicators = (
        "k8s",
        "kubernetes",
        "deployment",
        "service",
        "ingress",
        "statefulset",
        "daemonset",
        "pod",
        "cronjob",
    )
    if any(indicator in lower for indicator in k8s_indicators):
        return True

    try:
        with open(path, "r", encoding="utf-8") as handle:
            head = handle.read(2048)
    except OSError:
        return False

    return "apiVersion" in head and "kind" in head


def _load_file_content(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return None


def scan_project(root_path: str) -> ProjectDescriptor:
    """Walk the project directory, detect key files and populate a raw descriptor."""
    root_abs = os.path.abspath(root_path)
    metadata: Dict[str, Any] = {
        "detected_files": {},
        "file_contents": {},
        "k8s_manifests": [],
        "docker_compose_files": [],
        "dockerfiles": [],
    }

    descriptor = ProjectDescriptor(
        root_path=root_abs,
        dockerfile_present=False,
        has_k8s_manifests=False,
        additional_metadata=metadata,
    )

    for current_root, _dirs, files in os.walk(root_abs):
        for filename in files:
            filename_lower = filename.lower()
            filepath = os.path.join(current_root, filename)
            relpath = os.path.relpath(filepath, root_abs)

            # Track targeted files
            if filename_lower in TARGET_FILES:
                metadata["detected_files"].setdefault(filename_lower, []).append(relpath)

                if filename_lower == "dockerfile":
                    descriptor.dockerfile_present = True
                    metadata["dockerfiles"].append(relpath)
                if filename_lower == "docker-compose.yml":
                    metadata["docker_compose_files"].append(relpath)

                content = _load_file_content(filepath)
                if content is not None:
                    metadata["file_contents"].setdefault(filename_lower, []).append(content)

            # Kubernetes heuristics
            if _looks_like_k8s_manifest(filepath, filename):
                descriptor.has_k8s_manifests = True
                metadata["k8s_manifests"].append(relpath)

    return descriptor
