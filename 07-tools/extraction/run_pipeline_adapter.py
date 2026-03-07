#!/usr/bin/env python3
"""Run extraction pipeline via central-package adapter with local fallback.

Behavior:
- If LOUSARDZAG_USE_CENTRAL_PACKAGE=1 and central package is installed,
  execute tools by central module path from registry metadata.
- Otherwise, execute local scripts from 07-tools/extraction.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "02-src"))

from lousardzag.core_adapters import get_extraction_registry


TOOLS = [
    "export_core_contracts_jsonl",
    "validate_contract_alignment",
    "ingest_wa_fingerprints_to_contracts",
    "merge_document_records",
    "merge_document_records_with_profiles",
    "extract_fingerprint_index",
    "materialize_dialect_views",
    "summarize_unified_documents",
]


@dataclass
class ToolRunResult:
    name: str
    command: list[str]
    returncode: int
    duration_seconds: float
    mode: str
    skipped: bool = False


class AdapterPipelineRunner:
    def __init__(self, project_root: Path, dry_run: bool, skip_tools: set[str]):
        self.project_root = project_root
        self.dry_run = dry_run
        self.skip_tools = skip_tools
        self.local_extraction_dir = ROOT / "07-tools" / "extraction"
        self.registry = get_extraction_registry()
        self.results: list[ToolRunResult] = []

    def _command_for_tool(self, tool_name: str) -> tuple[list[str], str]:
        if self.registry is not None:
            spec = self.registry.get_tool(tool_name)
            if spec is not None and spec.module:
                return [sys.executable, "-m", spec.module], "central"
        local_script = self.local_extraction_dir / f"{tool_name}.py"
        return [sys.executable, str(local_script)], "local"

    def run(self) -> bool:
        print("=" * 80)
        print("ADAPTER EXTRACTION PIPELINE")
        print("=" * 80)
        print(f"Project root: {self.project_root}")
        print(f"Central registry available: {self.registry is not None}")
        print(f"Dry run: {self.dry_run}")
        print("=" * 80)

        all_ok = True

        for idx, tool_name in enumerate(TOOLS, start=1):
            if tool_name in self.skip_tools:
                print(f"[{idx}/{len(TOOLS)}] skipping {tool_name}")
                self.results.append(
                    ToolRunResult(
                        name=tool_name,
                        command=[],
                        returncode=0,
                        duration_seconds=0.0,
                        mode="skipped",
                        skipped=True,
                    )
                )
                continue

            cmd, mode = self._command_for_tool(tool_name)
            print(f"[{idx}/{len(TOOLS)}] {tool_name} ({mode})")

            if self.dry_run:
                print(f"  [DRY RUN] {' '.join(cmd)}")
                self.results.append(
                    ToolRunResult(
                        name=tool_name,
                        command=cmd,
                        returncode=0,
                        duration_seconds=0.0,
                        mode=mode,
                    )
                )
                continue

            started = time.time()
            proc = subprocess.run(cmd, cwd=self.project_root, capture_output=True, text=True)
            duration = time.time() - started

            self.results.append(
                ToolRunResult(
                    name=tool_name,
                    command=cmd,
                    returncode=proc.returncode,
                    duration_seconds=duration,
                    mode=mode,
                )
            )

            print(f"  exit={proc.returncode} in {duration:.2f}s")
            if proc.returncode != 0:
                all_ok = False
                print("  failed")

        return all_ok

    def write_report(self, output_json: Path) -> None:
        payload = {
            "execution": {
                "dry_run": self.dry_run,
                "central_registry_available": self.registry is not None,
                "total_tools": len(self.results),
                "failed_tools": [r.name for r in self.results if not r.skipped and r.returncode != 0],
            },
            "tools": [
                {
                    "name": r.name,
                    "mode": r.mode,
                    "command": r.command,
                    "returncode": r.returncode,
                    "duration_seconds": r.duration_seconds,
                    "skipped": r.skipped,
                }
                for r in self.results
            ],
        }
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Report written: {output_json}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run extraction pipeline via adapter")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=ROOT,
        help="Project root for tool execution (default: lousardzag root)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing")
    parser.add_argument("--skip", action="append", default=[], help="Tool name to skip (repeatable)")
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("08-data/pipeline_execution_report_adapter.json"),
        help="Output JSON report path (relative to project root if not absolute)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    output_json = args.output_json if args.output_json.is_absolute() else project_root / args.output_json

    runner = AdapterPipelineRunner(
        project_root=project_root,
        dry_run=args.dry_run,
        skip_tools=set(args.skip),
    )

    success = runner.run()
    runner.write_report(output_json)

    if success:
        print("Pipeline completed successfully")
        return 0
    print("Pipeline completed with failures")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
