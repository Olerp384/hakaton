#!/usr/bin/env bash
set -euo pipefail

# Helper to register the GitLab Runner against the GitLab container.
# Usage:
#   GITLAB_RUNNER_TOKEN=XXXX scripts/register_runner.sh
# Optional:
#   GITLAB_URL (default: http://gitlab)
#   RUNNER_IMAGE (default: alpine:latest)
#   RUNNER_DESCRIPTION (default: self-deploy-runner)

TOKEN="${GITLAB_RUNNER_TOKEN:?Set GITLAB_RUNNER_TOKEN env var}"
GITLAB_URL="${GITLAB_URL:-http://gitlab}"
RUNNER_IMAGE="${RUNNER_IMAGE:-alpine:latest}"
RUNNER_DESCRIPTION="${RUNNER_DESCRIPTION:-self-deploy-runner}"

docker run --rm -it \
  --network self_deploy_net \
  -v gitlab_runner_config:/etc/gitlab-runner \
  gitlab/gitlab-runner:alpine register --non-interactive \
  --url "${GITLAB_URL}" \
  --registration-token "${TOKEN}" \
  --executor docker \
  --docker-image "${RUNNER_IMAGE}" \
  --docker-privileged \
  --description "${RUNNER_DESCRIPTION}" \
  --tag-list "local" \
  --run-untagged="true"
