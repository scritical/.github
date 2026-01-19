#!/usr/bin/env python3
"""
Merge two INI-style configuration files.

This script reads a default config and a repo-specific config,
merges them (with repo-specific values taking precedence),
and writes the result to an output file.

Usage:
    python combine-config.py default.cfg repo.cfg output.cfg

If the repo config file doesn't exist, the default config is used as-is.
"""
import argparse
import configparser
import sys
from pathlib import Path


def merge_configs(default_path: str, repo_path: str, output_path: str) -> None:
    """Merge default and repo configs, writing result to output."""
    # Read default config
    config = configparser.ConfigParser()
    config.read(default_path)

    # Read and merge repo config if it exists
    repo_file = Path(repo_path)
    if repo_file.exists():
        config_repo = configparser.ConfigParser()
        config_repo.read(repo_path)

        # Merge: repo config overrides default
        for section in config_repo.sections():
            if not config.has_section(section):
                config.add_section(section)
            for key, value in config_repo.items(section):
                config.set(section, key, value)

    # Write merged config
    with open(output_path, "w") as f:
        config.write(f)


def main() -> int:
    """Parse arguments and run merge."""
    parser = argparse.ArgumentParser(
        description="Merge two INI-style configuration files"
    )
    parser.add_argument("default", type=str, help="Path to default config file")
    parser.add_argument("repo", type=str, help="Path to repo-specific config file")
    parser.add_argument("output", type=str, help="Path for merged output file")
    args = parser.parse_args()

    merge_configs(args.default, args.repo, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
