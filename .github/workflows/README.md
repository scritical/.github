# GitHub Actions Workflows

Reusable GitHub Actions workflows for Supercritical repositories. These workflows are called from individual repositories using the `workflow_call` trigger.

## Available Workflows

| Workflow | Description |
| :------- | :---------- |
| `build.yaml` | Build and test code in Docker container |
| `build-gpu.yaml` | Build CUDA on a CPU runner and test it on a GPU runner (never a required check) |
| `build-docs.yaml` | Build documentation site in Docker container and publish it to `api-docs.scritical.com` |
| `tapenade.yaml` | Tapenade automatic differentiation checks |
| `clang_format.yaml` | C/C++ formatting checks |
| `fprettify.yaml` | Fortran 90 formatting checks |
| `ruff.yaml` | Python formatting and linting with Ruff |
| `mypy.yaml` | Python type checking with MyPy |
| `branch-name-check.yaml` | Enforce the branch prefixes: `feature-`, `bugfix-`, `hotfix-` and `doc-`, and fail a `doc-` pull request that changes a non-documentation path |
| `bump_version.yaml` | Tag merged PRs with the next version from the `[major]`, `[minor]` or `[patch]` keyword in their titles |

---

## Composite Actions

Shared composite actions used by workflows and repository CI files.

| Action | Description |
| :----- | :---------- |
| `docker-setup` | Set Docker env vars, login, and start the container |
| `docker-cleanup` | Stop and remove the container |
| `depends-on` | Output the pull requests that the `Depends-On` lines of the PR description name |

`tests/` holds the tests of the action scripts. `test-actions.yaml` runs them, and the `depends-on` action itself, on every pull request to this repository.

### docker-setup

| Name | Type | Default | Description |
| :--- | :--- | :------ | :---------- |
| `SCRITICAL_HOMEDIR` | string | `/home/scriticaluser` | Base home directory for container paths |
| `BASHRC` | string | `/home/scriticaluser/.bashrc_scritical` | Bashrc for container environment |
| `DOCKER_TAG` | string | n/a | Docker image tag to use |
| `BW_ACCESS_TOKEN` | string | n/a | Bitwarden access token |
| `DOCKER_RUN_ARGS` | string | `""` | Extra arguments for `docker run`, such as `--runtime=nvidia --gpus all` on a GPU runner |

The runner needs `bash`, `docker`, and `python3` on the host. The action reads the PR description with `python3` before it starts the container.

#### Testing a repository PR against an unmerged docker change

Repository CI runs on the published `u24-*-latest` images, which change only when docker's build on `main` publishes them.
To run a repository PR on the images of an open docker PR, put this line in the PR description:

    Depends-On: scritical/docker#123

- The job starts the container from `scritical/private-dev:<DOCKER_TAG>-pr<N>-<platform>`, for example `u24-gcc-ompi-latest-pr123-amd64`, and shows a warning that names it. The platform is `amd64` on an X64 runner and `arm64v8` on an ARM64 runner.
- The docker PR pushes this image when its image build passes, even if its regression tests fail, and keeps the tag after it merges or closes. If the job cannot read the image, it fails and prints the docker error. For a missing tag, re-run the job after the docker PR has pushed its images.
- Name one docker PR. The job fails when the description names two different docker PRs. `docker-setup` ignores references to other repositories.
- `docker-setup` reads the description from the event payload, because the caller workflows do not give their `GITHUB_TOKEN` `pull-requests: read`. A re-run reuses the old description, so after editing it, push a commit, or close and reopen the PR.
- PRs without the line, and pushes to `main`, use the published image. From the repository PR's merge until the docker PR's `main` build publishes, the repository's `main` CI runs without the docker change and can fail. Remove the line when the docker PR merges.

### depends-on

| Name | Type | Default | Description |
| :--- | :--- | :------ | :---------- |
| `token` | string | `""` | Token that can read this repository's pull requests. With it, the description is read through the API, so a re-run sees an edited description. Without it, the description comes from the event payload, which a re-run reuses. |

Output `pull-requests`: the referenced pull requests as `owner/repo#N` in lower case, one per line, without repeats. Empty outside pull requests. `docker-setup` runs the same script.

A `Depends-On` line is the reference alone, optionally as a `-` or `*` bullet:

    Depends-On: scritical/sr-foilgen#28
    - Depends-On: https://github.com/scritical/sr-foilgen/pull/28

