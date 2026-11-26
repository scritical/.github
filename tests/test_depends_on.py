"""Tests for the Depends-On parser of the depends-on action."""

# Future modules
from __future__ import annotations

# Standard Python modules
import http.client
import io
import json
import os
import pathlib
import subprocess
import sys
import urllib.error

# External modules
import depends_on
from helpers import DEPENDS_ON_SCRIPT, run_event, run_main, write_event
import pytest


@pytest.mark.parametrize(
    ("line", "reference"),
    [
        ("Depends-On: scritical/sr-foilgen#28", "scritical/sr-foilgen#28"),
        ("depends-on:scritical/sr-foilgen#28  ", "scritical/sr-foilgen#28"),
        ("  Depends-On: scritical/sr-foilgen#28", "scritical/sr-foilgen#28"),
        ("- Depends-On: scritical/sr-foilgen#28", "scritical/sr-foilgen#28"),
        ("* Depends-On: scritical/sr-foilgen#28", "scritical/sr-foilgen#28"),
        ("Depends-On: https://github.com/scritical/sr-foilgen/pull/28", "scritical/sr-foilgen#28"),
        ("Depends-On: https://github.com/scritical/sr-foilgen/pull/28/", "scritical/sr-foilgen#28"),
        ("Depends-On: OpenMDAO/mphys#196", "openmdao/mphys#196"),
        ("Depends-On: scritical/docker#0133", "scritical/docker#133"),
    ],
)
def test_accepted_line(line: str, reference: str) -> None:
    assert depends_on.parse_depends_on(f"Intro.\r\n{line}\r\n") == [reference]


@pytest.mark.parametrize(
    "line",
    [
        "Depends-On:",
        "Depends-On: sr-foilgen#28",
        "Depends-On: scritical/sr-foilgen#",
        "Depends-On: scritical/sr-foilgen#13x",
        "Depends-On: scritical/sr-foilgen#28.",
        "Depends-On: (scritical/sr-foilgen#28)",
        "Depends-On: scritical/sr-foilgen#28 (splinetoolbox fix)",
        "Depends-On: scritical/sr-foilgen#28 scritical/sr-pygeo#44",
        "Depends-On: https://github.com/scritical/sr-foilgen/pull/28/files",
        "Depends-On: http://github.com/scritical/sr-foilgen/pull/28",
        "Depends-On: https://www.github.com/scritical/sr-foilgen/pull/28",
        "+ Depends-On: scritical/sr-foilgen#28",
        "1. Depends-On: scritical/sr-foilgen#28",
        "- [ ] Depends-On: scritical/sr-foilgen#28",
        "**Depends-On:** scritical/sr-foilgen#28",
        "**Depends-On**: scritical/sr-foilgen#28",
        "_Depends-On:_ scritical/sr-foilgen#28",
        "### Depends-On: scritical/sr-foilgen#28",
        "> Depends-On: scritical/sr-foilgen#28",
        "Depends on: scritical/sr-foilgen#28",
        "Depends_On: scritical/sr-foilgen#28",
        "Depends‑On: scritical/sr-foilgen#28",
        "Depends–On: scritical/sr-foilgen#28",
        "Depends-On : scritical/sr-foilgen#28",
        "    Depends-On: scritical/sr-foilgen#28",
        "\tDepends-On: scritical/sr-foilgen#28",
        "Depends-On scritical/sr-foilgen#28",
        "Depends on https://github.com/scritical/sr-foilgen/pull/28",
    ],
)
def test_malformed_line_is_an_error(line: str) -> None:
    with pytest.raises(depends_on.DependsOnError, match="Depends-On: OWNER/REPO#N"):
        depends_on.parse_depends_on(f"{line}\nscritical/sr-pygeo#44\n")


@pytest.mark.parametrize(
    "description",
    [
        "",
        "This change depends on: the lock refactor\n",
        "Needed by scritical/sr-foilgen#28.\n",
        "### Depends on\n",
        "**Depends on the A4 fix**\n",
    ],
)
def test_description_without_a_depends_on_line(description: str) -> None:
    assert depends_on.parse_depends_on(description) == []


def test_references_keep_their_order_without_repeats() -> None:
    description = (
        "Depends-On: scritical/sr-pygeo#44\n"
        "Depends-On: scritical/sr-foilgen#28\n"
        "Depends-On: https://github.com/Scritical/SR-pygeo/pull/44\n"
    )
    assert depends_on.parse_depends_on(description) == ["scritical/sr-pygeo#44", "scritical/sr-foilgen#28"]


@pytest.mark.parametrize(
    "hidden",
    [
        "<!-- Depends-On: scritical/docker#133 -->",
        "<!--\nDepends-On: scritical/docker#133\n-->",
        "<!-- unclosed\nDepends-On: scritical/docker#133",
        "<!-- Depends-On: (example) -->",
        "```\nDepends-On: scritical/docker#133\n```",
        "```\nDepends-On: scritical/docker#133",
        "~~~~text\nDepends-On: scritical/docker#133\n~~~\nDepends-On: not closed by a shorter fence\n~~~~",
        "```\n~~~\nDepends-On: not closed by the other fence character\n```",
        "```\n``` text\nDepends-On: not closed by a fence with text after it\n```",
        "Text <!--\nDepends-On: scritical/docker#133\n-->",
        "Text <!-- note\nDepends-On: scritical/docker#133\nend --> more text",
        "Text <!--\nnote --> Depends-On: scritical/docker#133",
        "Text <!-- a\nb --> c <!--\nDepends-On: scritical/docker#133\n-->",
    ],
)
def test_lines_the_page_does_not_show_are_skipped(hidden: str) -> None:
    description = f"## Purpose\nAdds X.\n{hidden}\n"
    assert depends_on.parse_depends_on(description) == []


