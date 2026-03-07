# Step 5 Optional Cleanup Plan (Post-Merge)

Date: 2026-03-06
Scope: lousardzag extraction pipeline migration cleanup

## Goal

Retire duplicated local extraction scripts under `07-tools/extraction` after central package execution is stable, while preserving a fast rollback path.

## Current Baseline

- Adapter exists: `07-tools/extraction/run_pipeline_adapter.py`
- Adapter supports two modes:
  - Central mode when `LOUSARDZAG_USE_CENTRAL_PACKAGE=1` and registry is available
  - Local fallback mode when central mode is disabled/unavailable
- CI extraction steps now invoke central package modules in `.github/workflows/extraction_pipeline.yml`
- Central package dependency is not currently declared in `requirements.txt` or `pyproject.toml`

### Phase 1 Baseline Evidence (Completed)

- Baseline command executed in `wa-llm`:
   - `python 07-tools/extraction/check_step5_readiness.py`
- Baseline summary artifact:
   - `08-data/step5_readiness_baseline_phase1.txt`
- Detailed report artifact:
   - `08-data/step5_readiness_report.json`
- Snapshot recorded (from baseline summary file):
   - `exit_code=0`
   - `duration_seconds=1.28`
   - `all_passed=True`
   - `adapter_dry_run_central: passed=True, returncode=0`
   - `adapter_dry_run_fallback: passed=True, returncode=0`
   - `integration_test: passed=True, returncode=0`

Use this snapshot as the pre-cutover reference when validating PR A (CI module cutover) and PR C (local script retirement).

## Readiness Gates (Must Pass Before Any Deletion)

1. Monitoring window complete: at least 1-2 weeks of stable post-merge runs.
2. Central dry-run stability:
   - `LOUSARDZAG_USE_CENTRAL_PACKAGE=1`
   - `python 07-tools/extraction/run_pipeline_adapter.py --dry-run`
3. Fallback dry-run stability (rollback safety):
   - `LOUSARDZAG_USE_CENTRAL_PACKAGE=0`
   - `python 07-tools/extraction/run_pipeline_adapter.py --dry-run`
4. Integration tests green:
   - `python -m pytest 04-tests/integration/test_central_package_integration.py -q`
5. CI dependency decision made and implemented:
   - Either central package pinned and installed in CI, or local fallback retained.

## Proposed Execution Phases

### Phase A: CI Cutover Plan (No File Deletions)

1. Introduce explicit central package installation in CI.
2. Keep adapter dry-run check in CI.
3. Replace direct local script invocations in workflow with central module invocations, one stage at a time.
4. Keep `continue-on-error: true` where data prerequisites are environment-dependent.

Implementation status (2026-03-06):

- Completed for PR A scope.
- Completed in `.github/workflows/extraction_pipeline.yml`:
   - Added central package install step:
      - `pip install git+https://github.com/RVogel101/armenian-corpus-core@main`
   - Switched extraction execution steps to central module invocations:
      - `python -m armenian_corpus_core.extraction.export_core_contracts_jsonl`
      - `python -m armenian_corpus_core.extraction.validate_contract_alignment`
      - `python -m armenian_corpus_core.extraction.ingest_wa_fingerprints_to_contracts`
      - `python -m armenian_corpus_core.extraction.merge_document_records`
      - `python -m armenian_corpus_core.extraction.merge_document_records_with_profiles`
      - `python -m armenian_corpus_core.extraction.extract_fingerprint_index`
      - `python -m armenian_corpus_core.extraction.materialize_dialect_views`
      - `python -m armenian_corpus_core.extraction.summarize_unified_documents`
   - Kept adapter dry-run step unchanged for transitional verification.

Acceptance criteria:
- No net increase in failing CI jobs.
- Summary and artifacts still generated for successful stages.

### Phase B: Runtime Default Strategy

1. Decide default mode policy:
   - Conservative: keep default fallback (`0`) until central dependency management is fully hardened.
   - Aggressive: set default central (`1`) after CI and local validation prove stable.
2. Document operational guidance in setup docs.

Implementation status (2026-03-06):

- Completed for PR B scope with central-default policy.
- Runtime default now prefers central mode when `LOUSARDZAG_USE_CENTRAL_PACKAGE` is unset.
- Fallback remains available for incident response via explicit disable:
   - `LOUSARDZAG_USE_CENTRAL_PACKAGE=0`
- Added integration coverage to lock default behavior:
   - `test_adapter_runner_dry_run_default_env_central()` in `04-tests/integration/test_central_package_integration.py`

Acceptance criteria:
- Team can reproduce central-mode execution from clean environment.
- Rollback to fallback mode remains a one-variable change.

### Phase C: Local Script Retirement

Delete only after Phases A and B remain stable across the monitoring period:

- Retired local duplicates for the following tool names:
   - `export_core_contracts_jsonl`
   - `validate_contract_alignment`
   - `ingest_wa_fingerprints_to_contracts`
   - `merge_document_records`
   - `merge_document_records_with_profiles`
   - `extract_fingerprint_index`
   - `materialize_dialect_views`
   - `summarize_unified_documents`

Implementation status (2026-03-06):

- Completed for PR C scope.
- Local duplicates above were removed from `07-tools/extraction`.
- Adapter runner and project-owned extraction scripts remain.

Keep:

- `07-tools/extraction/run_pipeline_adapter.py`
- Any project-specific extraction scripts not represented in central registry (for example `_extract_wa_sources.py` if still project-owned)

Acceptance criteria:
- No remaining runtime references to deleted local extraction scripts.
- Adapter and central pipeline tests pass.
- Workflow still produces expected outputs.

## Rollback Plan

If central execution regresses:

1. Set `LOUSARDZAG_USE_CENTRAL_PACKAGE=0` in affected environments.
2. Re-enable local script path in workflow (single revert commit or revert PR).
3. Re-run adapter dry-runs in both modes and integration tests.

## Verification Checklist

- [ ] Central mode dry-run succeeds
- [ ] Fallback mode dry-run succeeds
- [ ] Integration test file passes
- [ ] CI workflow executes without new hard failures
- [ ] No code references to removed local scripts remain
- [ ] Rollback path tested at least once after cutover

Quick command (single report):

```powershell
python 07-tools/extraction/check_step5_readiness.py
```

The report is written to `08-data/step5_readiness_report.json`.

## Suggested PR Breakdown

1. PR A: CI cutover and dependency wiring only
2. PR B: default-mode policy adjustment (if needed)
3. PR C: local script deletions + reference cleanup
4. PR D: WesternArmenianLLM parity (central-default adapter policy + fallback test coverage)

This keeps blast radius small and makes each stage easy to review and rollback.

## Step 5 (PR D) Parity Status - WesternArmenianLLM

Implementation status (2026-03-06):

- Completed parity updates in `C:/Users/litni/WesternArmenianLLM`:
   - `src/core_adapters.py`
   - `tests/test_core_adapters.py`
- Adapter policy now matches lousardzag central-first intent:
   - `WA_LLM_USE_CENTRAL_PACKAGE` defaults to enabled when unset.
   - Explicit incident fallback remains available via `WA_LLM_USE_CENTRAL_PACKAGE=0`.
- Validation:
   - `python -m pytest tests/test_core_adapters.py -q`
   - Result: `3 passed`