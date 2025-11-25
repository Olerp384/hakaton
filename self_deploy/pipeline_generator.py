"""Generate CI/CD pipeline content for GitLab based on project descriptors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from jinja2 import TemplateNotFound

from .project_scanner import ProjectDescriptor
from .template_engine import render_template


@dataclass
class PipelineRenderResult:
    """Result of rendering a CI pipeline template."""

    content: str
    template_used: str
    context: Dict[str, Any]


STAGES: List[str] = [
    "prepare",
    "lint",
    "test",
    "sonar",
    "build",
    "package",
    "docker_build",
    "push",
    "deploy_staging",
    "deploy_prod",
]


def select_gitlab_template(descriptor: ProjectDescriptor) -> str:
    """Select the GitLab CI template path for a project."""
    language = (descriptor.language or "").lower()
    build_tool = (descriptor.build_tool or "").lower()

    if language in {"java", "kotlin"}:
        if build_tool == "maven":
            return "gitlab/java-maven.yml.j2"
        return "gitlab/java-gradle.yml.j2"
    if language == "go":
        return "gitlab/go.yml.j2"
    if language in {"js", "ts"}:
        return "gitlab/node.yml.j2"
    if language == "python":
        return "gitlab/python.yml.j2"

    return "gitlab/generic.yml.j2"


def _base_image(descriptor: ProjectDescriptor) -> str:
    language = (descriptor.language or "").lower()
    build_tool = (descriptor.build_tool or "").lower()
    if language in {"java", "kotlin"}:
        if build_tool == "gradle":
            return "gradle:8-jdk17"
        return "maven:3.9-eclipse-temurin-17"
    if language == "go":
        return "golang:1.22"
    if language in {"js", "ts"}:
        return "node:20"
    if language == "python":
        return "python:3.12"
    return "alpine:3.19"


def _cache_paths(descriptor: ProjectDescriptor) -> List[str]:
    language = (descriptor.language or "").lower()
    build_tool = (descriptor.build_tool or "").lower()
    caches: List[str] = []

    if build_tool == "maven":
        caches.append(".m2/repository")
    if build_tool == "gradle":
        caches.append(".gradle")
    if language in {"js", "ts"}:
        caches.append("node_modules")
        caches.append(".npm")
    if language == "python":
        caches.append(".cache/pip")
    if language == "go":
        caches.append("go/pkg/mod")
    return caches


def _language_scripts(descriptor: ProjectDescriptor) -> Dict[str, List[str]]:
    language = (descriptor.language or "").lower()
    build_tool = (descriptor.build_tool or "").lower()

    if language in {"java", "kotlin"}:
        if build_tool == "gradle":
            runner = "./gradlew"
            return {
                "prepare": [f"{runner} --no-daemon --version"],
                "lint": [f"{runner} --no-daemon check"],
                "test": [f"{runner} --no-daemon test"],
                "sonar": [
                    f"{runner} --no-daemon sonarqube "
                    "-Dsonar.host.url=$SONAR_HOST_URL "
                    "-Dsonar.login=$SONAR_TOKEN"
                ],
                "build": [f"{runner} --no-daemon build -x test"],
                "package": [f"{runner} --no-daemon assemble -x test"],
            }
        runner = "mvn"
        return {
            "prepare": [f"{runner} -B dependency:go-offline"],
            "lint": [f"{runner} -B -DskipTests verify"],
            "test": [f"{runner} -B test"],
            "sonar": [
                f"{runner} -B sonar:sonar -Dsonar.host.url=$SONAR_HOST_URL -Dsonar.login=$SONAR_TOKEN"
            ],
            "build": [f"{runner} -B package -DskipTests"],
            "package": [f"{runner} -B package -DskipTests"],
        }

    if language == "go":
        return {
            "prepare": ["go mod download"],
            "lint": ["go vet ./..."],
            "test": ["go test ./..."],
            "sonar": ["echo \"Run SonarQube scanner for Go\""],
            "build": ["go build -o app ./..."],
            "package": ["tar -czf app.tar.gz app"],
        }

    if language in {"js", "ts"}:
        pkg_manager = "npm"
        return {
            "prepare": [f"{pkg_manager} ci"],
            "lint": [f"{pkg_manager} run lint"],
            "test": [f"{pkg_manager} test -- --ci --runInBand"],
            "sonar": ["echo \"Run SonarQube scanner for Node.js\""],
            "build": [f"{pkg_manager} run build"],
            "package": ["tar -czf app.tgz dist"],
        }

    if language == "python":
        return {
            "prepare": ["python -m pip install --upgrade pip", "pip install -r requirements.txt"],
            "lint": ["flake8 . || true"],
            "test": ["pytest"],
            "sonar": ["echo \"Run SonarQube scanner for Python\""],
            "build": ["python -m pip install build && python -m build || true"],
            "package": ["ls dist || true"],
        }

    return {
        "prepare": ["echo \"Prepare stage placeholder\""],
        "lint": ["echo \"Lint stage placeholder\""],
        "test": ["echo \"Test stage placeholder\""],
        "sonar": ["echo \"Sonar stage placeholder\""],
        "build": ["echo \"Build stage placeholder\""],
        "package": ["echo \"Package stage placeholder\""],
    }


def _deploy_rules(target: str) -> List[Dict[str, Any]]:
    if target == "staging":
        return [{"if": '$CI_COMMIT_BRANCH == "develop"'}]
    return [{"if": '$CI_COMMIT_BRANCH == "main"'}, {"if": "$CI_COMMIT_TAG"}]


def generate_gitlab_ci(descriptor: ProjectDescriptor, ci_context: Dict[str, Any]) -> PipelineRenderResult:
    """Return the contents of a .gitlab-ci.yml suited for the project."""
    template_path = select_gitlab_template(descriptor)
    scripts = _language_scripts(descriptor)
    caches = _cache_paths(descriptor)

    docker_image = ci_context.get("docker_image", "$CI_REGISTRY_IMAGE")
    docker_tag = ci_context.get("docker_tag", "${CI_COMMIT_SHORT_SHA:-latest}")
    docker_image_full = f"{docker_image}:{docker_tag}"
    ci = {
        "sonar_host": ci_context.get("sonar_host", "http://sonarqube:9000"),
        "sonar_token": ci_context.get("sonar_token", "$SONAR_TOKEN"),
        "docker_image": docker_image,
        "docker_tag": docker_tag,
        "docker_image_full": docker_image_full,
        "registry": ci_context.get("registry", "$CI_REGISTRY"),
    }

    base_image = ci_context.get("base_image") or _base_image(descriptor)
    job_defaults: Dict[str, Any] = {
        "image": base_image,
        "cache_paths": caches,
        "before_script": ci_context.get("before_script", []),
    }

    jobs: Dict[str, Dict[str, Any]] = {}

    # Artifacts per language/build tool
    package_artifacts: List[str] = []
    build_artifacts: List[str] = []
    language = (descriptor.language or "").lower()
    build_tool = (descriptor.build_tool or "").lower()
    if language in {"java", "kotlin"}:
        package_artifacts = ["target/*.jar"] if build_tool == "maven" else ["build/libs/*.jar"]
        build_artifacts = package_artifacts
    elif language == "go":
        package_artifacts = ["app", "app.tar.gz"]
        build_artifacts = ["app"]
    elif language in {"js", "ts"}:
        package_artifacts = ["app.tgz", "dist/"]
        build_artifacts = ["dist/"]
    elif language == "python":
        package_artifacts = ["dist/"]
        build_artifacts = ["dist/"]

    def add_job(
        name: str,
        stage: str,
        script: List[str],
        needs: Optional[List[str]] = None,
        artifacts: Optional[List[str]] = None,
        variables: Optional[Dict[str, str]] = None,
        image: Optional[str] = None,
        rules: Optional[List[Dict[str, Any]]] = None,
        services: Optional[List[str]] = None,
    ) -> None:
        jobs[name] = {
            "stage": stage,
            "script": script,
            "needs": needs or [],
            "artifacts": artifacts or [],
            "variables": variables or {},
            "image": image,
            "rules": rules or [],
            "services": services or [],
            "cache_paths": caches
            if stage not in {"docker_build", "push", "deploy_staging", "deploy_prod"}
            else [],
        }

    detected_dirs = descriptor.additional_metadata.get("detected_dirs", {}) if descriptor.additional_metadata else {}
    has_integration = any("integration" in name or "e2e" in name for name in detected_dirs.keys())

    add_job("prepare", "prepare", scripts["prepare"])
    add_job("lint", "lint", scripts["lint"], needs=["prepare"])
    add_job("test", "test", scripts["test"], needs=["lint"])
    if has_integration:
        add_job("integration_test", "test", ["echo Running integration tests..."], needs=["lint"])
    add_job(
        "sonar",
        "sonar",
        scripts["sonar"],
        needs=["test"],
        variables={"SONAR_HOST_URL": ci["sonar_host"], "SONAR_TOKEN": ci["sonar_token"]},
    )
    add_job("build", "build", scripts["build"], needs=["test"], artifacts=build_artifacts)
    add_job("package", "package", scripts["package"], needs=["build"], artifacts=package_artifacts)
    add_job(
        "docker_build",
        "docker_build",
        [
            "echo $CI_JOB_TOKEN | docker login -u $CI_REGISTRY_USER --password-stdin $CI_REGISTRY",
            f"docker build -t {docker_image_full} .",
            f"docker save {docker_image_full} -o image.tar",
        ],
        needs=["package"],
        image="docker:24",
        services=["docker:24-dind"],
        variables={"DOCKER_TLS_CERTDIR": ""},
        artifacts=["image.tar"],
    )
    add_job(
        "push",
        "push",
        [
            "echo $CI_JOB_TOKEN | docker login -u $CI_REGISTRY_USER --password-stdin $CI_REGISTRY",
            f"docker push {docker_image_full}",
        ],
        needs=["docker_build"],
        image="docker:24",
        services=["docker:24-dind"],
        variables={"DOCKER_TLS_CERTDIR": ""},
    )
    add_job(
        "deploy_staging",
        "deploy_staging",
        ["echo Deploying to staging..."],
        needs=["push"],
        rules=_deploy_rules("staging"),
    )
    add_job(
        "deploy_prod",
        "deploy_prod",
        ["echo Deploying to production..."],
        needs=["push"],
        rules=_deploy_rules("prod"),
    )

    context = {
        "descriptor": descriptor,
        "stages": STAGES,
        "ci": ci,
        "jobs": jobs,
        "job_defaults": job_defaults,
    }

    try:
        content = render_template(template_path, context)
        used_template = template_path
    except (TemplateNotFound, FileNotFoundError):
        # Fallback generic template content
        used_template = "generated-inline"
        content_lines = ["stages:"] + [f"  - {stage}" for stage in STAGES]
        content_lines += [
            "variables:",
            f"  SONAR_HOST_URL: \"{ci['sonar_host']}\"",
            f"  SONAR_TOKEN: \"{ci['sonar_token']}\"",
            f"  DOCKER_IMAGE: \"{ci['docker_image']}\"",
            f"  DOCKER_TAG: \"{ci['docker_tag']}\"",
            f"  DOCKER_IMAGE_FULL: \"{ci['docker_image_full']}\"",
        ]
        for name, job in jobs.items():
            content_lines.append(f"\n{name}:")
            content_lines.append(f"  stage: {job['stage']}")
            if job["needs"]:
                content_lines.append("  needs:")
                for need in job["needs"]:
                    content_lines.append(f"    - {need}")
            content_lines.append("  script:")
            for line in job["script"]:
                content_lines.append(f"    - {line}")
        content = "\n".join(content_lines)

    return PipelineRenderResult(content=content, template_used=used_template, context=context)
