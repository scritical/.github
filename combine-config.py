#!/usr/bin/env python3
"""Merge two INI-style configuration files.

This script merges a *default* INI config with an optional *repo-specific* INI
config, writing the merged result to an output path. If the repo-specific
config file does not exist, the default config is written as-is.

Notes
-----
The merge behavior is:

- Sections present only in the default config are preserved.
- Sections present in the repo config are added if missing.
- For keys present in both configs, the repo config value overrides the
    default.

Examples
--------
From the command line::

        python combine-config.py default.cfg repo.cfg merged.cfg

"""
import argparse
import configparser
import sys
from pathlib import Path


def merge_configs(default_path: str, repo_path: str, output_path: str) -> None:
    """Merge a default config with an optional repo config.

    Parameters
    ----------
    default_path : str
        Path to the default INI-style configuration file.
    repo_path : str
        Path to the repo-specific INI-style configuration file. If this file
        does not exist, the default config is used without modification.
    output_path : str
        Path to write the merged INI configuration.

    Returns
    -------
    None
        This function writes the merged configuration to ``output_path``.
    """
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
    """CLI entry point.

    Parses command-line arguments and writes a merged configuration file.

    Returns
    -------
    int
        Process exit code. Returns ``0`` on successful completion.
    """
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
