"""Reporting utilities for self-deploy."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

from .project_scanner import ProjectDescriptor


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _descriptor_dict(descriptor: ProjectDescriptor) -> Dict[str, Any]:
    return asdict(descriptor)


def generate_reports(
    output_dir: Path,
    descriptor: ProjectDescriptor,
    ci_template: str,
    dockerfile_template: str | None,
    generated_files: List[str],
    warnings: List[str],
) -> None:
    """Write JSON and Markdown reports to the output directory."""
    report_json_path = output_dir / "report.json"
    report_md_path = output_dir / "report.md"

    descriptor_dict = _descriptor_dict(descriptor)
    report_data = {
        "descriptor": descriptor_dict,
        "ci_template": ci_template,
        "dockerfile_template": dockerfile_template,
        "generated_files": generated_files,
        "warnings": warnings,
    }

    _write_file(report_json_path, json.dumps(report_data, indent=2))

    md_lines = [
        "# Self Deploy Report",
        "",
        "## Detected Stack",
        f"- Language: {descriptor.language or 'unknown'}",
        f"- Framework: {descriptor.framework or 'unknown'}",
        f"- Build tool: {descriptor.build_tool or 'unknown'}",
        f"- Package manager: {descriptor.package_manager or 'unknown'}",
        f"- Tests: {', '.join(descriptor.tests) if descriptor.tests else 'none detected'}",
        f"- Dockerfile present: {'yes' if descriptor.dockerfile_present else 'no'}",
        f"- Kubernetes manifests: {'yes' if descriptor.has_k8s_manifests else 'no'}",
        "",
        "## Templates",
        f"- CI template: {ci_template}",
        f"- Dockerfile template: {dockerfile_template or 'skipped (existing)'}",
        "",
        "## Generated Files",
    ]
    md_lines.extend(f"- {path}" for path in generated_files)
    md_lines.append("")
    md_lines.append("## Warnings")
    if warnings:
        md_lines.extend(f"- {w}" for w in warnings)
    else:
        md_lines.append("- None")

    _write_file(report_md_path, "\n".join(md_lines))
