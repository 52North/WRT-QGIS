# WRT-QGIS

QGIS Plugin for the Weather Routing Tool

## Requirements

- QGIS 3.44 or newer

## Installation

The plugin can be installed directly from a ZIP archive through the QGIS Plugin Manager.

### 1. Get the plugin ZIP

Download the latest `WRT-QGIS.zip` from the
[releases page](https://github.com/52north/WRT-QGIS/releases), or build it
yourself from the source:

```bash
git clone https://github.com/52north/WRT-QGIS.git
# Create a ZIP whose top-level folder matches the plugin name
zip -r WRT-QGIS.zip WRT-QGIS -x "WRT-QGIS/.git/*" "WRT-QGIS/.gitignore"
```

### 2. Install through the QGIS Plugin Manager

1. Open QGIS.
2. Go to **Plugins → Manage and Install Plugins…**
3. Select the **Install from ZIP** tab.
4. Click the **…** button and browse to the downloaded/built `WRT-QGIS.zip`.
5. Click **Install Plugin**.
6. Confirm any security warning about installing plugins from a ZIP file.

### 3. Enable the plugin

1. Switch to the **Installed** tab in the Plugin Manager.
2. Make sure **Weather Routing Tool Plugin** is checked (enabled).
3. Close the Plugin Manager. The plugin is now available from the toolbar / **Plugins** menu.

## Updating

To update to a newer version, repeat the **Install from ZIP** steps with the new
ZIP file. QGIS will overwrite the existing installation. Restart QGIS if the
changes do not appear immediately.

## Development

### Linting & formatting

The project uses [Ruff](https://docs.astral.sh/ruff/) for both linting and
formatting. The configuration lives in [`pyproject.toml`](pyproject.toml).

Install Ruff:

```bash
uv install ruff
# or
pip install ruff
```

Common commands:

```bash
ruff check .              # lint
ruff check . --fix        # lint and apply safe fixes
ruff format .             # format
ruff format --check .     # verify formatting without writing changes
```

### Pre-commit hook

A [pre-commit](https://pre-commit.com/) hook runs Ruff automatically on staged
files before each commit. Enable it once after cloning:

```bash
pip install pre-commit   # or: uv tool install pre-commit
pre-commit install
```

Run it against the whole codebase at any time with:

```bash
pre-commit run --all-files
```

### GitHub Actions

Every push to `main` and every pull request runs the same Ruff lint and
format checks via GitHub Actions (see
[`.github/workflows/lint.yml`](.github/workflows/lint.yml)).
