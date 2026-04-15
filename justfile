export KAS_CONTAINER_ENGINE := env("KAS_CONTAINER_ENGINE", "podman")
export SSTATE_DIR := env("SSTATE_DIR", justfile_directory() + "/cache/sstate-cache")
export DL_DIR := env("DL_DIR", justfile_directory() + "/cache/downloads")

_uv_run := "uv run"
_uv_dev := "uv run --group dev"
_cli := "python -m rugix_bsp.cli"

[private]
_default:
    @just --list

# List all available boards and releases.
list:
    {{ _uv_run }} {{ _cli }} list

# Build a BSP for a specific board (e.g., `just build radxa-rock5b`).
build board *args:
    {{ _uv_run }} {{ _cli }} build {{ board }} {{ args }}

# Build BSPs for all boards and releases.
build-all *args:
    {{ _uv_run }} {{ _cli }} build-all {{ args }}

# Print content hash for a board (for CI change detection).
hash board *args:
    {{ _uv_run }} {{ _cli }} hash {{ board }} {{ args }}

# Generate Kas config without building (for debugging).
kas-config board *args:
    {{ _uv_run }} {{ _cli }} kas-config {{ board }} {{ args }}

# Push a BSP archive to an OCI registry.
push archive *args:
    {{ _uv_run }} {{ _cli }} push {{ archive }} {{ args }}

# Run type checker.
typecheck:
    {{ _uv_dev }} mypy src/

# Run linter.
lint:
    {{ _uv_dev }} ruff check src/
    {{ _uv_dev }} ruff format --check src/

# Auto-format code.
fmt:
    {{ _uv_dev }} ruff check --fix src/
    {{ _uv_dev }} ruff format src/

# Run all checks.
check: lint typecheck
