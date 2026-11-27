#!/usr/bin/env bash
# Print the image docker-setup starts, from $DOCKER_TAG and the Depends-On references on stdin.
set -euo pipefail

readonly IMAGE_REPOSITORY=scritical/private-dev
readonly DOCKER_REPOSITORY=scritical/docker

docker_prs=()
while read -r reference || [[ -n $reference ]]; do
  if [[ $reference =~ ^${DOCKER_REPOSITORY}#([0-9]+)$ ]]; then
    docker_prs+=("${BASH_REMATCH[1]}")
  fi
done
if (( ${#docker_prs[@]} == 0 )); then
  echo "$IMAGE_REPOSITORY:$DOCKER_TAG"
  exit 0
fi
if (( ${#docker_prs[@]} > 1 )); then
  echo "::error::The description names several docker PRs: ${docker_prs[*]/#/#}. Keep one Depends-On line for $DOCKER_REPOSITORY." >&2
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
image="$IMAGE_REPOSITORY:$DOCKER_TAG-pr$docker_pr-$platform"

if ! inspect_error=$(docker manifest inspect "$image" 2>&1 > /dev/null); then
  echo "::error::Cannot read image $image: $inspect_error" >&2
  echo "::error::If $DOCKER_REPOSITORY#$docker_pr has not pushed its images yet, re-run this job after it has. If its image build failed, fix that docker PR. If the number is wrong, fix the Depends-On line." >&2
  exit 1
fi
echo "::warning::This job runs on the image of $DOCKER_REPOSITORY#$docker_pr ($image), not on the published image. The tag holds that docker PR's latest pushed build, even after the PR merges or closes. Remove the Depends-On line when the docker PR merges." >&2
echo "$image"
