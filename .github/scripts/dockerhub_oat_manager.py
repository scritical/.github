from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def require_env(name: str) -> str:
    """Fetch a required environment variable.

    Parameters
    ----------
    name : str
        Environment variable name to read.

    Returns
    -------
    str
        Value of the environment variable.

    Raises
    ------
    RuntimeError
        If the environment variable is missing or empty.
    """
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def write_github_env(key: str, value: str) -> None:
    """Append a key/value pair to the GitHub Actions environment file.

    Parameters
    ----------
    key : str
        Environment variable name to export.
    value : str
        Environment variable value to export.
    """
    env_path = require_env("GITHUB_ENV")
    with open(env_path, "a", encoding="utf-8") as handle:
        handle.write(f"{key}={value}\n")


def mask_value(value: str) -> None:
    """Mask a sensitive value in GitHub Actions logs.

    Parameters
    ----------
    value : str
        Sensitive value to mask.
    """
    if value:
        print(f"::add-mask::{value}")


def request_json(method: str, url: str, payload: dict | None, headers: dict) -> dict:
    """Send an HTTP request and parse the JSON response.

    Parameters
    ----------
    method : str
        HTTP method (GET, POST, DELETE, etc.).
    url : str
        Target URL.
    payload : dict | None
        JSON payload to send or None for no body.
    headers : dict
        HTTP headers to include.

    Returns
    -------
    dict
        Parsed JSON response payload.

    Raises
    ------
    RuntimeError
        If the HTTP request fails.
    """
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers = {**headers, "Content-Type": "application/json"}
    req = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(req) as response:
            data = response.read().decode("utf-8")
    except HTTPError as exc:
        raise RuntimeError(
            f"Docker Hub API request failed: {exc.code} {exc.reason}"
        ) from exc
    return json.loads(data) if data else {}


def request_no_body(method: str, url: str, headers: dict) -> None:
    """Send an HTTP request without a request body.

    Parameters
    ----------
    method : str
        HTTP method (GET, POST, DELETE, etc.).
    url : str
        Target URL.
    headers : dict
        HTTP headers to include.

    Raises
    ------
    RuntimeError
        If the HTTP request fails.
    """
    req = Request(url, headers=headers, method=method)
    try:
        with urlopen(req) as response:
            response.read()
    except HTTPError as exc:
        raise RuntimeError(
            f"Docker Hub API request failed: {exc.code} {exc.reason}"
        ) from exc


def create_oat() -> None:
    """Create a Docker Hub organization access token and export it.

    Raises
    ------
    RuntimeError
        If authentication fails or the token cannot be created.
    """
    username = require_env("DOCKERHUB_USERNAME")
    password = require_env("DOCKERHUB_PASSWORD")
    org = require_env("DOCKERHUB_ORG")
    run_id = require_env("GITHUB_RUN_ID")

    # Mask credential values early to prevent accidental disclosure in logs.
    mask_value(username)
    mask_value(password)

    # Authenticate with Docker Hub to obtain a short-lived bearer token.
    auth_payload = {"identifier": username, "secret": password}
    auth_response = request_json(
        "POST",
        "https://hub.docker.com/v2/auth/token",
        auth_payload,
        {},
    )
    access_token = auth_response.get("access_token")
    if not access_token:
        raise RuntimeError("Docker Hub auth response missing access_token")
    mask_value(access_token)
    write_github_env("DOCKERHUB_BEARER", access_token)

    # Build a scoped OAT payload with a 30-day expiration.
    expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(
        timespec="seconds"
    )
    oat_payload = {
        "label": f"gh-actions-rotate-{run_id}",
        "description": "Rotated by GitHub Actions",
        "expires_at": expires_at,
        "resources": [
            {"type": "TYPE_REPO", "path": "*/*/public", "scopes": ["repo-pull"]},
            {
                "type": "TYPE_REPO",
                "path": f"{org}/*",
                "scopes": ["repo-pull", "repo-push"],
            },
        ],
    }
    oat_response = request_json(
        "POST",
        f"https://hub.docker.com/v2/orgs/{org}/access-tokens",
        oat_payload,
        {"Authorization": f"Bearer {access_token}"},
    )
    new_oat = oat_response.get("token")
    new_oat_id = oat_response.get("id")
    if not new_oat or not new_oat_id:
        raise RuntimeError("Docker Hub OAT response missing token or id")

    # Export the token and id for later workflow steps.
    mask_value(new_oat)
    write_github_env("NEW_OAT_ID", new_oat_id)
    write_github_env("NEW_OAT", new_oat)


def revoke_oats() -> None:
    """Revoke prior rotation tokens created by this workflow.

    Raises
    ------
    RuntimeError
        If listing or deleting access tokens fails.
    """
    org = require_env("DOCKERHUB_ORG")
    bearer = require_env("DOCKERHUB_BEARER")
    keep_id = require_env("NEW_OAT_ID")

    # List recent tokens and keep only previous rotation tokens.
    headers = {"Authorization": f"Bearer {bearer}"}
    response = request_json(
        "GET",
        f"https://hub.docker.com/v2/orgs/{org}/access-tokens?page_size=100",
        None,
        headers,
    )
    results = response.get("results", [])
    old_ids = [
        item.get("id")
        for item in results
        if item.get("label", "").startswith("gh-actions-rotate-")
        and item.get("id") != keep_id
    ]

    if not old_ids:
        print("No previous tokens to revoke.")
        return

    # Delete old rotation tokens, leaving the newest token active.
    for token_id in old_ids:
        if not token_id:
            continue
        request_no_body(
            "DELETE",
            f"https://hub.docker.com/v2/orgs/{org}/access-tokens/{token_id}",
            headers,
        )
    print(f"Revoked {len(old_ids)} previous token(s).")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns
    -------
    argparse.Namespace
        Parsed arguments with action flags.
    """
    parser = argparse.ArgumentParser(
        description="Create and revoke Docker Hub organization access tokens."
    )
    parser.add_argument(
        "--create",
        action="store_true",
        help="Create a new organization access token and export it to GITHUB_ENV.",
    )
    parser.add_argument(
        "--revoke",
        action="store_true",
        help="Revoke previous organization access tokens created by this workflow.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the requested Docker Hub OAT actions.

    Returns
    -------
    int
        Process exit code.

    Raises
    ------
    RuntimeError
        If no action flags are provided.
    """
    args = parse_args()
    if not args.create and not args.revoke:
        raise RuntimeError("At least one action is required: --create or --revoke")

    if args.create:
        create_oat()
    if args.revoke:
        revoke_oats()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
