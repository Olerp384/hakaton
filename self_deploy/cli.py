"""Command line interface for the self-deploy tool."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

import yaml

from .dockerfile_generator import DockerfileRenderResult, generate_dockerfile
from .pipeline_generator import PipelineRenderResult, generate_gitlab_ci
from .project_scanner import ProjectDescriptor, scan_project
from .repo_cloner import clone_repo
from .reporter import generate_reports
from .tech_detector import detect_tech


def _load_config(path: Path | None) -> Dict[str, Any]:
    if not path:
        return {}
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        if path.suffix.lower() in {".yml", ".yaml"}:
            return yaml.safe_load(handle) or {}
        return json.load(handle)


def _write_output(path: Path, content: str, overwrite: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        return
    path.write_text(content, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="self-deploy",
        description="Generate CI/CD pipelines and Dockerfiles based on repository analysis.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser(
        "generate",
        help="Generate CI/CD pipeline and Dockerfile assets.",
    )
    generate.add_argument(
        "--repo",
        required=True,
        help="Git repository URL to analyze.",
    )
    generate.add_argument(
        "--branch",
        default=None,
        help="Optional branch or tag to check out.",
    )
    generate.add_argument(
        "--ci",
        default="gitlab",
        choices=["gitlab"],
        help="Target CI provider.",
    )
    generate.add_argument(
        "--output",
        default="./out",
        help="Path to write generated artifacts.",
    )
    generate.add_argument(
        "--config",
        default=None,
        help="Path to optional configuration file (YAML or JSON).",
    )

    return parser


def _summarize(descriptor: ProjectDescriptor, generated_files: list[str]) -> str:
    parts = [
        f"Language: {descriptor.language or 'unknown'}",
        f"Framework: {descriptor.framework or 'unknown'}",
        f"Build tool: {descriptor.build_tool or 'unknown'}",
        f"Tests: {', '.join(descriptor.tests) if descriptor.tests else 'none'}",
        f"Generated: {', '.join(generated_files)}",
    ]
    return " | ".join(parts)


def _generate_sonar_properties(descriptor: ProjectDescriptor, ci_context: Dict[str, Any]) -> str:
    project_key = f"self-deploy-{descriptor.language or 'project'}"
    host = ci_context.get("sonar_host", "http://sonarqube:9000")
    return "\n".join(
        [
            f"sonar.projectKey={project_key}",
            f"sonar.host.url={host}",
            "sonar.sources=.",
            "sonar.login=${SONAR_TOKEN}",
        ]
    )


def handle_generate(args: argparse.Namespace) -> int:
    config = _load_config(Path(args.config)) if args.config else {}
    output_dir = Path(args.output).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    templates_dir_override = None
    if isinstance(config, dict):
        templates_dir_override = config.get("templates_dir")
    if templates_dir_override:
        os.environ.setdefault("SELF_DEPLOY_TEMPLATES_DIR", str(templates_dir_override))

    repo_path = clone_repo(args.repo, args.branch)
    raw_descriptor = scan_project(repo_path)
    descriptor = detect_tech(raw_descriptor)

    warnings: list[str] = []
    generated_files: list[str] = []

    ci_context: Dict[str, Any] = config.get("ci", {}) if isinstance(config, dict) else {}

    if not descriptor.language:
        warnings.append("Unsupported or unknown language detected; falling back to generic pipeline.")
    if not descriptor.tests:
        warnings.append("No tests detected; consider adding a test suite.")

    pipeline_result: PipelineRenderResult = generate_gitlab_ci(descriptor, ci_context)
    gitlab_ci_path = output_dir / ".gitlab-ci.yml"
    _write_output(gitlab_ci_path, pipeline_result.content)
    generated_files.append(str(gitlab_ci_path))

    dockerfile_result: DockerfileRenderResult | None = None
    dockerfile_template_used: str | None = None
    if descriptor.dockerfile_present:
        warnings.append("Existing Dockerfile detected; generation skipped.")
    else:
        dockerfile_result = generate_dockerfile(descriptor)
        dockerfile_template_used = dockerfile_result.template_used
        dockerfile_path = output_dir / "Dockerfile"
        _write_output(dockerfile_path, dockerfile_result.content)
        generated_files.append(str(dockerfile_path))

    sonar_content = _generate_sonar_properties(descriptor, ci_context)
    sonar_path = output_dir / "sonar-project.properties"
    existed_before = sonar_path.exists()
    _write_output(sonar_path, sonar_content, overwrite=False)
    if not existed_before:
        generated_files.append(str(sonar_path))

    report_files = [str(output_dir / "report.json"), str(output_dir / "report.md")]

    generate_reports(
        output_dir=output_dir,
        descriptor=descriptor,
        ci_template=pipeline_result.template_used,
        dockerfile_template=dockerfile_template_used,
        generated_files=generated_files + report_files,
        warnings=warnings,
    )
    generated_files.extend(report_files)

    print(_summarize(descriptor, generated_files))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "generate":
        try:
            return handle_generate(args)
        except Exception as exc:  # pragma: no cover - CLI surface
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
