#!/bin/bash

USAGE="
usage: updateYaml [-w WORK_LEVEL] [-r REPO_NAME] [-l REPO_LIST]

Description:
This script generates a .readthedocs.yaml file for a given repository and
copies it to the proper location within the repository. Depending on the
work-level specified, it will copy the file, create a branch, commit, push,
and create a PR on GitHub.

Argument description:
    -w|--work-level     0: Clone and copy yaml file to repository (default)
                        1: Commit yaml file changes to a new branch
                        2: Push the branch to GH
                        3: Create GH PRs
    -r|--repo           Name of a single repository that should be updated
    -l|--repo-list      Text file with a list of repositories that should be updated
    -h|--help           Print this help
"

die () {
    exit 9
}

# Parse input
WORK_LEVEL=0
MANUAL_REPO=""
REPO_LIST=""
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -w|--work-level) WORK_LEVEL="$2"; shift ;;
        -r|--repo ) MANUAL_REPO="$2"; shift ;;
        -l|--repo-list ) REPO_LIST="$2"; shift ;;
        -h|--help) echo "$USAGE";  exit 1 ;;
        *) echo "Unknown parameter passed: $1"; echo "$USAGE"; exit 1 ;;
    esac
    shift
done

# Check input
if [[ -z $MANUAL_REPO && -z $REPO_LIST ]]; then
    echo "Insufficient inputs, see usage:"
    echo "$USAGE"
    die
fi

# If input is specified then we only use that
if [[ ! -z $MANUAL_REPO ]]; then
    REPOS=("$MANUAL_REPO")
elif [[ -f $REPO_LIST ]]; then
    # Read the specified list
    readarray -t REPOS < "$REPO_LIST"
else
    echo "Repo file, $REPO_LIST, not found. Check input, exiting!"
    die
fi

# Check and verify input
echo "The following repo(s) will be updated:"
for repo in ${REPOS[@]}; do
    echo $repo
done

# Make sure everything is good, otherwise abort
read -r -p "Are you sure? [y/N]:" response
response=${response,,} # tolower
if [[ ! "$response" =~ ^(yes|y)$ ]]; then
    echo "Aborting..."
    die
fi

ROOTDIR=$(pwd)

# Create a working tmp directory
WORKDIR="$ROOTDIR/tmp"
rm -rf $WORKDIR && mkdir -p $WORKDIR

BRANCH_NAME="updateRtdYaml"
RTD_PR_TEMPATE_FILE=$WORKDIR/RTD_PR_TEMPATE.md
cat > $RTD_PR_TEMPATE_FILE << EOF
## Purpose
Update \`.readthedocs.yaml\` file

## Expected time until merged
Few days

## Type of change
- [ ] Bugfix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (non-backwards-compatible fix or feature)
- [ ] Code style update (formatting, renaming)
- [ ] Refactoring (no functional changes, no API changes)
- [x] Documentation update
- [x] Maintenance update
- [ ] Other (please describe)

EOF


# Init array to track progress
declare -A REPO_STATUS

checkFailure () {
    if [[ $1 -ne 0 ]]; then
        REPO_STATUS["$2"]="Failed"
        echo "ERROR: Repository, $2, failed. See output for details."
        return $1
    fi
    REPO_STATUS["$2"]="Success"
    return 0
}

# Main loop
for repo in ${REPOS[@]}; do
    # Reset
    cd $WORKDIR
    REPODIR="$WORKDIR/$repo"
    echo ""
    echo "---------------- Updating $repo ------------------------"
    git clone git@github.com:scritical/"$repo".git
    checkFailure $? $repo || continue

    cd $REPODIR
    git checkout -b $BRANCH_NAME
    checkFailure $? $repo || continue

    # Generate the yaml file (just copy for now)
    # python genYaml.py
    cp $ROOTDIR/.rtd.yaml $REPODIR/.readthedocs.yaml

    # Commit the changes
    if [[ $WORK_LEVEL -ge 1 ]]; then
        git add .readthedocs.yaml
        checkFailure $? $repo || continue

        git commit -m "update .readthedocs.yaml"
        checkFailure $? $repo || continue

        # Push branch
        if [[ $WORK_LEVEL -ge 2 ]]; then
            git push --set-upstream origin $BRANCH_NAME
            checkFailure $? $repo || continue

            # Create the PR on GH
            if [[ $WORK_LEVEL -ge 3 ]]; then
                PR_LINK=$(gh pr create --title "Update .readthedocs.yaml" --body-file "$RTD_PR_TEMPATE_FILE")
                checkFailure $? $repo || continue
                # Overwrite the "success" with PR link for summary.
                REPO_STATUS["$repo"]="$PR_LINK"
            fi
        fi
    fi
done

# Print summary at the end so we dont need to go through the output
echo ""
echo "----------------------"
echo "       SUMMARY        "
echo "----------------------"
echo "Repository - Status/PR"
echo "----------------------"
for key in ${!REPO_STATUS[@]}; do
    echo ${key} - ${REPO_STATUS[${key}]}
done
