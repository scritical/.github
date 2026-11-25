"""Print the pull requests that the Depends-On lines of this pull request's description name."""

# Future modules
from __future__ import annotations

# Standard Python modules
import http.client
import json
import os
import re
import sys
import urllib.request

_OWNER_OR_REPOSITORY = r"[A-Za-z0-9_.-]+"
_SHORTHAND_PULL_REQUEST = re.compile(rf"({_OWNER_OR_REPOSITORY})/({_OWNER_OR_REPOSITORY})#(\d+)")
_URL_PULL_REQUEST = re.compile(rf"https://github\.com/({_OWNER_OR_REPOSITORY})/({_OWNER_OR_REPOSITORY})/pull/(\d+)/?")
_DEPENDS_ON_LINE = re.compile(r" {0,3}(?:[-*][ \t]+)?depends-on:[ \t]*(\S+)[ \t]*", re.IGNORECASE)
# Anything a reader could take for a Depends-On line: a bullet, task box, heading, quote, bold or italic marker,
# "Depends on", "Depends_On" or another dash, or a space before the colon
_LOOKS_LIKE_DEPENDS_ON = re.compile(
    r"[\s>#*+-]*(?:\[[ xX]\]\s*)?(?:\d+[.)]\s*)?[*_]*\s*depends[\s_‐-―-]*on\s*[*_]*\s*:", re.IGNORECASE
)
_COMMENT_BLOCK_START = re.compile(r" {0,3}<!--")
_CLOSED_COMMENT = re.compile(r"<!--.*?-->")
_FENCE = re.compile(r" {0,3}(`{3,}(?=[^`]*$)|~{3,})")
_DEFAULT_API_URL = "https://api.github.com"
_ACCEPT_HEADER = "application/vnd.github+json"
_TIMEOUT_SECONDS = 30
_EXPECTED_FORM = (
    "Write it as 'Depends-On: OWNER/REPO#N' or 'Depends-On: https://github.com/OWNER/REPO/pull/N', alone on its line"
)


class DependsOnError(Exception):
    """The Depends-On references cannot be found: a line is malformed, or the description cannot be read."""


def parse_depends_on(description: str) -> list[str]:
    """Return the pull requests that the Depends-On lines of a description name.

    Lines inside HTML comments and fenced code blocks are skipped.

    Parameters
    ----------
    description : str
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
    for line in _visible_lines(description):
        if not _LOOKS_LIKE_DEPENDS_ON.match(line):
            continue
        reference = _parse_line(line)
        if reference not in references:
            references.append(reference)
    return references


def _visible_lines(description: str) -> list[str]:
    """Return the lines of a description that the pull request page shows as text.

    Parameters
    ----------
    description : str
        Pull request description, as Markdown.

    Returns
    -------
    list of str
        The lines outside fenced code blocks and HTML comment blocks, with closed inline comments removed.
    """
    lines: list[str] = []
    fence = None
    in_comment = False
    for line in description.splitlines():
        if in_comment:
            in_comment = "-->" not in line
        elif fence is not None:
            match = _FENCE.match(line)
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not line[match.end() :].strip():
                fence = None
        elif match := _FENCE.match(line):
            fence = match[1]
        elif _COMMENT_BLOCK_START.match(line):
            in_comment = "-->" not in line[line.index("<!--") + 2 :]
        else:
            lines.append(_CLOSED_COMMENT.sub("", line))
    return lines


def _parse_line(line: str) -> str:
    """Return the pull request that a Depends-On line names.

    Parameters
    ----------
    line : str
        A line that looks like a Depends-On line.

    Returns
    -------
    str
        ``owner/repo#N`` in lower case.

    Raises
    ------
    DependsOnError
        If the line is not a Depends-On line followed by one pull request alone.
    """
    depends_on_match = _DEPENDS_ON_LINE.fullmatch(line)
    pull_request_match = depends_on_match and (
        _SHORTHAND_PULL_REQUEST.fullmatch(depends_on_match[1]) or _URL_PULL_REQUEST.fullmatch(depends_on_match[1])
    )
    if not pull_request_match:
        raise DependsOnError(f"Cannot read {line.strip()!r}. {_EXPECTED_FORM}.")
    owner, repo, number = pull_request_match.groups()
    return f"{owner}/{repo}#{int(number)}".lower()


def _description_from_api(url: str, token: str) -> str:
    """Return the description of a pull request, read through the GitHub REST API.

    Parameters
    ----------
    url : str
        API URL of the pull request.
    token : str
        Token that can read the repository's pull requests.

    Returns
    -------
    str
        The description, empty when it has none.

    Raises
    ------
    DependsOnError
        If the request fails or the reply is not JSON.
    """
    request = urllib.request.Request(url, headers={"Accept": _ACCEPT_HEADER, "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            return json.load(response)["body"] or ""
    except (OSError, http.client.HTTPException, ValueError) as error:
        raise DependsOnError(f"Cannot read the description of {url}: {error}") from error


def main() -> int:
    """Print the Depends-On references of the workflow's pull request, one per line.

    Reads ``GITHUB_EVENT_PATH``, ``GITHUB_REPOSITORY``, ``GITHUB_API_URL`` and the optional ``DEPENDS_ON_TOKEN`` from
    the environment. Without a token, the description comes from the event payload; with one, from the API.
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
    pull_request = event["pull_request"]
    token = os.environ.get("DEPENDS_ON_TOKEN", "")
    try:
        if token:
            api_url = os.environ.get("GITHUB_API_URL", _DEFAULT_API_URL)
            repository = os.environ["GITHUB_REPOSITORY"]
            description = _description_from_api(f"{api_url}/repos/{repository}/pulls/{pull_request['number']}", token)
        else:
            description = pull_request["body"] or ""
        references = parse_depends_on(description)
    except DependsOnError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1
    for reference in references:
        print(reference)
    return 0


if __name__ == "__main__":
    sys.exit(main())