- Letter case does not matter. Lines inside HTML comments (`<!-- -->`) and fenced code blocks are skipped, as the PR page hides them, so commenting a line out disables it.
- The job fails on a line that looks like `Depends-On` in another form, such as `**Depends-On:**`, `Depends on:`, a numbered bullet, a task-list item, a line indented as code, or a reference with text after it.

### docker-cleanup

No inputs.

---

## Workflow Options

Configuration inheritance/overrides are documented in each workflow section below.

### build.yaml

Docker-based build and test workflow using the `scritical/private-dev` image with GCC and Intel compilers.

| Name | Type | Default | Description |
| :--- | :--- | :------ | :---------- |
| `TIMEOUT` | number | `120` | Runtime allowed for the job, in minutes |
| `GCC_CONFIG` | string | `""` | Path to GCC configuration file (from repository root) |
| `INTEL_CONFIG` | string | `""` | Path to Intel configuration file (from repository root) |
| `BUILD_SCRIPT` | string | `.github/build.sh` | Path to build script. Empty string skips this step |
| `TEST_SCRIPT` | string | `.github/test.sh` | Path to test script. Empty string skips this step |

**Required Secrets:**
| Name | Description |
| :--- | :---------- |
| `BW_ACCESS_TOKEN` | Bitwarden access token |

If these secrets are configured at the organization level, callers can use `secrets: inherit` instead of listing each secret.

---

### build-gpu.yaml

