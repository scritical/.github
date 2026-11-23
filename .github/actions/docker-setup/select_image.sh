#!/usr/bin/env bash
# Print the image docker-setup starts: scritical/private-dev:$DOCKER_TAG, or the images of the docker PR
# that a Depends-On reference on stdin names (owner/repo#N, one per line, from depends-on/depends_on.py).
set -euo pipefail

mapfile -t docker_prs < <(grep -oP '^scritical/docker#\K[0-9]+$' || true)
if (( ${#docker_prs[@]} == 0 )); then
  echo "scritical/private-dev:$DOCKER_TAG"
  exit 0
fi
if (( ${#docker_prs[@]} > 1 )); then
  echo "::error::The description names several docker PRs: ${docker_prs[*]/#/#}. Keep one Depends-On line for scritical/docker." >&2
  exit 1
fi

docker_pr=${docker_prs[0]}
# A docker PR's images have per-platform tags only
case "$RUNNER_ARCH" in
  X64) platform=amd64 ;;
  ARM64) platform=arm64v8 ;;
  *)
    echo "::error::Depends-On needs an X64 or ARM64 runner. Docker PR images are built for amd64 and arm64v8, not for $RUNNER_ARCH." >&2
    exit 1
    ;;
esac
image="scritical/private-dev:$DOCKER_TAG-pr$docker_pr-$platform"

if ! inspect_error=$(docker manifest inspect "$image" 2>&1 > /dev/null); then
  echo "::error::Cannot read image $image: $inspect_error" >&2
  echo "::error::If scritical/docker#$docker_pr has not pushed its images yet, re-run this job after it has. If its image build failed, or the number is wrong, fix the Depends-On line." >&2
  exit 1
fi
echo "::warning::This job runs on the image of scritical/docker#$docker_pr ($image), not on the published image. The tag holds that docker PR's latest pushed build, even after the PR merges or closes. Remove the Depends-On line when the docker PR merges." >&2
echo "$image"
