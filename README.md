# self-deploy

Self Deploy analyzes a Git repository, infers its tech stack, and auto-generates GitLab CI pipelines, multi-stage Dockerfiles, and concise reports — all via local static analysis with no external calls.

## Installation

```bash
pip install -e .
```

Requirements: Python 3.10+, Git CLI, and Docker (for running the local validation stack).

## Usage

Generate automation for a repository:

```bash
self-deploy generate --repo https://github.com/org/java-app.git --output ./out
```

With a branch override and custom output:

```bash
self-deploy generate --repo https://github.com/org/python-service.git --branch develop --output ./generated
```

Artifacts produced in the output directory:
- `.gitlab-ci.yml` — GitLab CI pipeline with prepare, lint, test, sonar, build/package, docker build/push, and staged deploy jobs.
- `Dockerfile` — multi-stage image tailored to the detected language (skipped if an existing Dockerfile was found).
- `sonar-project.properties` — stub SonarQube configuration.
- `report.json` — machine-readable analysis summary.
- `report.md` — human-readable report.

## Local validation stack (GitLab, Runner, SonarQube, Nexus)

Bring up the stack:

```bash
docker-compose up -d
```

Optional: copy `compose/.env.example` to `compose/.env` and adjust secrets/tokens before running (docker-compose already loads it for the services).

### Quick initial setup
- **GitLab**: open http://localhost:8080, set the root password (or use `GITLAB_ROOT_PASSWORD` in `.env`), create a project, and note the runner registration token.
- **GitLab Runner**: set `GITLAB_RUNNER_TOKEN` (via `.env`) before `docker-compose up`, or exec into the runner container and run `gitlab-runner register` using the Docker executor.
- **SonarQube**: open http://localhost:9000, set the admin password, create a project and token; configure `SONAR_HOST_URL` and `SONAR_TOKEN` CI variables.
- **Nexus**: open http://localhost:8081, complete the admin unlock flow, and create the repos you need (Maven/npm/PyPI/Docker hosted/proxy as desired). The Docker hosted repo can be bound to port 8082 (exposed by the compose stack).

### Testing a generated pipeline locally
1. Generate artifacts with `self-deploy generate ...`.
2. Push the generated `.gitlab-ci.yml` and `Dockerfile` to the GitLab instance running in Docker Compose.
3. Add CI/CD variables for registry auth and SonarQube (`SONAR_HOST_URL`, `SONAR_TOKEN`, `CI_REGISTRY_USER`, `CI_REGISTRY_PASSWORD` if needed).
4. Run the pipeline; inspect stages (lint/test/sonar/build/package/docker/deploy) and view results in GitLab and SonarQube.

## Templates and customization
- Templates live under `templates/` (overridable via `SELF_DEPLOY_TEMPLATES_DIR` or `templates_dir` in config).
- CI templates target GitLab and include caching, SonarQube hooks, Docker build/push, and deploy stage stubs.
- Docker templates are multi-stage for Java/Kotlin, Go, Node.js/TypeScript (backend/frontend), and Python.
