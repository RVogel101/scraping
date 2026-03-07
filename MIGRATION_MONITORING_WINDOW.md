# Migration Monitoring Window

Start date: 2026-03-06 UTC
Duration: 7 days
Scope: Post-merge stability for central extraction migration

## Monitored Repositories

1. RVogel101/lousardzag
2. RVogel101/WesternArmenianLLM

## Daily Checklist

- [ ] Confirm no extraction rollback commits were applied
- [ ] Confirm central-mode behavior remains default intent
- [ ] Confirm fallback mode still works when explicitly enabled (`*=0`)
- [ ] Confirm no reintroduction of removed duplicate extraction scripts in lousardzag
- [ ] Confirm adapter tests continue passing in both repos
- [ ] Record incidents and mitigation (if any)

## Incident Log

Use this section to record any migration-related issue.

- Date:
- Repo:
- Symptom:
- Impact:
- Mitigation:
- Resolution status:

## Daily Run Log

### Day 1 - 2026-03-06 UTC

- Rollback commit check (RVogel101/lousardzag, `origin/main`): PASS
	- No commit messages containing `revert` or `rollback` in the last 24h or since 2026-03-01.
- Central-default adapter behavior check: PASS
	- `python 07-tools/extraction/run_pipeline_adapter.py --dry-run` reported all 8 steps as `(central)`.
- Explicit fallback behavior check (`LOUSARDZAG_USE_CENTRAL_PACKAGE=0`): PASS
	- `python 07-tools/extraction/run_pipeline_adapter.py --dry-run` reported all 8 steps as `(local)`.
- Duplicate extraction script reintroduction check: PASS
	- Confirmed absent in `07-tools/extraction/`:
		- `export_core_contracts_jsonl.py`
		- `validate_contract_alignment.py`
		- `ingest_wa_fingerprints_to_contracts.py`
		- `merge_document_records.py`
		- `merge_document_records_with_profiles.py`
		- `extract_fingerprint_index.py`
		- `materialize_dialect_views.py`
		- `summarize_unified_documents.py`
- Daily adapter/integration validation commands:
	- `python 07-tools/extraction/check_step5_readiness.py`: PASS
		- `[PASS] adapter_dry_run_central (exit=0)`
		- `[PASS] adapter_dry_run_fallback (exit=0)`
		- `[PASS] integration_test (exit=0)`
	- `python -m pytest 04-tests/integration/test_central_package_integration.py -q`: PASS (6 passed)
- Secondary repository check (RVogel101/WesternArmenianLLM): BLOCKED (local path unavailable)
	- Attempted path: `C:/Users/litni/OneDrive/Documents/anki/WesternArmenianLLM`
	- Result: path not found on this machine.
	- Follow-up: run `python -m pytest tests/test_core_adapters.py -q` once the repo is available locally.

## Exit Criteria

- 7-day window completed
- No rollback events required
- No critical migration regressions
- Adapter validation/tests remain green

## Completion Record

- End date:
- Outcome:
- Approved by:
