"""Tests for the Depends-On parser of the depends-on action."""

# Future modules
from __future__ import annotations

# Standard Python modules
import importlib.util
import io
import json
import pathlib
import types
import urllib.error

# External modules
import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / ".github" / "actions" / "depends-on" / "depends_on.py"


def load_depends_on() -> types.ModuleType:
    """Load depends_on.py by path, since the action directory is not a package."""
    spec = importlib.util.spec_from_file_location("depends_on", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DEPENDS_ON = load_depends_on()


@pytest.mark.parametrize(
    ("line", "reference"),
    [
        ("Depends-On: scritical/sr-foilgen#28", "scritical/sr-foilgen#28"),
        ("depends-on:scritical/sr-foilgen#28  ", "scritical/sr-foilgen#28"),
        ("- Depends-On: scritical/sr-foilgen#28", "scritical/sr-foilgen#28"),
        ("* Depends-On: scritical/sr-foilgen#28", "scritical/sr-foilgen#28"),
        ("Depends-On: https://github.com/scritical/sr-foilgen/pull/28", "scritical/sr-foilgen#28"),
        ("Depends-On: https://github.com/scritical/sr-foilgen/pull/28/", "scritical/sr-foilgen#28"),
        ("Depends-On: OpenMDAO/mphys#196", "openmdao/mphys#196"),
        ("Depends-On: scritical/docker#0133", "scritical/docker#133"),
    ],
)
def test_accepted_line(line: str, reference: str) -> None:
    assert DEPENDS_ON.parse_depends_on(f"Intro.\r\n{line}\r\n") == [reference]


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
        "**Depends-On:** scritical/sr-foilgen#28",
        "### Depends-On: scritical/sr-foilgen#28",
        "> Depends-On: scritical/sr-foilgen#28",
        "Depends on: scritical/sr-foilgen#28",
        "Depends-On : scritical/sr-foilgen#28",
    ],
)
def test_malformed_line_is_an_error(line: str) -> None:
    with pytest.raises(DEPENDS_ON.DependsOnError, match="Depends-On: OWNER/REPO#N"):
        DEPENDS_ON.parse_depends_on(f"{line}\nscritical/sr-pygeo#44\n")


@pytest.mark.parametrize(
    "body", ["", "Moves the images to splinetoolbox v15.\n", "Needed by scritical/sr-foilgen#28.\n"]
)
def test_description_without_a_depends_on_line(body: str) -> None:
    assert DEPENDS_ON.parse_depends_on(body) == []


def test_references_keep_their_order_without_repeats() -> None:
    body = (
        "Depends-On: scritical/sr-pygeo#44\n"
        "Depends-On: scritical/sr-foilgen#28\n"
        "Depends-On: https://github.com/Scritical/SR-pygeo/pull/44\n"
    )
    assert DEPENDS_ON.parse_depends_on(body) == ["scritical/sr-pygeo#44", "scritical/sr-foilgen#28"]


@pytest.mark.parametrize(
    "hidden",
    [
        "<!-- Depends-On: scritical/docker#133 -->",
        "<!--\nDepends-On: scritical/docker#133\n-->",
        "<!-- unclosed\nDepends-On: scritical/docker#133",
        "```\nDepends-On: scritical/docker#133\n```",
        "~~~~text\nDepends-On: scritical/docker#133\n~~~\nDepends-On: not closed by a shorter fence\n~~~~",
        "```\nDepends-On: scritical/docker#133",
        "<!-- Depends-On: (example) -->",
    ],
)
def test_lines_the_page_does_not_show_are_skipped(hidden: str) -> None:
    body = f"## Purpose\nAdds X.\n{hidden}\n"
    assert DEPENDS_ON.parse_depends_on(body) == []


def test_line_after_a_closed_block_is_read() -> None:
    body = "<!-- note -->\n```\ncode\n```\nDepends-On: scritical/docker#133\n"
    assert DEPENDS_ON.parse_depends_on(body) == ["scritical/docker#133"]


def run_main(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path, event: dict, token: str = ""
) -> tuple[int, list[str]]:
    """Run main with *event* as the payload and return its exit code and printed lines."""
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_REPOSITORY", "scritical/docker")
    monkeypatch.setenv("DEPENDS_ON_TOKEN", token)
    output = io.StringIO()
    monkeypatch.setattr("sys.stdout", output)
    return DEPENDS_ON.main(), output.getvalue().splitlines()


def test_event_without_a_pull_request_prints_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    assert run_main(monkeypatch, tmp_path, {"ref": "refs/heads/main"}) == (0, [])


def test_pull_request_without_a_description(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    assert run_main(monkeypatch, tmp_path, {"pull_request": {"number": 7, "body": None}}) == (0, [])


def test_description_is_read_from_the_payload_without_a_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("no API request without a token")

    monkeypatch.setattr(DEPENDS_ON.urllib.request, "urlopen", fail)
    event = {"pull_request": {"number": 7, "body": "Depends-On: scritical/sr-pygeo#44\nDepends-On: scritical/docker#5"}}
    assert run_main(monkeypatch, tmp_path, event) == (0, ["scritical/sr-pygeo#44", "scritical/docker#5"])


def test_description_is_read_through_the_api_with_a_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    requests = []

    def urlopen(request: object, timeout: float) -> io.BytesIO:
        requests.append(request)
        return io.BytesIO(json.dumps({"body": "Depends-On: scritical/sr-pygeo#44"}).encode())

    monkeypatch.setattr(DEPENDS_ON.urllib.request, "urlopen", urlopen)
    event = {"pull_request": {"number": 7, "body": "an old description"}}
    assert run_main(monkeypatch, tmp_path, event, token="secret") == (0, ["scritical/sr-pygeo#44"])
    assert requests[0].full_url.endswith("/repos/scritical/docker/pulls/7")
    assert requests[0].get_header("Authorization") == "Bearer secret"


def test_failed_api_request_is_an_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def urlopen(request: object, timeout: float) -> None:
        raise urllib.error.URLError("rate limited")

    monkeypatch.setattr(DEPENDS_ON.urllib.request, "urlopen", urlopen)
    event = {"pull_request": {"number": 7, "body": ""}}
    assert run_main(monkeypatch, tmp_path, event, token="secret") == (1, [])
    assert "::error::Cannot read the description" in capsys.readouterr().err


def test_malformed_line_fails_main(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    event = {"pull_request": {"number": 7, "body": "Depends-On: scritical/docker#133."}}
    assert run_main(monkeypatch, tmp_path, event) == (1, [])
    assert "::error::Cannot read 'Depends-On: scritical/docker#133.'" in capsys.readouterr().err
