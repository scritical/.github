"""Print the pull requests that the Depends-On lines of this pull request's description name."""

# Future modules
from __future__ import annotations

# Standard Python modules
import json
import os
import re
import sys
import urllib.error
import urllib.request

_NAME = r"[A-Za-z0-9_.-]+"
_SHORTHAND_PULL_REQUEST = re.compile(rf"({_NAME})/({_NAME})#(\d+)")
_URL_PULL_REQUEST = re.compile(rf"https://github\.com/({_NAME})/({_NAME})/pull/(\d+)/?")
_DEPENDS_ON_LINE = re.compile(r"[ \t]*(?:[-*][ \t]+)?depends-on:[ \t]*(\S+)[ \t]*", re.IGNORECASE)
# Anything a reader could take for a Depends-On line: a bullet, heading, quote or bold marker,
# "Depends on" or "Depends_On", or a space before the colon
_LOOKS_LIKE_DEPENDS_ON = re.compile(r"[\s>#*+-]*(?:\d+[.)]\s*)?\**\s*depends[\s_-]*on\s*\**\s*:", re.IGNORECASE)
_HTML_COMMENT = re.compile(r"<!--.*?(?:-->|\Z)", re.DOTALL)
_FENCE = re.compile(r" {0,3}(`{3,}|~{3,})")
_API_URL = os.environ.get("GITHUB_API_URL", "https://api.github.com")
_ACCEPT_HEADER = "application/vnd.github+json"
_TIMEOUT_SECONDS = 30
_EXPECTED_FORM = (
    "Write it as 'Depends-On: OWNER/REPO#N' or 'Depends-On: https://github.com/OWNER/REPO/pull/N', alone on its line"
)


class DependsOnError(Exception):
    """A Depends-On line that does not name one pull request."""


def parse_depends_on(body: str) -> list[str]:
    """Return the pull requests that the Depends-On lines of a description name.

    Lines inside HTML comments and fenced code blocks are skipped, since the rendered page does not show them as text.

    Parameters
    ----------
    body : str
        Pull request description, as Markdown.

    Returns
    -------
    list of str
        ``owner/repo#N`` in lower case, in order, without repeats.

    Raises
    ------
    DependsOnError
        If a line looks like a Depends-On line but does not name exactly one pull request.
    """
    references: list[str] = []
    for line in _visible_lines(body):
        if not _LOOKS_LIKE_DEPENDS_ON.match(line):
            continue
        reference = _parse_line(line)
        if reference not in references:
            references.append(reference)
    return references


def _visible_lines(body: str) -> list[str]:
    """Return the lines of *body* outside HTML comments and fenced code blocks."""
    lines = []
    fence = None
    for line in _HTML_COMMENT.sub("", body).splitlines():
        match = _FENCE.match(line)
        if fence is None and match:
            fence = match[1]
        elif fence is not None:
            closing = match is not None and match[1][0] == fence[0] and len(match[1]) >= len(fence)
            if closing and not line[match.end() :].strip():
                fence = None
        else:
            lines.append(line)
    return lines


def _parse_line(line: str) -> str:
    """Return the ``owner/repo#N`` that a Depends-On line names, in lower case."""
    line_match = _DEPENDS_ON_LINE.fullmatch(line)
    reference = line_match and (
        _SHORTHAND_PULL_REQUEST.fullmatch(line_match[1]) or _URL_PULL_REQUEST.fullmatch(line_match[1])
    )
    if not reference:
        raise DependsOnError(f"Cannot read {line.strip()!r}. {_EXPECTED_FORM}.")
    owner, repo, number = reference.groups()
    return f"{owner}/{repo}#{int(number)}".lower()


def _read_description(event: dict, repository: str, token: str) -> str:
    """Return the description of the event's pull request.

    Parameters
    ----------
    event : dict
        Webhook payload of the workflow run.
    repository : str
        ``owner/repo`` the workflow runs in.
    token : str
        Token that can read the repository's pull requests. When empty, the description comes from *event*, which a
        re-run reuses; otherwise it is read through the API, so a re-run sees an edited description.

    Returns
    -------
    str
        The description, empty when it has none.

    Raises
    ------
    DependsOnError
        If the API request fails.
    """
    pull_request = event["pull_request"]
    if token:
        url = f"{_API_URL}/repos/{repository}/pulls/{pull_request['number']}"
        request = urllib.request.Request(url, headers={"Accept": _ACCEPT_HEADER, "Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
                pull_request = json.load(response)
        except urllib.error.URLError as error:
            raise DependsOnError(f"Cannot read the description of {url}: {error}") from error
    return pull_request["body"] or ""


def main() -> int:
    """Print the Depends-On references of the workflow's pull request, one per line.

    Reads ``GITHUB_EVENT_PATH``, ``GITHUB_REPOSITORY`` and the optional ``DEPENDS_ON_TOKEN`` from the environment.
    Prints nothing for an event without a pull request.

    Returns
    -------
    int
        0 on success, 1 when the description cannot be read or a line cannot be parsed.
    """
    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as event_file:
        event = json.load(event_file)
    if "pull_request" not in event:
        return 0
    try:
        body = _read_description(event, os.environ["GITHUB_REPOSITORY"], os.environ.get("DEPENDS_ON_TOKEN", ""))
        references = parse_depends_on(body)
    except DependsOnError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1
    for reference in references:
        print(reference)
    return 0


if __name__ == "__main__":
    sys.exit(main())
