# DSpace collection and retrieval training plan

> Execute with the existing autonomous authorization. Use independent agents for import and training; main agent owns collection/integration and final verification.

**Goal:** Collect the complete currently exposed public UTH digital metadata inventory, integrate validated records into the library chatbot, and run a measured local embedding fine-tune.

**Architecture:** Fixed-host HTTPS collector reuses network/robots guards, stages hashed per-item snapshots with resumability, and reconciles every sitemap ID. Existing BookInput/SQLite catalog stays authoritative for structured fields. Train a separate multilingual embedding checkpoint on grouped weak-supervision data with a frozen dev/test split and baseline comparison; no silent production promotion or external publication.

- [x] COLLECT-01: RED→GREEN tests for same-host sitemap IDs, snapshot integrity, robots denial, rate/retry limits and resume. Collect with at most2 simultaneous metadata requests and4 request starts/second, slowing/stopping on server limits. No full text, OPAC robots bypass, private paths, paid provider or credential use.
- [x] IMPORT-01: Agent normalizes metadata roles/year/visibility, reports rejects, validates dry-run, preserves operator edits and imports explicitly after SQLite backup. Main agent verifies live catalog/search against collected samples.
- [x] TRAIN-01: Agent creates isolated local training environment, provenance/grouped dataset, one-step smoke, one bounded fine-tune and frozen retrieval evaluation. Record real metrics, sample counts, hashes, hardware and failure limits. Synthetic evaluation is not staff acceptance. Do not upload models/data.
- [x] QA-01: Run backend tests plus representative real API search/RAG checks. Review collection completeness/import counts/training evidence; update status files and document external printed-catalog/full-text/current-policy limits. Repair concrete failures before closing the milestone.

**Review boundaries:** Public digital documents are not the complete physical-book inventory. Missing/withdrawn records and failed HTTP calls are distinct. Metadata may omit abstracts or mislabel supervisors as authors. Never infer live loan availability. Keep the existing Qwen1.7B library-only/source/prompt guards and all uncommitted prior work.
