# Migration Monitoring Window

Start date: 2026-03-07 UTC
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

## Exit Criteria

- 7-day window completed
- No rollback events required
- No critical migration regressions
- Adapter validation/tests remain green

## Completion Record

- End date:
- Outcome:
- Approved by:
