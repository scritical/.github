#!/usr/bin/env python3
"""Summarise a cloc diff report as a Markdown table of line changes.

Reads the JSON written by ``cloc --git-diff-rel --by-file --json BASE HEAD`` and
splits the added, modified and removed lines of each changed file into source,
test and docs files. Source and test lines are further split into code and
comment lines. Docs lines are not, because cloc's code/comment split of prose
formats such as reStructuredText and Markdown is not meaningful. Blank lines
are not counted.

Examples
--------
From the command line::

        python pr_line_stats.py cloc.json --base abc123 --head def456 > stats.md

"""

# Future modules
from __future__ import annotations

# Standard Python modules
import argparse
import json
from pathlib import Path
import re
import sys

DEFAULT_TEST_REGEX = r"(^|/)([^/]*_)?tests?/|(^|/)test_[^/]*$|_test\.[^/]+$"
DEFAULT_DOCS_REGEX = r"(^|/)docs?/|\.(md|rst)$"
CHANGE_TYPES: tuple[str, ...] = ("added", "modified", "removed")
LINE_TYPES = ("code", "comment")
# Table row of each (file group, line type) pair, in table order. Both line types of docs files share one row.
ROW_LABELS = {
    ("source", "code"): "Source code",
    ("source", "comment"): "Source comments",
    ("test", "code"): "Test code",
    ("test", "comment"): "Test comments",
    ("docs", "code"): "Docs",
    ("docs", "comment"): "Docs",
}

Tally = dict[str, dict[str, int]]


def parse_report(text: str) -> dict:
    """Parse the output of cloc, which is JSON unless no countable file changed.

    Parameters
    ----------
    text : str
        Everything cloc printed to stdout.

    Returns
    -------
    dict
        The parsed report, or an empty dict when cloc printed "Nothing to count." or nothing at all.
    """
    return json.loads(text) if text.lstrip().startswith("{") else {}


def classify_path(path: str, test_pattern: re.Pattern[str], docs_pattern: re.Pattern[str]) -> str:
    """Return the file group of a changed file: "docs", "test" or "source".

    Parameters
    ----------
    path : str
        Path of the file relative to the repository root.
    test_pattern : re.Pattern[str]
        A path that matches this pattern (``re.search``) is a test file.
    docs_pattern : re.Pattern[str]
        A path that matches this pattern (``re.search``) is a docs file, even if it also matches ``test_pattern``.

    Returns
    -------
    str
        The file group.
    """
    # Docs win, so an example script such as doc/examples/test_plate.py counts as docs.
    if docs_pattern.search(path) is not None:
        return "docs"
    if test_pattern.search(path) is not None:
        return "test"
    return "source"


def tally_changes(report: dict, test_pattern: re.Pattern[str], docs_pattern: re.Pattern[str]) -> Tally:
    """Sum the changed lines of a cloc by-file diff report into the table rows.

    Parameters
    ----------
    report : dict
        Parsed JSON of a ``cloc --diff --by-file --json`` report.
    test_pattern : re.Pattern[str]
        A path that matches this pattern (``re.search``) is a test file.
    docs_pattern : re.Pattern[str]
        A path that matches this pattern (``re.search``) is a docs file. Any file that is neither is a source file.

    Returns
    -------
    Tally
        Maps each row label of `ROW_LABELS`, in table order, to its line counts for each change type.
    """
    tally = {label: dict.fromkeys(CHANGE_TYPES, 0) for label in ROW_LABELS.values()}
    for change_type in CHANGE_TYPES:
        for path, counts in report.get(change_type, {}).items():
            group = classify_path(path, test_pattern, docs_pattern)
            for line_type in LINE_TYPES:
                tally[ROW_LABELS[(group, line_type)]][change_type] += counts.get(line_type, 0)
    return tally


def format_row(label: str, counts: dict[str, int]) -> str:
    """Format one Markdown table row of added, modified, removed and net line counts.

    Parameters
    ----------
    label : str
        Text of the first column.
    counts : dict[str, int]
        Line count for each change type.

    Returns
    -------
    str
        The Markdown table row.
    """
    net = counts["added"] - counts["removed"]
    cells = [f"+{counts['added']}", str(counts["modified"]), f"-{counts['removed']}", f"{net:+d}"]
    return f"| {label} | " + " | ".join(cells) + " |"


def render_markdown(tally: Tally, base: str, head: str, test_regex: str, docs_regex: str) -> str:
    """Render the tallied line changes as a Markdown comment body.

    Parameters
    ----------
    tally : Tally
        Output of `tally_changes`.
    base : str
        Commit the changes are measured from.
    head : str
        Commit the changes are measured to.
    test_regex : str
        Pattern that picks out the test files, quoted in the footnote.
    docs_regex : str
        Pattern that picks out the docs files, quoted in the footnote.

    Returns
    -------
    str
        The Markdown text.
    """
    total = {change_type: sum(counts[change_type] for counts in tally.values()) for change_type in CHANGE_TYPES}
    lines = [
        "### Line changes by type",
        "",
        "| | Added | Modified | Removed | Net |",
        "| :-- | --: | --: | --: | --: |",
        *(format_row(label, counts) for label, counts in tally.items()),
        format_row("**Total**", total),
        "",
        f"<sub>Counted by [cloc](https://github.com/AlDanial/cloc) from `{base[:10]}` (merge base) to "
        f"`{head[:10]}`. Blank lines and files in languages cloc does not know are not counted. "
        "GitHub counts a modified line as one addition and one deletion. "
        f"Docs files are paths that match `{docs_regex}`, and the Docs row holds both their code and comment "
        f"lines. Test files are other paths that match `{test_regex}`.</sub>",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    """Read a cloc diff report and print the Markdown summary to stdout."""
    parser = argparse.ArgumentParser(description="Summarise a cloc diff report as a Markdown table of line changes.")
    parser.add_argument("report", type=Path, help="JSON from cloc --git-diff-rel --by-file --json")
    parser.add_argument("--base", required=True, help="Commit the diff starts from")
    parser.add_argument("--head", required=True, help="Commit the diff ends at")
    parser.add_argument("--test-regex", default="", help="Paths that match are test files. Empty uses the default")
    parser.add_argument("--docs-regex", default="", help="Paths that match are docs files. Empty uses the default")
    args = parser.parse_args()

    test_regex = args.test_regex if len(args.test_regex) > 0 else DEFAULT_TEST_REGEX
    docs_regex = args.docs_regex if len(args.docs_regex) > 0 else DEFAULT_DOCS_REGEX
    report = parse_report(args.report.read_text())
    tally = tally_changes(report, re.compile(test_regex), re.compile(docs_regex))
    sys.stdout.write(render_markdown(tally, args.base, args.head, test_regex, docs_regex))


if __name__ == "__main__":
    main()