@pytest.mark.parametrize(
    "before",
    [
        "<!-- note -->\n```\ncode\n```",
        "An HTML comment starts with `<!--`.",
        "```html\n<!--\n```",
        "Lines after <!-- are not hidden.",
        "<!-->",
        "<!--->",
        "```x``` is inline code.",
        "``` a`b",
        "    ```",
    ],
)
def test_line_the_page_shows_is_read(before: str) -> None:
    description = f"{before}\nDepends-On: scritical/docker#133\n"
    assert depends_on.parse_depends_on(description) == ["scritical/docker#133"]


@pytest.mark.parametrize(
    "description",
    [
        "Text <!--\n\nDepends-On: scritical/docker#133\n-->",
        "Text <!--\n```\n```\nDepends-On: scritical/docker#133\n-->",
        "Use `<!--` to start a comment.\nDepends-On: scritical/docker#133\n-->",
        "Text <!--\nnote -->\nDepends-On: scritical/docker#133",
    ],
)
def test_inline_comment_hides_only_lines_up_to_its_end_within_the_paragraph(description: str) -> None:
    assert depends_on.parse_depends_on(description) == ["scritical/docker#133"]


@pytest.mark.parametrize(
    "description",
    [
        "<!-- PRs this needs --> Depends-On: scritical/docker#133",
        "<!--\nnote\n--> Depends-On: scritical/docker#133",
        "<!-- a --> <!-- b -->Depends-On: scritical/docker#133",
    ],
)
def test_text_after_a_comment_block_is_read(description: str) -> None:
    assert depends_on.parse_depends_on(description) == ["scritical/docker#133"]


def test_error_quotes_the_indent_of_the_line() -> None:
    with pytest.raises(depends_on.DependsOnError, match="'    - Depends-On: .*indented by at most 3 spaces"):
        depends_on.parse_depends_on("- Dependencies\n    - Depends-On: scritical/docker#133\n")


def test_event_without_a_pull_request_prints_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    assert run_event(monkeypatch, tmp_path, {"ref": "refs/heads/main"}) == (0, [])


def test_pull_request_without_a_description(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    assert run_main(monkeypatch, tmp_path, None) == (0, [])


def test_description_is_read_from_the_payload_without_a_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("no API request without a token")

    monkeypatch.setattr(depends_on.urllib.request, "urlopen", fail)
    description = "Depends-On: scritical/sr-pygeo#44\nDepends-On: scritical/docker#5"
    assert run_main(monkeypatch, tmp_path, description) == (0, ["scritical/sr-pygeo#44", "scritical/docker#5"])


def test_description_is_read_through_the_api_with_a_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    requests = []

    def urlopen(request: urllib.request.Request, timeout: float) -> io.BytesIO:
        requests.append((request, timeout))
        return io.BytesIO(json.dumps({"body": "Depends-On: scritical/sr-pygeo#44"}).encode())

    monkeypatch.setattr(depends_on.urllib.request, "urlopen", urlopen)
    monkeypatch.setenv("GITHUB_API_URL", "https://github.example/api/v3")
    assert run_main(monkeypatch, tmp_path, "an old description", token="secret") == (0, ["scritical/sr-pygeo#44"])
    request, timeout = requests[0]
    assert request.full_url == "https://github.example/api/v3/repos/scritical/docker/pulls/7"
    assert request.get_header("Authorization") == "Bearer secret"
    assert request.get_header("Accept") == "application/vnd.github+json"
    assert timeout == 30


@pytest.mark.parametrize(
    "failure",
    [
        urllib.error.URLError("rate limited"),
        TimeoutError("The read operation timed out"),
        http.client.RemoteDisconnected("Remote end closed connection without response"),
        None,
    ],
)
def test_failed_api_request_is_an_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    failure: Exception | None,
) -> None:
    def urlopen(request: object, timeout: float) -> io.BytesIO:
        if failure is not None:
            raise failure
        return io.BytesIO(b"<html>Unicorn!</html>")

    monkeypatch.setattr(depends_on.urllib.request, "urlopen", urlopen)
    assert run_main(monkeypatch, tmp_path, "", token="secret") == (1, [])
    assert "::error::Cannot read the description" in capsys.readouterr().err


def test_malformed_line_fails_main(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_main(monkeypatch, tmp_path, "Depends-On: scritical/docker#133.") == (1, [])
    assert "::error::Cannot read 'Depends-On: scritical/docker#133.'" in capsys.readouterr().err


def test_script_exits_with_one_on_a_malformed_line(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    write_event(monkeypatch, tmp_path, {"pull_request": {"number": 7, "body": "Depends-On: scritical/docker#133."}})
    result = subprocess.run(
        [sys.executable, str(DEPENDS_ON_SCRIPT)], env=dict(os.environ), capture_output=True, text=True, check=False
    )
    assert (result.returncode, result.stdout) == (1, "")
    assert result.stderr.startswith("::error::Cannot read")
