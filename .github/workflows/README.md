# GitHub Actions Workflows

Reusable GitHub Actions workflows for Supercritical repositories. These workflows are called from individual repositories using the `workflow_call` trigger.

## Available Workflows

| Workflow | Description |
| :------- | :---------- |
| `build.yaml` | Build and test code in Docker container |
| `format-and-lint.yaml` | Python formatting and linting with ruff/pre-commit |
| `pypi.yaml` | Publish Python packages to PyPI |
| `tapenade.yaml` | Tapenade automatic differentiation checks |
| `clang_format.yaml` | C/C++ formatting checks |
| `fprettify.yaml` | Fortran 90 formatting checks |
| `isort.yaml` | Python import sorting checks |
| `pylint.yaml` | Python linting with pylint |
| `mypy.yaml` | Python type checking |
| `branch-name-check.yml` | Enforce branch naming conventions |

---

## Workflow Options

### build.yaml

Docker-based build and test workflow using the `scritical/private-dev` image.

| Name | Type | Default | Description |
| :--- | :--- | :------ | :---------- |
| `TIMEOUT` | number | `120` | Runtime allowed for the job, in minutes |
| `GCC_CONFIG` | string | `""` | Path to GCC configuration file (from repository root) |
| `BUILD_SCRIPT` | string | `.github/build_real.sh` | Path to build script. Empty string skips this step |
| `TEST_SCRIPT` | string | `.github/test_real.sh` | Path to test script. Empty string skips this step |

**Required Secrets:**
| Name | Description |
| :--- | :---------- |
| `DOCKER_OAT` | Docker registry Organization Access Token |

---

### format-and-lint.yaml

Python formatting and linting using pre-commit with ruff.

| Name | Type | Default | Description |
| :--- | :--- | :------ | :---------- |
| `MCCABE` | boolean | `false` | Enable McCabe complexity check (pass/fail, max complexity = 10) |

**Configuration Override:** Create a `ruff.toml` in your repo with:
```toml
extend = "~/.config/ruff/ruff.toml"

# Local overrides here
[lint]
ignore = ["N802"]
```

---

### pypi.yaml

Publish Python packages to PyPI on tagged releases.

**Required Secrets:**
| Name | Description |
| :--- | :---------- |
| `PYPI_API_TOKEN` | PyPI API token for publishing |

---

### tapenade.yaml

Run Tapenade automatic differentiation and check for uncommitted changes.

| Name | Type | Default | Description |
| :--- | :--- | :------ | :---------- |
| `TIMEOUT` | number | `10` | Runtime allowed for the job, in minutes |
| `TAPENADE_SCRIPT` | string | `.github/build_tapenade.sh` | Path to Tapenade build script |

Uses Tapenade version 3.16.

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

### isort.yaml

Python import sorting checks.

**Configuration Override:** Create a `.isort.cfg` file in your repo root with overrides. The global and local configs are merged automatically using `combine-config.py`.

---

### pylint.yaml

Python linting with pylint.

**Configuration Override:** Create a `.pylintrc` file in your repo root with overrides. The global and local configs are merged automatically using `combine-config.py`.

---

### mypy.yaml

Python type checking with mypy.

No configurable inputs. Uses Python 3.11.

---

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
      DOCKER_OAT: ${{ secrets.DOCKER_OAT }}

  format-and-lint:
    uses: scritical/.github/.github/workflows/format-and-lint.yaml@main

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
- `DOCKER_OAT` - Docker Organization Access Token for pulling private images

---

## PyPI Publishing

For repositories that publish to PyPI, extend your workflow:

```yaml
name: CI

on:
  push:
    branches: [main]
    tags:
      - 'v*.*.*'
  pull_request:
    branches: [main]

jobs:
  format-and-lint:
    uses: scritical/.github/.github/workflows/format-and-lint.yaml@main

  build:
    uses: scritical/.github/.github/workflows/build.yaml@main
    with:
      GCC_CONFIG: config/defaults/config.LINUX_GFORTRAN.mk
    secrets:
      DOCKER_OAT: ${{ secrets.DOCKER_OAT }}

  pypi:
    needs: [format-and-lint, build]
    uses: scritical/.github/.github/workflows/pypi.yaml@main
    secrets:
      PYPI_API_TOKEN: ${{ secrets.PYPI_API_TOKEN }}
```

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
      DOCKER_OAT: ${{ secrets.DOCKER_OAT }}

  build-complex:
    uses: scritical/.github/.github/workflows/build.yaml@main
    with:
      GCC_CONFIG: config/defaults/config.LINUX_GFORTRAN.mk
      BUILD_SCRIPT: .github/build_complex.sh
      TEST_SCRIPT: .github/test_complex.sh
    secrets:
      DOCKER_OAT: ${{ secrets.DOCKER_OAT }}
```

---

## Configuration Inheritance

Several workflows support configuration inheritance/overrides:

| Tool | Method | Local Config File |
| :--- | :----- | :---------------- |
| Ruff | Native `extend` keyword | `ruff.toml` |
| Pylint | Merged via `combine-config.py` | `.pylintrc` |
| isort | Merged via `combine-config.py` | `.isort.cfg` |
| clang-format | Local file takes precedence | `.clang-format` |
| fprettify | Local file takes precedence | `.fprettify.rc` |

### Example: Ruff Override

```toml
# ruff.toml
extend = "~/.config/ruff/ruff.toml"

[lint]
ignore = ["N802", "N803"]  # Allow uppercase function/argument names
```

### Example: Pylint Override

```ini
# .pylintrc (partial - only overrides)
[MESSAGES CONTROL]
disable = C0114,C0115

[FORMAT]
max-line-length = 150
```

---

## Adding Status Badge

Add a status badge to your README:

```markdown
![CI](https://github.com/scritical/REPO_NAME/actions/workflows/ci.yaml/badge.svg)
```
