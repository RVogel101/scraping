"""Integration checks for armenian-corpus-core migration wiring.

These tests validate that lousardzag can consume the central package through
its adapter layer when the feature flag is enabled.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def enable_central_package(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enable central package usage for adapter-level integration checks."""
    monkeypatch.setenv("LOUSARDZAG_USE_CENTRAL_PACKAGE", "1")


def test_adapter_registry_available(enable_central_package: None) -> None:
    """Adapter should expose a registry when central package is installed."""
    from lousardzag.core_adapters import get_extraction_registry

    registry = get_extraction_registry()
    assert registry is not None, "Central registry not available via adapter"
    tools = registry.list_tools()
    assert len(tools) >= 8


def test_adapter_diagnostics_green(enable_central_package: None) -> None:
    """Diagnostics should report an installed and reachable central package."""
    from lousardzag.core_adapters import diagnose_central_package

    diagnostics = diagnose_central_package()

    assert diagnostics["central_package_enabled"] is True
    assert diagnostics["central_package_installed"] is True
    assert diagnostics["registry_available"] is True
    assert diagnostics["tools_count"] >= 8


def test_orchestration_cli_dry_run_from_central_package(enable_central_package: None) -> None:
    """Central orchestration CLI should locate and dry-run all lousardzag tools."""
    # Repository layout expected by this migration:
    # lousardzag/ (this repo) and sibling armenian-corpus-core/
    lousardzag_root = Path(__file__).resolve().parents[2]
    central_root = lousardzag_root.parent / "armenian-corpus-core"
    cli_path = central_root / "armenian_corpus_core" / "extraction" / "run_extraction_pipeline.py"

    if not cli_path.exists():
        pytest.skip(f"Central package CLI not found at expected path: {cli_path}")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    proc = subprocess.run(
        [sys.executable, str(cli_path), "--project", "lousardzag", "--dry-run"],
        cwd=str(lousardzag_root),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    assert "Pipeline completed successfully" in combined
    assert "summarize_unified_documents" in combined


def test_adapter_runner_dry_run_central_mode(enable_central_package: None) -> None:
    """Adapter runner should execute in central mode when feature flag is enabled."""
    lousardzag_root = Path(__file__).resolve().parents[2]
    adapter_runner = lousardzag_root / "07-tools" / "extraction" / "run_pipeline_adapter.py"

    if not adapter_runner.exists():
        pytest.skip(f"Adapter runner not found: {adapter_runner}")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["LOUSARDZAG_USE_CENTRAL_PACKAGE"] = "1"

    proc = subprocess.run(
        [sys.executable, str(adapter_runner), "--dry-run"],
        cwd=str(lousardzag_root),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    assert "(central)" in combined


def test_adapter_runner_dry_run_local_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Adapter runner should fall back to local mode when feature flag is disabled."""
    monkeypatch.setenv("LOUSARDZAG_USE_CENTRAL_PACKAGE", "0")

    lousardzag_root = Path(__file__).resolve().parents[2]
    adapter_runner = lousardzag_root / "07-tools" / "extraction" / "run_pipeline_adapter.py"

    if not adapter_runner.exists():
        pytest.skip(f"Adapter runner not found: {adapter_runner}")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["LOUSARDZAG_USE_CENTRAL_PACKAGE"] = "0"

    proc = subprocess.run(
        [sys.executable, str(adapter_runner), "--dry-run"],
        cwd=str(lousardzag_root),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    assert "(local)" in combined


def test_adapter_runner_dry_run_default_env_central(monkeypatch: pytest.MonkeyPatch) -> None:
    """Adapter runner should default to central mode when env var is unset."""
    monkeypatch.delenv("LOUSARDZAG_USE_CENTRAL_PACKAGE", raising=False)

    lousardzag_root = Path(__file__).resolve().parents[2]
    adapter_runner = lousardzag_root / "07-tools" / "extraction" / "run_pipeline_adapter.py"

    if not adapter_runner.exists():
        pytest.skip(f"Adapter runner not found: {adapter_runner}")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("LOUSARDZAG_USE_CENTRAL_PACKAGE", None)

    proc = subprocess.run(
        [sys.executable, str(adapter_runner), "--dry-run"],
        cwd=str(lousardzag_root),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    assert "(central)" in combined
