# QA defect ledger

These tests come from `qa/exploration-verification`. Each one asserts the **correct** behaviour; a
failing test is an open, recorded defect, not a broken test. They are intentionally outside
`pytest.ini` testpaths, so CI stays green while the ledger stays visible.

```bash
python -m pytest qa/tests -q -p no:cacheprovider
```

Status when this branch was opened (provider keys unset): 54 passed, 38 failed, 1 skipped.
Fixed defects stay here as regression tests. See `docs/roadmap/MILESTONES.md` (M10) for the open list.
