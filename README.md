# self-deploy

Self Deploy analyzes Git repositories to infer language/tooling, then auto-generates CI/CD pipelines and multi-stage Dockerfiles so projects can get production-ready automation with minimal manual setup.

## Local stack (GitLab, Runner, SonarQube, Nexus)

Start the supporting services:

```bash
docker-compose up -d
```

### Quick initial setup (high level)
- GitLab: open http://localhost:8080, set root password, create a project and obtain a runner registration token.
- GitLab Runner: set `GITLAB_RUNNER_TOKEN` env var before `docker-compose up` or register manually inside the `gitlab-runner` container to use the Docker executor.
- SonarQube: open http://localhost:9000, set admin password, create a project and token; configure `SONAR_HOST_URL` and `SONAR_TOKEN` in CI variables.
- Nexus: open http://localhost:8081, complete initial admin password flow, create the repos you need (e.g., Maven/npm/pypi/docker proxy/hosted).

## Using self-deploy

Generate artifacts for a repository:

```bash
self-deploy generate --repo <url> --output ./out
```

The tool produces:
- `.gitlab-ci.yml` — GitLab CI pipeline tailored to the detected stack.
- `Dockerfile` — multi-stage build aligned with the project language/tooling.
- `report.json` — structured report of detected tech and generated artifacts.
- `report.md` — human-readable summary of the findings.
