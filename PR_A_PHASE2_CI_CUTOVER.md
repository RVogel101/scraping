## PR Title

`chore(extraction): cut CI pipeline over to central package module execution`

## Overview

This PR implements Phase 2 / PR A of the migration by switching extraction execution in CI from local script paths to central package module invocations.

## What Changed

### CI dependency wiring

- Updated `.github/workflows/extraction_pipeline.yml` install step to include central package:
	- `pip install git+https://github.com/RVogel101/armenian-corpus-core@main`

### CI extraction command cutover

- Replaced direct local script invocations with central module invocations:
	- `python -m armenian_corpus_core.extraction.export_core_contracts_jsonl`
	- `python -m armenian_corpus_core.extraction.validate_contract_alignment`
	- `python -m armenian_corpus_core.extraction.ingest_wa_fingerprints_to_contracts`
	- `python -m armenian_corpus_core.extraction.merge_document_records`
	- `python -m armenian_corpus_core.extraction.merge_document_records_with_profiles`
	- `python -m armenian_corpus_core.extraction.extract_fingerprint_index`
	- `python -m armenian_corpus_core.extraction.materialize_dialect_views`
	- `python -m armenian_corpus_core.extraction.summarize_unified_documents`

### Adapter-only path preserved

- Kept adapter dry-run check unchanged:
	- `python 07-tools/extraction/run_pipeline_adapter.py --dry-run`

## Validation Performed

- Confirmed central module entrypoints resolve in `wa-llm`:
	- `python -m armenian_corpus_core.extraction.export_core_contracts_jsonl --help`
	- `python -m armenian_corpus_core.extraction.merge_document_records --help`
- Re-ran readiness checker successfully:
	- `python 07-tools/extraction/check_step5_readiness.py`
	- Result: central dry-run pass, fallback dry-run pass, integration test pass

## Why This PR

- Removes operational coupling to duplicated local extraction scripts in CI.
- Makes CI execution path consistent with central-package migration goals.
- Keeps rollback safety through adapter/fallback behavior.

## Out Of Scope

- No deletion of local extraction scripts in this PR (planned for PR C).
- No runtime default policy change in this PR (planned for PR B).

## Post-Merge Checks

1. Verify extraction workflow succeeds on next run.
2. Confirm artifacts are still generated under `08-data/*` patterns.
3. Compare outcomes against Phase 1 baseline evidence:
	 - `08-data/step5_readiness_baseline_phase1.txt`
	 - `08-data/step5_readiness_report.json`
