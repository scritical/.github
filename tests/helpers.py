"""Helpers that run the action scripts the way a workflow does."""

# Future modules
from __future__ import annotations

# Standard Python modules
import io
import json
import os
import pathlib
import subprocess

# External modules
import depends_on
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DEPENDS_ON_SCRIPT = REPO_ROOT / ".github" / "actions" / "depends-on" / "depends_on.py"
SELECT_IMAGE_SCRIPT = REPO_ROOT / ".github" / "actions" / "docker-setup" / "select_image.sh"


def write_event(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path, event: dict, token: str = "") -> None:
    """Set the environment a workflow step gives depends_on.py, with *event* as the payload.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Fixture that sets the environment.
    tmp_path : pathlib.Path
        Directory for the payload file.
    event : dict
        Webhook payload.
    token : str, optional
        Value of ``DEPENDS_ON_TOKEN``.
    """
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_REPOSITORY", "scritical/docker")
    monkeypatch.setenv("DEPENDS_ON_TOKEN", token)


def run_event(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path, event: dict, token: str = ""
) -> tuple[int, list[str]]:
    """Run depends_on.main with *event* as the payload.

    Returns
    -------
    tuple of int and list of str
        The exit code and the printed lines.
    """
    write_event(monkeypatch, tmp_path, event, token)
    output = io.StringIO()
    monkeypatch.setattr("sys.stdout", output)
    return depends_on.main(), output.getvalue().splitlines()


def run_main(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path, description: str | None, token: str = ""
) -> tuple[int, list[str]]:
    """Run depends_on.main for a pull request event whose payload holds *description*.

    Returns
    -------
    tuple of int and list of str
        The exit code and the printed lines.
    """
    return run_event(monkeypatch, tmp_path, {"pull_request": {"number": 7, "body": description}}, token)


def select_image(
    tmp_path: pathlib.Path, pull_requests: str, arch: str = "X64", docker_error: str = ""
) -> subprocess.CompletedProcess[str]:
    """Run select_image.sh with *pull_requests* on stdin and docker replaced by a stub.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Directory for the stub, which logs its arguments to ``docker.log`` there.
    pull_requests : str
        Depends-On references, one per line.
    arch : str, optional
        Value of ``RUNNER_ARCH``.
    docker_error : str, optional
        When set, the stub prints it and fails.

    Returns
    -------
    subprocess.CompletedProcess of str
        The finished script.
    """
    failure = f'echo "{docker_error}" >&2\nexit 1\n' if docker_error else ""
    stub = tmp_path / "docker"
    stub.write_text(f'#!/usr/bin/env bash\necho "$@" >> "{tmp_path}/docker.log"\n{failure}')
    stub.chmod(0o755)
    env = {
        "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        "DOCKER_TAG": "u24-gcc-ompi-latest",
        "RUNNER_ARCH": arch,
    }
    return subprocess.run(
        [str(SELECT_IMAGE_SCRIPT)], input=pull_requests, env=env, capture_output=True, text=True, check=False
    )
