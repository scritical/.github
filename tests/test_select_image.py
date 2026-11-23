"""Tests for the image selection of the docker-setup action, with docker replaced by a stub."""

# Future modules
from __future__ import annotations

# Standard Python modules
import os
import pathlib
import subprocess

# External modules
import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / ".github" / "actions" / "docker-setup" / "select_image.sh"
PUBLISHED = "scritical/private-dev:u24-gcc-ompi-latest"


def select_image(
    tmp_path: pathlib.Path, refs: str, arch: str = "X64", docker_error: str = ""
) -> subprocess.CompletedProcess[str]:
    """Run select_image.sh with *refs* on stdin and a docker stub that fails with *docker_error* when it is set."""
    stub = tmp_path / "docker"
    stub.write_text(f'#!/usr/bin/env bash\necho "$@" >> "{tmp_path}/docker.log"\n')
    if docker_error:
        stub.write_text(stub.read_text() + f'echo "{docker_error}" >&2\nexit 1\n')
    stub.chmod(0o755)
    env = {
        "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        "DOCKER_TAG": "u24-gcc-ompi-latest",
        "RUNNER_ARCH": arch,
    }
    return subprocess.run([str(SCRIPT)], input=refs, env=env, capture_output=True, text=True, check=False)


@pytest.mark.parametrize("refs", ["", "\n", "scritical/sr-pygeo#44\n", "someone/docker#5\n"])
def test_published_image_without_a_docker_reference(tmp_path: pathlib.Path, refs: str) -> None:
    result = select_image(tmp_path, refs)
    assert (result.returncode, result.stdout, result.stderr) == (0, PUBLISHED + "\n", "")
    assert not (tmp_path / "docker.log").exists()


@pytest.mark.parametrize(("arch", "platform"), [("X64", "amd64"), ("ARM64", "arm64v8")])
def test_docker_reference_selects_that_pull_requests_image(tmp_path: pathlib.Path, arch: str, platform: str) -> None:
    result = select_image(tmp_path, "scritical/sr-pygeo#44\nscritical/docker#133\n", arch=arch)
    image = f"{PUBLISHED}-pr133-{platform}"
    assert (result.returncode, result.stdout) == (0, image + "\n")
    assert result.stderr.startswith(f"::warning::This job runs on the image of scritical/docker#133 ({image})")
    assert (tmp_path / "docker.log").read_text() == f"manifest inspect {image}\n"


def test_two_docker_references_are_an_error(tmp_path: pathlib.Path) -> None:
    result = select_image(tmp_path, "scritical/docker#133\nscritical/docker#140\n")
    assert result.returncode == 1
    assert "several docker PRs: #133 #140" in result.stderr


def test_runner_without_docker_pr_images_is_an_error(tmp_path: pathlib.Path) -> None:
    result = select_image(tmp_path, "scritical/docker#133\n", arch="ARM")
    assert result.returncode == 1
    assert "not for ARM" in result.stderr


def test_unreadable_image_reports_the_docker_error(tmp_path: pathlib.Path) -> None:
    result = select_image(tmp_path, "scritical/docker#133\n", docker_error="toomanyrequests: rate limit")
    assert (result.returncode, result.stdout) == (1, "")
    assert f"Cannot read image {PUBLISHED}-pr133-amd64: toomanyrequests: rate limit" in result.stderr
