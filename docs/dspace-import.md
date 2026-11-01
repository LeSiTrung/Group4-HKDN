# Import public DSpace metadata

The collector stores raw public item snapshots under `backend/runtime/uth-dspace/records/<uuid>.json`. This importer does not make network requests, download full text, or access Qdrant.

Each snapshot contains `source_url`, an aware ISO `fetched_at` timestamp, `record` (the DSpace JSON object) and `sha256`. The hash is SHA-256 of the UTF-8 canonical JSON record using `ensure_ascii=False`, `sort_keys=True`, `separators=(',', ':')`.

From the repository root:

```powershell
# Collect the current public sitemap inventory; reuse valid local snapshots on resume.
backend/.venv/Scripts/python.exe scripts/collect_dspace.py --output backend/runtime/uth-dspace
# Stage and review without opening/creating the application database.
backend/.venv/Scripts/python.exe scripts/import_dspace.py backend/runtime/uth-dspace/records --publish
# Back up the existing SQLite database first; then apply explicitly.
backend/.venv/Scripts/python.exe scripts/import_dspace.py backend/runtime/uth-dspace/records --publish --apply
# Stop the API before opening local Qdrant from CLI.
Push-Location backend
./.venv/Scripts/python.exe -m app.cli index --namespace books
Pop-Location
```

Collection is fixed to UTH's public digital repository. It rechecks robots, uses at most two workers with globally paced starts (at least0.25 seconds apart, slower if robots requires), respects Retry-After and checkpoints canonical hashes. Per-item401/404/410 are recorded separately; authentication is never attempted. Global403/robots denial or persistent busy responses stop collection. `--limit N` is a partial smoke only. Inspect manifest.json for every target, collected/restricted/failed/remaining counts; complete means reconciled inventory, not universally readable metadata. Never run two collectors or two local-Qdrant owners concurrently. Resume preserves the first successful snapshot; use a separately reviewed refresh/reconciliation policy for changed or withdrawn upstream records.

The31/10/2026 run reconciled5,578 items:5,569 public metadata snapshots and9 restricted401 items, zero technical failures/remaining. Import accepted5,568 and quarantined one missing-title source. The main catalog contains5,569 records including its earlier OPAC seed. Repeat apply imported0/skipped5,568. The initial SQLite backup is local/private; runtime metadata, vectors, training weights and backups are ignored by Git. A fresh checkout must collect/import or restore an authorized data package.

Without `--publish`, new records remain drafts. Without `--apply`, no catalog writes occur. The report defaults to `dspace-import-report.json` alongside the records directory; `--report PATH` selects another path outside the raw records directory. A rejected snapshot produces exit1 and a filename/reason entry in the report. An explicit apply imports accepted records atomically even if other snapshots were rejected; reconcile the report before claiming complete coverage.

`normalize_snapshot(snapshot, published=False)` returns the existing `BookInput`. It requires canonical matching UTH item URLs/UUIDs, matching content hashes, an aware fetch timestamp, item type and explicit archived/discoverable/nonwithdrawn flags. It keeps source metadata missing instead of inventing an abstract, year or availability. Unknown/multiple issue years remain blank. Labelled supervisor entries (`GVHD`, `CBHD`, người hướng dẫn) are omitted from the author display; raw metadata remains untouched. Overlong bibliographic fields are rejected for review, never silently clipped. Every staged JSON file is accepted or reported rejected, including malformed files and filename/record identity mismatches.

Imports use one `BEGIN IMMEDIATE` transaction and source URL identity. An existing record is always skipped, preserving operator edits, draft status and withdrawals. No missing source is deleted, and this command is not a complete incremental synchronization policy: an existing published record is not automatically withdrawn merely because its newly collected snapshot is rejected. Source withdrawals and later updates need a separately reviewed reconciliation step.

The existing catalog normalizes/scans rows and performs fuzzy comparisons in Python. At several thousand records, measure real lookup latency before claiming capacity; this importer does not change ranking or search architecture.

Prepare the books index **before** a demonstration after a bulk import. The current5,569 published records produce18,441 embedding chunks; the first CPU build takes many minutes and holds local Qdrant exclusively. Do not leave this first build to a reader's semantic-search request. Unchanged later builds reuse persisted hashes/embeddings. The five local full-catalog lexical probes measured680–1,044ms each; these are single-run measurements, not a concurrent-service SLA.
