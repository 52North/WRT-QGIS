# Contributing to WRT-QGIS

Thanks for your interest in improving the plugin. This guide covers the
development workflow: linting, formatting, and CI.

## Requirements

- QGIS 3.44 or newer
- Python (matching your QGIS installation's Python)

## Getting the code

```bash
git clone https://github.com/52north/WRT-QGIS.git
```

## Linting & formatting

The project uses [Ruff](https://docs.astral.sh/ruff/) for both linting and
formatting. The configuration lives in [pyproject.toml](pyproject.toml).

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

## Pre-commit hook

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

## GitHub Actions

Every push to `main` and every pull request runs the same Ruff lint and
format checks via GitHub Actions (see
[.github/workflows/lint.yml](.github/workflows/lint.yml)).

## Project layout

- `config_wizard/` — the multi-page setup wizard (route, algorithm, boat,
  weather, constraints, review). See the [`Weather Routing Tool`](https://github.com/52North/WeatherRoutingTool)  repo for
  anything config-related that lives on the routing side.
- `visualizer/` — the map timeline / data visualizer dock.
- `tools/` — standalone scripts, e.g. `fix_netcdf_names.py`.

## Submitting changes

1. Create a branch off `main`.
2. Make your changes, keeping commits focused.
3. Run `ruff format .`and `ruff check . --fix` before opening a PR.
4. Open a pull request against `main` only.
