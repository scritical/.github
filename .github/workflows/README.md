# GitHub Actions Workflows

Reusable GitHub Actions workflows for Supercritical repositories. These workflows are called from individual repositories using the `workflow_call` trigger.

## Available Workflows

| Workflow | Description |
| :------- | :---------- |
| `build.yaml` | Build and test code in Docker container |
| `tapenade.yaml` | Tapenade automatic differentiation checks |
| `clang_format.yaml` | C/C++ formatting checks |
| `fprettify.yaml` | Fortran 90 formatting checks |
| `ruff.yaml` | Python formatting and linting with Ruff |
| `branch-name-check.yaml` | Enforce branch naming conventions |

---

## Workflow Options

### build.yaml

Docker-based build and test workflow using the `scritical/private-dev` image.
Runs separate GCC and Intel jobs when the matching config input is provided.

| Name | Type | Default | Description |
| :--- | :--- | :------ | :---------- |
| `TIMEOUT` | number | `120` | Runtime allowed for the job, in minutes |
| `GCC_CONFIG` | string | `""` | Path to GCC configuration file (from repository root) |
| `INTEL_CONFIG` | string | `""` | Path to Intel configuration file (from repository root) |
| `INTEL` | boolean | `false` | Whether to run Intel-specific build and test steps |
| `GCC` | boolean | `true` | Whether to run GCC-specific build and test steps |
| `BUILD_SCRIPT` | string | `.github/build_real.sh` | Path to build script. Empty string skips this step |
| `TEST_SCRIPT` | string | `.github/test_real.sh` | Path to test script. Empty string skips this step |
| `TEST` | boolean | `true` | Whether to run the test step |
| `MYPY` | boolean | `false` | Whether to run mypy type checking |

**Required Secrets:**
| Name | Description |
| :--- | :---------- |
| `DOCKER_USER` | Docker registry username |
| `DOCKER_OAT` | Docker registry Organization Access Token |

---

### ruff.yaml

Python formatting and linting using Ruff.
The workflow checks out the org-wide Ruff configuration from `scritical/.github` and uses `ruff.toml` from that repo as the base config.

| Name | Type | Default | Description |
| :--- | :--- | :------ | :---------- |
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

C/C++ code formatting checks using clang-format.

| Name | Type | Default | Description |
| :--- | :--- | :------ | :---------- |
| `TIMEOUT` | number | `10` | Runtime allowed for the job, in minutes |

**Configuration Override:** Create a `.clang-format` file in your repo root.

---

### fprettify.yaml

Fortran 90 code formatting checks using fprettify.

| Name | Type | Default | Description |
| :--- | :--- | :------ | :---------- |
| `TIMEOUT` | number | `10` | Runtime allowed for the job, in minutes |

**Configuration Override:** Create a `.fprettify.rc` file in your repo root.

---

### branch-name-check.yaml

Enforces branch naming conventions for pull requests:

- For PRs targeting `main`, source branches must start with `feature-`, `bugfix-`, or `hotfix-`.
- For PRs targeting `client-*`, source branches must start with `feature-`, `bugfix-`, or `hotfix-`.

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
      GCC_CONFIG: config/defaults/config.LINUX_GFORTRAN.mk
      BUILD_SCRIPT: .github/build_real.sh
      TEST_SCRIPT: .github/test_real.sh
    secrets:
      DOCKER_USER: ${{ secrets.DOCKER_USER }}
      DOCKER_OAT: ${{ secrets.DOCKER_OAT }}

  ruff:
    uses: scritical/.github/.github/workflows/ruff.yaml@main

  clang-format:
    uses: scritical/.github/.github/workflows/clang_format.yaml@main

  fprettify:
    uses: scritical/.github/.github/workflows/fprettify.yaml@main
```

### Step 2: Write Build Script

Create `.github/build_real.sh` in your repository:

```bash
#!/bin/bash
set -e
cp $CONFIG_FILE config/config.mk
make
pip install .
```

### Step 3: Write Test Script

Create `.github/test_real.sh` in your repository:

```bash
#!/bin/bash
set -e
./input_files/get-input-files.sh
testflo -v . -n 1
```

### Step 4: Add Secrets

In your repository settings, add the required secrets:
- `DOCKER_USER` - Docker organization name
- `DOCKER_OAT` - Docker Organization Access Token for pulling private images

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
    secrets:
      DOCKER_USER: ${{ secrets.DOCKER_USER }}
      DOCKER_OAT: ${{ secrets.DOCKER_OAT }}

  build-complex:
    uses: scritical/.github/.github/workflows/build.yaml@main
    with:
      GCC_CONFIG: config/defaults/config.LINUX_GFORTRAN.mk
      BUILD_SCRIPT: .github/build_complex.sh
      TEST_SCRIPT: .github/test_complex.sh
    secrets:
      DOCKER_USER: ${{ secrets.DOCKER_USER }}
      DOCKER_OAT: ${{ secrets.DOCKER_OAT }}
```

---

## Configuration Inheritance

Several workflows support configuration inheritance/overrides:

| Tool | Method | Local Config File |
| :--- | :----- | :---------------- |
| Ruff | Native `extend` keyword | `ruff.toml` |
| clang-format | Local file takes precedence | `.clang-format` |
| fprettify | Local file takes precedence | `.fprettify.rc` |

### Example: Ruff Override

```toml
# ruff.toml
extend = "~/.config/ruff/ruff.toml"

[lint]
ignore = ["N802", "N803"]  # Allow uppercase function/argument names
```

---

## Adding Status Badge

Add a status badge to your README:

```markdown
![CI](https://github.com/scritical/REPO_NAME/actions/workflows/ci.yaml/badge.svg)
```
