#!/bin/bash

# clang-format expects a .clang-format file in the root (local dir) where the command
# is run. Need to check for existing files first. If none copy over the global file
# and remove once done to make sure its not added to git.

# -------------- Command line input --------------
USAGE="
usage: [-d]

Argument description:
    -d|--dry-run    Do not make changes, only simulate formatting changes
"
DRY_RUN=""
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -d|--dry-run) DRY_RUN="--dry-run"; shift ;;
        -h|--help) echo "$USAGE";  exit 1 ;;
        *) echo "Unknown parameter passed: $1"; echo "$USAGE"; exit 1 ;;
    esac
    shift
done

# Set some constants
CLANGFORMAT_CONFIG_FILE=""
LOCAL_CONFIG_FILE=".clang-format"
GLOBAL_CONFIG_FILE="../.github/.clang-format"

# Initialize variables
global=0

if [[ -f "$LOCAL_CONFIG_FILE" ]]; then
    # Use local config file
    echo "Using local config file: $LOCAL_CONFIG_FILE"
    CLANGFORMAT_CONFIG_FILE="$LOCAL_CONFIG_FILE"
elif [[ -f "$GLOBAL_CONFIG_FILE" ]]; then
    # Use global config file
    echo "Using .github shared config file: $GLOBAL_CONFIG_FILE"
    CLANGFORMAT_CONFIG_FILE="$GLOBAL_CONFIG_FILE"
    cp "$GLOBAL_CONFIG_FILE" .
    global=1
else
    echo "No clang-format config was found. Exiting"
    exit 2
fi

# Setting common values
clang_format_args="-style=file --verbose --Werror"
if [[ -z "$DRY_RUN" ]]; then
    # Apply the formatting inplace
    clang_format_args="$clang_format_args -i"
else
    # Only do a dry run
    clang_format_args="$clang_format_args --dry-run"
fi

echo "Running clang-format with args: $clang_format_args"

# Run the formatting
find . -iname '*.h' -o -iname '*.hpp' -o -iname '*.c' -o -iname '*.cpp' | xargs clang-format $clang_format_args

# Store the exit code in case we are running dry-run and find
clang_exit_code=$?

if [[ 1 == "$global" ]]; then
    # Remove only of we copied over
    rm "$LOCAL_CONFIG_FILE"
fi

exit $clang_exit_code