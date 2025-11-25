"""Generate CI/CD pipeline content for GitLab."""

from __future__ import annotations

from typing import Any, Dict, List

from jinja2 import Template, TemplateNotFound

from .project_scanner import ProjectDescriptor
from .template_engine import render_template

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

DEFAULT_GITLAB_TEMPLATE = Template(
    """
stages:
{% for stage in stages %}
  - {{ stage }}
{% endfor %}

variables:
  SONAR_HOST_URL: "{{ ci.sonar_host }}"
  SONAR_TOKEN: "{{ ci.sonar_token }}"
  DOCKER_IMAGE: "{{ ci.docker_image }}"
  DOCKER_TAG: "{{ ci.docker_tag }}"
  DOCKER_IMAGE_FULL: "{{ ci.docker_image_full }}"

{% if cache_paths %}
cache:
  key: "${CI_COMMIT_REF_SLUG}"
  paths:
{% for cache in cache_paths %}
    - {{ cache.path }}
{% endfor %}
{% endif %}

{% for name, job in jobs.items() %}
{{ name }}:
  stage: {{ job.stage }}
{% if job.image %}  image: {{ job.image }}
{% endif %}{% if job.needs %}  needs: [{% for dep in job.needs %}{{ dep }}{% if not loop.last %}, {% endif %}{% endfor %}]
{% endif %}{% if job.variables %}  variables:
{% for key, value in job.variables.items() %}    {{ key }}: "{{ value }}"
{% endfor %}{% endif %}  script:
{% for line in job.script %}    - {{ line }}
{% endfor %}{% if job.artifacts %}  artifacts:
    paths:
{% for art in job.artifacts %}      - {{ art }}
{% endfor %}{% endif %}

{% endfor %}
""".strip()
)


def _select_template(descriptor: ProjectDescriptor) -> str:
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

    raise ValueError(f"Unsupported language for GitLab CI generation: {descriptor.language}")


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
                "sonar": [f"{runner} --no-daemon sonarqube -Dsonar.host.url=$SONAR_HOST_URL -Dsonar.login=$SONAR_TOKEN"],
                "build": [f"{runner} --no-daemon build -x test"],
                "package": [f"{runner} --no-daemon assemble -x test"],
            }
        else:
            runner = "mvn"
            return {
                "prepare": [f"{runner} -B dependency:go-offline"],
                "lint": [f"{runner} -B -DskipTests verify"],
                "test": [f"{runner} -B test"],
                "sonar": [f"{runner} -B sonar:sonar -Dsonar.host.url=$SONAR_HOST_URL -Dsonar.login=$SONAR_TOKEN"],
                "build": [f"{runner} -B package -DskipTests"],
                "package": [f"{runner} -B package -DskipTests"],
            }
    if language == "go":
        return {
            "prepare": ["go mod download"],
            "lint": ["go vet ./..."],
            "test": ["go test ./..."],
            "sonar": ["echo \"Sonar analysis for Go\""],
            "build": ["go build -o app ./..."],
            "package": ["tar -czf app.tar.gz app"],
        }
    if language in {"js", "ts"}:
        pkg_manager = "npm"
        return {
            "prepare": [f"{pkg_manager} ci"],
            "lint": [f"{pkg_manager} run lint"],
            "test": [f"{pkg_manager} test"],
            "sonar": ["echo \"Sonar analysis for Node\""],
            "build": [f"{pkg_manager} run build"],
            "package": ["tar -czf app.tgz ."],
        }
    if language == "python":
        return {
            "prepare": ["python -m pip install --upgrade pip", "pip install -r requirements.txt"],
            "lint": ["flake8 . || true"],
            "test": ["pytest"],
            "sonar": ["echo \"Sonar analysis for Python\""],
            "build": ["python setup.py sdist bdist_wheel || true"],
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


def _cache_paths(descriptor: ProjectDescriptor) -> List[Dict[str, str]]:
    language = (descriptor.language or "").lower()
    build_tool = (descriptor.build_tool or "").lower()
    caches: List[Dict[str, str]] = []

    if build_tool == "maven":
        caches.append({"name": "maven", "path": ".m2/repository"})
    if build_tool == "gradle":
        caches.append({"name": "gradle", "path": ".gradle"})
    if language in {"js", "ts"}:
        caches.append({"name": "npm", "path": "node_modules"})
    if language == "python":
        caches.append({"name": "pip", "path": ".cache/pip"})
    if language == "go":
        caches.append({"name": "go", "path": "go/pkg/mod"})

    return caches


def generate_gitlab_ci(descriptor: ProjectDescriptor, ci_context: Dict[str, Any]) -> str:
    """Return the contents of a .gitlab-ci.yml suited for the project."""
    template_path = _select_template(descriptor)
    scripts = _language_scripts(descriptor)
    caches = _cache_paths(descriptor)

    docker_image = ci_context.get("docker_image", "$CI_REGISTRY_IMAGE")
    docker_tag = ci_context.get("docker_tag", "${CI_COMMIT_SHORT_SHA:-latest}")
    ci = {
        "sonar_host": ci_context.get("sonar_host", "$SONAR_HOST_URL"),
        "sonar_token": ci_context.get("sonar_token", "$SONAR_TOKEN"),
        "docker_image": docker_image,
        "docker_tag": docker_tag,
        "docker_image_full": f"{docker_image}:{docker_tag}",
    }

    jobs: Dict[str, Dict[str, Any]] = {}

    def add_job(
        name: str,
        stage: str,
        script: List[str],
        needs: List[str] | None = None,
        artifacts: List[str] | None = None,
        variables: Dict[str, str] | None = None,
        image: str | None = None,
    ) -> None:
        jobs[name] = {
            "stage": stage,
            "script": script,
            "needs": needs or [],
            "artifacts": artifacts or [],
            "variables": variables or {},
            "image": image,
        }

    add_job("prepare", "prepare", scripts["prepare"])
    add_job("lint", "lint", scripts["lint"], needs=["prepare"])
    add_job("test", "test", scripts["test"], needs=["lint"])
    add_job(
        "sonar",
        "sonar",
        scripts["sonar"],
        needs=["test"],
        variables={"SONAR_HOST_URL": ci["sonar_host"], "SONAR_TOKEN": ci["sonar_token"]},
    )
    add_job("build", "build", scripts["build"], needs=["test"])
    add_job("package", "package", scripts["package"], needs=["build"])
    add_job(
        "docker_build",
        "docker_build",
        [
            "echo $CI_JOB_TOKEN | docker login -u $CI_REGISTRY_USER --password-stdin $CI_REGISTRY",
            f"docker build -t {ci['docker_image_full']} .",
        ],
        needs=["package"],
    )
    add_job(
        "push",
        "push",
        [
            "echo $CI_JOB_TOKEN | docker login -u $CI_REGISTRY_USER --password-stdin $CI_REGISTRY",
            f"docker push {ci['docker_image_full']}",
        ],
        needs=["docker_build"],
    )
    add_job("deploy_staging", "deploy_staging", ["echo Deploying to staging..."], needs=["push"])
    add_job("deploy_prod", "deploy_prod", ["echo Deploying to production..."], needs=["push"])

    context = {
        "descriptor": descriptor,
        "stages": STAGES,
        "ci": ci,
        "cache_paths": caches,
        "jobs": jobs,
    }

    try:
        return render_template(template_path, context)
    except (TemplateNotFound, FileNotFoundError):
        # Fall back to the built-in template if a file-backed template is unavailable.
        return DEFAULT_GITLAB_TEMPLATE.render(**context)
