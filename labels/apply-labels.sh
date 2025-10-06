#!/bin/bash

# this is inspired partially by
# https://github.com/alphagov/design-system-team-labels

# these are the files storing the repos
ALL_REPOS=repos.json
ACTIVE_REPOS=repos.txt
LABELS_FILE=labels.yaml

# for github-label-sync
args=(
  # --allow-added-labels # keep any existing labels that are not in the config
  --labels $LABELS_FILE # we use yaml files
)

# Unless the APPLY environment variable is provided, just do a dry run and show
# the changes that we would make.
if [[ -z "$APPLY" ]]; then
  args+=(--dry-run)
fi

# We exit if $GITHUB_TOKEN does not exist
if [[ -z "$GITHUB_TOKEN" ]]; then
  echo "The environment variable \$GITHUB_TOKEN needs to be defined" && exit 1
fi

# get all repos
# this relies on an authenticated gh session
gh api graphql -F owner='scritical' -f query='
  query($owner: String!) {
    organization(login: $owner) {
      repositories(first: 100) {
        nodes {
          nameWithOwner
          isArchived
          repositoryTopics(first: 100) {
            nodes {
              topic {
                name
              }
            }
          }
        }
      }
    }
  }
' | jq > $ALL_REPOS

# filter out archived ones
python filter-repos.py $ALL_REPOS $ACTIVE_REPOS

# read the file and store in bash array
readarray -t repos < $ACTIVE_REPOS

for repo in ${repos[*]}; do
  echo
  echo "---"
  echo "$repo"
  echo "---"

  npx github-label-sync -a "$GITHUB_TOKEN" "${args[@]}" "$repo"
done