Builds CUDA code on a CPU runner (the GPU runner's CPU is slow and costs about $1/h), uploads the packed build as the `cuda-build` artifact (retention 1 day), and tests it on an L4 GPU runner started with `--runtime=nvidia --gpus all`.

Jobs: `build-cuda` (CPU runner) and `test-gpu` (GPU runner, `needs: build-cuda`). GPU runners are ephemeral and can queue for hours, so `test-gpu` must never be a required check and nothing should depend on it. Pass the image tag, not the image name: a job output containing the masked DockerHub user is dropped.

| Name | Type | Default | Description |
| :--- | :--- | :------ | :---------- |
| `CONFIG_FILE` | string | n/a | Path to the build configuration file (from repository root). Passed to the build script as `CONFIG_FILE` |
| `BUILD_SCRIPT` | string | n/a | Path to the build script, which writes `BUILD_ARTIFACT` |
| `TEST_SCRIPT` | string | n/a | Path to the test script, which reads `BUILD_ARTIFACT` |
| `BUILD_ARTIFACT` | string | n/a | Packed build written by the build script, relative to the repository root |
| `DOCKER_TAG` | string | `u24-llvm-ompi-latest` | Tag of `scritical/private-dev` image to build and test inside |
| `USE_DVC` | boolean | `false` | Enables DVC to pull reference data for the test job only |
| `BUILD_TIMEOUT` | number | `120` | Runtime allowed for the build job, in minutes |
| `TEST_TIMEOUT` | number | `120` | Runtime allowed for the test job, in minutes |

**Required Secrets:**
| Name | Description |
| :--- | :---------- |
| `BW_ACCESS_TOKEN` | Bitwarden access token |

If these secrets are configured at the organization level, callers can use `secrets: inherit` instead of listing each secret.

---

### build-docs.yaml

Docker-based documentation build and (optional) publish workflow using the `scritical/private-dev` image.

Single job: builds the docs site inside the container, then — if `PUBLISH=true` — calls the `publish-to-api-docs` composite action from `scritical/documentation-server` to publish the rendered HTML.

Gating lives in the caller: pass a boolean expression for `PUBLISH` (or omit it for build-only).

| Name | Type | Default | Description |
| :--- | :--- | :------ | :---------- |
| `PROJECT_ID` | string | n/a | URL slug under `https://api-docs.scritical.com/<PROJECT_ID>/`. **Required when `PUBLISH=true`.** Must match `^[a-z0-9-]+$` (no slashes, no uppercase, no underscores) |
| `PUBLISH` | boolean | `false` | Whether to publish after building. Typically passed as an expression. |
| `TIMEOUT` | number | `30` | Runtime allowed for the job, in minutes |
| `DOCKER_TAG` | string | `u24-gcc-ompi-latest` | Tag of `scritical/private-dev` image to build inside |
| `BUILD_SCRIPT` | string | `""` | Path to a build script run inside the container before the docs build. Use for compiled packages whose autodoc needs extension modules built from source. Runs before `PIP_INSTALL_FLAGS`; leave empty to skip |
| `PIP_INSTALL_FLAGS` | string | `--no-build-isolation --no-deps` | Flags passed to `pip install <FLAGS> .` from the repo root. Set to empty string to skip the install step entirely (for pure-docs repos with no installable package) |
| `DOCS_SRC` | string | `doc` | Docs source directory (relative to repo root). Must contain a `Makefile` with an `html` target that emits to `_build/html/` |

**Required Secrets:**
| Name | Description |
| :--- | :---------- |
| `BW_ACCESS_TOKEN` | Bitwarden access token |

If these secrets are configured at the organization level, callers can use `secrets: inherit` instead of listing each secret.

---

### ruff.yaml

Python formatting and linting using Ruff.
The workflow checks out the org-wide Ruff configuration from `scritical/.github` and uses it for format, lint, and isort checks.

| Name | Type | Default | Description |
| :--- | :--- | :------ | :---------- |
| `TIMEOUT` | number | `20` | Runtime allowed for the job, in minutes |
| `MCCABE` | boolean | `false` | Enable McCabe complexity check (pass/fail, max complexity = 10) |
| `ISORT` | boolean | `false` | Enable import sorting check (pass/fail) |

**Configuration Override:** Create a `ruff.toml` in your repo with:
```toml
extend = "~/.config/ruff/ruff.toml"

# Local overrides here
[lint]
ignore = ["N802"]
```

---

### mypy.yaml

Runs MyPy type checking in the GCC OpenMPI Docker image.

| Name | Type | Default | Description |
| :--- | :--- | :------ | :---------- |
| `TIMEOUT` | number | `30` | Runtime allowed for the job, in minutes |

**Required Secrets:**
| Name | Description |
| :--- | :---------- |
| `BW_ACCESS_TOKEN` | Bitwarden access token |

If these secrets are configured at the organization level, callers can use `secrets: inherit` instead of listing each secret.

---

### tapenade.yaml

Run Tapenade automatic differentiation and check for uncommitted changes.

| Name | Type | Default | Description |
| :--- | :--- | :------ | :---------- |
| `TIMEOUT` | number | `10` | Runtime allowed for the job, in minutes |
| `TAPENADE_SCRIPT` | string | `.github/build_tapenade.sh` | Path to Tapenade build script |

Uses Tapenade version 3.16 from tapenade_3.16-v2-723-ge8da61555.tar. Using a different version will create a diff.

Here is the link to our tapenade version: https://gitlab.inria.fr/tapenade/tapenade/-/package_files/112870/download

---

### clang_format.yaml

C/C++ and CUDA code formatting checks using clang-format: the tracked `*.h`, `*.hpp`, `*.c`, `*.cpp`, `*.cu` and `*.cuh` files.

| Name | Type | Default | Description |
| :--- | :--- | :------ | :---------- |
| `TIMEOUT` | number | `10` | Runtime allowed for the job, in minutes |

**Configuration Override:** Create a `.clang-format` file in your repo root.

Uses the exact clang-format version pinned in the workflow (`CLANG_FORMAT_VERSION`), installed from PyPI. `clang-format.sh` and the Docker images use the same version, so install it locally with `pip install clang-format==<version>`.

---

### fprettify.yaml

Fortran 90 code formatting checks using fprettify.

| Name | Type | Default | Description |
| :--- | :--- | :------ | :---------- |
| `TIMEOUT` | number | `10` | Runtime allowed for the job, in minutes |

**Configuration Override:** Create a `.fprettify.rc` file in your repo root.

---

### branch-name-check.yaml

Enforces branch naming conventions for pull requests. It has no inputs.

Job `check-branch-name`:

- For PRs targeting `main`, source branches must start with `feature-`, `bugfix-`, `hotfix-` or `doc-`.
- For PRs targeting `client-*`, source branches must be `main` or start with `feature-`, `bugfix-`, `hotfix-` or `doc-`.

Job `doc-only-check` runs only on a pull request from a `doc-` branch. A repository can skip its build and test jobs on the `doc-` prefix, because a `doc-` branch holds a documentation-only change:

```yaml
  build:
    if: ${{ !startsWith(github.head_ref, 'doc-') }}
    uses: scritical/.github/.github/workflows/build.yaml@main
```

The job fails when the pull request changes a path outside the documentation paths. A renamed file counts under both names, because the job reads the changed paths from `git diff --name-only --no-renames <base>...<head>`. The job also fails when the diff lists no path.

The job reads the documentation paths from `.github/doc-paths` on the base commit of the pull request. A pull request therefore cannot change its own documentation paths. The file holds one git pathspec per line. A line that starts with `#` is a comment:

```
# A directory, with everything under it.
docs/
# A file name pattern, in every directory.
*.md
```

The file is required. The job fails when the base commit has no `.github/doc-paths`, or when the file holds no pathspec. A repository adds the file in a `feature-` pull request before its first `doc-` pull request.

A repository that skips jobs on the `doc-` prefix must do two things:

- List in `.github/doc-paths` only the paths that no skipped job reads. In a Sphinx repository, `doc/` also holds `conf.py` and can hold scripts. A documentation build or a test can read those files.
- Run each check of the whole tree on a `doc-` pull request too. A check that reads every tracked file, such as a check for binary files, also reads the documentation paths. If the check runs only in a skipped job, move it to a job that runs on `doc-` pull requests.

An organization ruleset can require the workflow on every pull request with no caller job, because the workflow also has a `pull_request` trigger.

---

### bump_version.yaml

Tags the merge commit of a merged PR with the next `vX.Y.Z` version, bumped by the `[major]`, `[minor]` or `[patch]` keyword in the PR title.
A PR whose title has no single keyword gets no tag and a warning, and the next tag covers it.
Call it on `pull_request` events of type `closed`, and grant the calling job `contents: write` and `pull-requests: read`:

```yaml
on:
  pull_request:
    types:
      - closed
    branches:
      - main

jobs:
  bump_version:
    permissions:
      contents: write
      pull-requests: read
    uses: scritical/.github/.github/workflows/bump_version.yaml@main
```

Runs in a repository go one at a time, in the order they were queued.
In a stack, every run tags all untagged merged PRs at or below its own, in stack order, in one atomic push, so a stack merged at once gets one tag per PR in commit order.
A PR merged outside the stack around the same time can still get a version out of commit order.
Without `pull-requests: read`, the run logs a warning and tags each PR on its own, so a stack merged at once can be tagged out of order.

## Setting Up Workflows

### Step 1: Create Workflow File

Create `.github/workflows/ci.yaml` in your repository:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    uses: scritical/.github/.github/workflows/build.yaml@main
    with:
      GCC_CONFIG: config/defaults/config.LINUX_GFORTRAN.mk # If necessary
    secrets: inherit

  ruff:
    uses: scritical/.github/.github/workflows/ruff.yaml@main

  clang-format:
    uses: scritical/.github/.github/workflows/clang_format.yaml@main

  fprettify:
    uses: scritical/.github/.github/workflows/fprettify.yaml@main
```

### Step 2: Write Build Script

Create `.github/build.sh` in your repository:

```bash
#!/bin/bash
set -e
cp $CONFIG_FILE config/config.mk
make
pip install .
```

### Step 3: Write Test Script

Create `.github/test.sh` in your repository:

```bash
#!/bin/bash
set -e
./input_files/get-input-files.sh
testflo -v . -n 1
```

### Step 4: Add Secrets

In your organization settings, add the required secrets:
- `BW_ACCESS_TOKEN` - Bitwarden access token

---

## Complex Builds

For repositories requiring both real and complex builds:

```yaml
jobs:
  build-real:
    uses: scritical/.github/.github/workflows/build.yaml@main
    with:
      GCC_CONFIG: config/defaults/config.LINUX_GFORTRAN.mk
      BUILD_SCRIPT: .github/build_real.sh
      TEST_SCRIPT: .github/test_real.sh
    secrets: inherit

  build-complex:
    uses: scritical/.github/.github/workflows/build.yaml@main
    with:
      GCC_CONFIG: config/defaults/config.LINUX_GFORTRAN.mk
      BUILD_SCRIPT: .github/build_complex.sh
      TEST_SCRIPT: .github/test_complex.sh
    secrets: inherit
```

---

## Adding Status Badge

Add a status badge to your README:

```markdown
![CI](https://github.com/scritical/REPO_NAME/actions/workflows/ci.yaml/badge.svg)
```
