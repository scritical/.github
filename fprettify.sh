#!/bin/bash

# Format only the files git tracks: never ignored or generated files (build trees, downloaded
# subprojects, virtual environments) or the contents of submodules, which belong to other repos.
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Not inside a git work tree: run this from the repository to format. Exiting"
    exit 2
fi

FPRETTIFY_CONFIG_FILE=""
LOCAL_CONFIG_FILE=".fprettify.rc"
GLOBAL_CONFIG_FILE="../.github/.fprettify.rc"

if [[ ! -z "$1" ]]; then
    # Offer the option of supplying config file through an argument
    echo "Using user supplied fprettify config file: $1"
    FPRETTIFY_CONFIG_FILE="$1"
elif [[ -f "$LOCAL_CONFIG_FILE" ]]; then
    # Use local config file
    echo "Using local fprettify config file: $LOCAL_CONFIG_FILE"
    FPRETTIFY_CONFIG_FILE="$LOCAL_CONFIG_FILE"
elif [[ -f "$GLOBAL_CONFIG_FILE" ]]; then
    # Use global config file
    echo "Using .github shared fprettify config file: $GLOBAL_CONFIG_FILE"
    FPRETTIFY_CONFIG_FILE="$GLOBAL_CONFIG_FILE"
else
    echo "No fprettify config was found. Exiting"
    exit 2
fi

# Run fprettify on non-differentiated Fortran 90 source files
git ls-files -z -- ':(icase)*.f90' ':(exclude,icase)*_b.f90' ':(exclude,icase)*_d.f90' | while IFS= read -r -d '' fileName
do
    echo "Checking $fileName"
    fprettify --config-file "$FPRETTIFY_CONFIG_FILE" "$fileName"

    # Check if this file changed and print a message if it did
    git diff --summary --exit-code $fileName
    if [ $? -ne 0 ]; then
        echo "$fileName was formatted"
    fi
done
