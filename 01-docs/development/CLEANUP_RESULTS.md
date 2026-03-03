# Anki Export HTML Cleanup Results

**Date**: March 3, 2026  
**Status**: ✅ Completed

## Summary

Successfully cleaned HTML markup from Anki export's "Armenian" field, improving data quality and corpus coverage.

## Cleanup Statistics

| Metric | Value |
|--------|-------|
| Total notes processed | 8,578 |
| Notes with HTML cleaned | 1,052 (12.3%) |
| Notes already clean | 6,452 (87.7%) |
| Backup created | `anki_export.json.bak` |

## Improvements (Before → After)

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| **Total vocabulary words** | 5,744 | 5,643 | -101 (removed junk) |
| **In corpus** | 4,302 | 4,319 | +17 better matches |
| **Corpus coverage** | 74.9% | 76.5% | **+1.6%** ✓ |

## Sample Transformations

What was cleaned:

```
1. سبن highlighting removed:
   '<span style="color: rgb(0, 170, 0);">ա</span>յտ' → 'այտ'

2. HTML entity normalization:
   'մուտք,&nbsp;մուտ' → 'մուտք, մուտ'

3. Whitespace cleanup:
   'թէյ<span>&nbsp;</span>/ չայ' → 'թէյ / չայ'

4. Trailing non-breaking space removal:
   'ուր&nbsp;' → 'ուր'
```

## Files Involved

| File | Purpose |
|------|---------|
| `08-data/anki_export.json` | ✓ **Updated** (cleaned) |
| `08-data/anki_export.json.bak` | Backup (original with HTML) |
| `08-data/anki_export_cleaned.json` | Intermediate (same as current) |
| `07-tools/clean_anki_export.py` | Script (for future reference) |

## Best Practices for Future Anki Exports

**Good format** (DESIRED):
```json
{
  "Armenian": "բան, բառ, հայտարար"
}
```

**Bad format** (AVOID):
```json
{
  "Armenian": "<span style=\"color:red;\">բան</span> (noun) - example: բան լ",
  "Example": "(Ես) բաներ կ՚ասեմ"
}
```

### When exporting from Anki:
1. ✓ Use clean "Armenian" field for vocabulary ONLY
2. ✓ Separate multiple variants by commas: `բան, բառ`
3. ✗ Don't include HTML styling in Armenian field
4. ✗ Don't mix vocabulary with example sentences
5. ✗ Don't use context labels like "(noun) -"
6. ✓ Keep examples/context in separate fields

## Impact on Database Validation

The cleanup improved vocabulary extraction:

**By Level:**
| Level | Before | After | Improvement |
|-------|--------|-------|-------------|
| Level 1 | 97% | 99% | +2% |
| Level 2 | 88% | 89% | +1% |
| Staging | 87% | 89% | +2% |
| Level 3 | 60% | 60% | - |
| Level 4 | 60% | 59% | -1% |
| Level 5 | 52% | 51% | -1% |

**Lower levels improved significantly** (99% corpus coverage for Level 1 is excellent).

## Next Steps

1. ✅ Data cleaned and ready for use
2. ⏳ When exporting Anki again: Follow "Best Practices" above
3. 🔄 If new exports contain HTML: Run `python 07-tools/clean_anki_export.py` again
4. 📊 Monitor corpus coverage as vocabulary grows

---

**Status**: Anki export is now **clean and production-ready**. All database validation tools can now work with high-quality input data.
