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
# "Depends on", "Depends_On" or another dash, a space before the colon, or no colon before a reference
_LOOKS_LIKE_DEPENDS_ON = re.compile(
    r"[\s>#*+-]*(?:\[[ xX]\]\s*)?(?:\d+[.)]\s*)?[*_]*\s*depends[\s_‐-―-]*on"
    r"(?:\s*[*_]*\s*:|\s+(?:[\w.-]+/[\w.-]+#\d|https?://))",
    re.IGNORECASE,
)
_COMMENT_BLOCK_START = re.compile(r" {0,3}<!--")
# Applied to one line at a time; DOTALL only satisfies CodeQL's py/bad-tag-filter
_CLOSED_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_FENCE = re.compile(r" {0,3}(`{3,}(?=[^`]*$)|~{3,})")
_CODE_SPAN = re.compile(r"(`+).+?(?<!`)\1(?!`)")
_DEFAULT_API_URL = "https://api.github.com"
_ACCEPT_HEADER = "application/vnd.github+json"
_TIMEOUT_SECONDS = 30
_EXPECTED_FORM = (
    "Write it as 'Depends-On: OWNER/REPO#N' or 'Depends-On: https://github.com/OWNER/REPO/pull/N', alone on its line"
    " and indented by at most 3 spaces"
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
        The lines outside fenced code blocks and HTML comments.
    """
    lines = description.splitlines()
    visible: list[str] = []
    fence = None
    index = 0
    while index < len(lines):
        line = lines[index]
        if fence is not None:
            fence = None if _closes_fence(line, fence) else fence
            index += 1
        elif match := _FENCE.match(line):
            fence = match[1]
            index += 1
        elif _COMMENT_BLOCK_START.match(line):
            index = _after_comment_block(lines, index)
        else:
            text, index = _paragraph_line(lines, index)
            visible.append(text)
    return visible


def _closes_fence(line: str, fence: str) -> bool:
    """Return whether *line* closes the code block that *fence* opened.

    Parameters
    ----------
    line : str
        A line inside the code block.
    fence : str
        The backticks or tildes that opened it.

    Returns
    -------
    bool
        True for a fence of the same character, at least as long, with nothing after it.
    """
    match = _FENCE.match(line)
    return bool(match) and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not line[match.end() :].strip()


def _after_comment_block(lines: list[str], index: int) -> int:
    """Return the index of the next line to read after the HTML comment block that starts at *index*.

    The block ends on the line holding ``-->``. The page shows what follows ``-->`` on that line, so that text
    replaces the line in *lines*, to be read next.

    Parameters
    ----------
    lines : list of str
        Lines of the description; the closing line may be replaced.
    index : int
        Index of the line that opens the block.

    Returns
    -------
    int
        Index of the next line to read.
    """
    # Searching from the second dash of "<!--" lets "<!-->" and "<!--->" close at once
    start = lines[index].index("<!--") + 2
    for end in range(index, len(lines)):
        closing = lines[end].find("-->", start if end == index else 0)
        if closing >= 0:
            rest = lines[end][closing + 3 :]
            if not rest.strip():
                return end + 1
            lines[end] = rest
            return end
    return len(lines)


def _paragraph_line(lines: list[str], index: int) -> tuple[str, int]:
    """Return the text the page shows for a paragraph line, joined with what follows a comment it opens.

    An inline comment may close on a later line of its paragraph. The page then shows the text before the comment
    and the text after it as one line.

    Parameters
    ----------
    lines : list of str
        Lines of the description.
    index : int
        Index of the paragraph line.

    Returns
    -------
    tuple of str and int
        The visible text, and the index of the next line to read.
    """
    text = lines[index]
    index += 1
    while True:
        text = _CLOSED_COMMENT.sub("", text)
        start = _comment_opening(text)
        end = None if start is None else _comment_closing_line(lines, index)
        if end is None:
            return text, index
        text = text[:start] + lines[end].split("-->", 1)[1]
        index = end + 1


def _comment_opening(text: str) -> int | None:
    """Return where an unclosed ``<!--`` outside inline code starts in *text*, or None.

    Parameters
    ----------
    text : str
        A paragraph line without closed comments.

    Returns
    -------
    int or None
        Index of the ``<!--``.
    """
    start = _CODE_SPAN.sub(lambda span: " " * len(span[0]), text).find("<!--")
    return None if start < 0 else start


def _comment_closing_line(lines: list[str], index: int) -> int | None:
    """Return the index of the line holding ``-->``, if it comes before the paragraph ends.

    Parameters
    ----------
    lines : list of str
        Lines of the description.
    index : int
        Index of the first line after the one that opens the comment.

    Returns
    -------
    int or None
        Index of the closing line; None when a blank line, a fence or the end of the description comes first.
    """
    for later in range(index, len(lines)):
        if not lines[later].strip() or _FENCE.match(lines[later]):
            return None
        if "-->" in lines[later]:
            return later
    return None


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
        raise DependsOnError(f"Cannot read {line.rstrip()!r}. {_EXPECTED_FORM}.")
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
