# Retrieval quality and embedding export implementation plan

> Execute under the user's continuing autonomous authorization. Main owns catalog/search evaluation and integration. An independent worker owns only local export; final review is read-only. Preserve all existing uncommitted work and user AGENTS.md.

**Goal:** Improve measured catalog precision on real public metadata and make the trained embedding checkpoint evaluable without altering the deployed model or tuning on the frozen training test.

**Architecture:** Keep structured SQLite metadata authoritative. Add only verified exact-title/author intent handling ahead of existing fuzzy/semantic paths. Freeze metadata-derived lookup cases before code changes, measure before/after on the same catalog, and report these as developer retrieval checks. Resolve ONNX dependencies in an isolated export environment, verify against original training-runtime tensors, and retain baseline production until runtime/pipeline acceptance.

**Scope/assumptions:** No paid API/GPU, upload, recrawl, credentials, production deployment, user-data edits or model promotion. Current branch/workspace contains ongoing authorized work; do not reset or move it. No new database tables or search framework. Missing authors, duplicate titles, no-accent collisions, withdrawals, filters and follow-up context must remain explicit.

- [x] SEARCH-03: Freeze a small real-metadata exact-title/author lookup corpus plus adversarial synthetic cases. Save baseline precision/recall/Hit@k/latency and corpus hash. Reproduce actual wrong/broad results before changing shared catalog logic. Author intent must search author metadata, never unrelated descriptions; exact titles retain every word and duplicates. Ordinary topics and typo fallback remain usable.
- [x] EXPORT-01: Independently inspect checkpoint/export helper. Use a separate compatible local environment or a supported direct exporter; never downgrade training/backend environments or force incompatible packages. Test candidate/integrity gates, export exact weights, compare against tensors produced in the original training environment across varied lengths/Unicode, then check FastEmbed compatibility if feasible. Record exact hashes, versions, failures and limits; no production promotion.
- [x] QA-03: Run affected tests, full backend suite and representative live catalog/chat regression, with real Ollama semantic verification where affected. Review the final diff independently. Update technical evidence and four status files with actual gains/regressions; do not claim staff-approved quality or full project completion.

**Review focus:** A common word must not select a different full title; explicit authors cannot match abstract mentions; duplicate/withdrawn/kind-filtered records stay correct; export must use trained weights and identical tokenizer/pooling/normalization, and fails closed on mismatch; measurements must not use labels to generate results or hide failed/no-hit cases.
