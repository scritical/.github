"""Tests for the image selection of the docker-setup action, with docker replaced by a stub."""

# Future modules
from __future__ import annotations

# Standard Python modules
import pathlib

# External modules
from helpers import select_image
import pytest

PUBLISHED_IMAGE = "scritical/private-dev:u24-gcc-ompi-latest"


@pytest.mark.parametrize(
    "pull_requests",
    ["", "scritical/sr-pygeo#44\n", "someone/docker#5\n", "xscritical/docker#5\n", "scritical/docker#5x\n"],
)
def test_published_image_without_a_docker_reference(tmp_path: pathlib.Path, pull_requests: str) -> None:
    result = select_image(tmp_path, pull_requests)
    assert (result.returncode, result.stdout, result.stderr) == (0, PUBLISHED_IMAGE + "\n", "")
    assert not (tmp_path / "docker.log").exists()


@pytest.mark.parametrize(("arch", "platform"), [("X64", "amd64"), ("ARM64", "arm64v8")])
def test_docker_reference_selects_that_pull_requests_image(tmp_path: pathlib.Path, arch: str, platform: str) -> None:
    result = select_image(tmp_path, "scritical/sr-pygeo#44\nscritical/docker#133\n", arch=arch)
    image = f"{PUBLISHED_IMAGE}-pr133-{platform}"
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
    assert f"Cannot read image {PUBLISHED_IMAGE}-pr133-amd64: toomanyrequests: rate limit" in result.stderr
    assert "If its image build failed, fix that docker PR." in result.stderr
