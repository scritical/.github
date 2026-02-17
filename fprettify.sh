#!/bin/bash

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
find . -type f -iname '*.f90' ! -iname '*_b.f90' ! -iname '*_d.f90' -print0 | while read -d $'\0' fileName
do
    echo "Checking $fileName"
    fprettify --config-file "$FPRETTIFY_CONFIG_FILE" "$fileName"

    # Check if this file changed and print a message if it did
    git diff --summary --exit-code $fileName
    if [ $? -ne 0 ]; then
        echo "$fileName was formatted"
    fi
done
