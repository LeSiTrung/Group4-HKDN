# Public Library Data Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement and verify each task below.

**Goal:** Expand reviewed public library knowledge and answer regular opening hours from an official source without representing them as confirmed live hours.

**Architecture:** Reuse KnowledgeInput, SQLite, the existing crawler and grounded retrieval. Store a dated collection manifest and curated FAQ pack; import explicitly and idempotently, preserving operator edits. Keep dated schedules authoritative for today, with a clearly labelled regular-hours reference only when appropriate. No new dependency, production deployment or OPAC crawling against robots.txt.

**Spec:** User requests public library data and explicitly selects official library opening hours. Existing AGENTS.md delegates routine design decisions; no separate approval gate.

**Tech stack:** Python/FastAPI/SQLite, existing Qdrant/FastEmbed/Ollama.

- [x] DATA-01: Record sitemap/collection coverage, failures, exclusions, conflicts and official PDF page12 provenance in data/documents. Curate a separate KnowledgeInput JSON pack; do not publish raw crawls, sample credentials or unrelated pages.
- [x] DATA-02: Add app.cli import-knowledge FILE using existing validation/insert helpers. Validate the whole pack before writes, skip existing question/source pairs without overwriting or republishing them. RED→GREEN tests cover idempotency, operator edits and invalid-pack atomicity.
- [x] HOURS-01: Add source-backed regular-hours routing in assistant.py. Preserve invalid/multiple-branch and future-date clarification, dated schedule precedence, lunch breaks, unknown Sunday and withdrawal. RED→GREEN tests cover these boundaries; no hardcoded model-generated hours.
- [x] Verify backend suite, launcher, live development corpus and new data/hour cases. Back up the local SQLite file before importing; restart API with existing Qwen3-1.7B and check a guest UI response. Update technical status and distinguish collection coverage from a full catalog or staff approval.

**Review focus:** Conflicting/undated hours are references, not current assertions; no fake effective dates or verifier. Imports must not overwrite accounts/admin content. Excluded or robots-blocked sources stay out of inference. Raw pages with placeholder text or credentials do not enter the published corpus. Existing date/branch routing must remain tested.

Outcome: DATA-01/02 and HOURS-01 verified locally. See docs/validation/2026-10-31-public-data.json. Ruling: retain explicit weekday/date clarification; regular table remains available without asserting a current schedule. Browser control unavailable; API checks substituted, no UI smoke claimed. No push, merge or deployment performed.
