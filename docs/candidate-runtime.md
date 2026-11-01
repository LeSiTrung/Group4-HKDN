# Verified local candidate runtime

The trained metadata checkpoint now runs through the application's actual FastEmbed/Qdrant path. It is opt-in through `EMBEDDING_EXPORT`; an empty value keeps the existing registry embedding. The current main environment remains on that baseline.

## Asset and index boundary

Point `EMBEDDING_EXPORT` to the export's `onnx-parity.json`, whose sibling `onnx/model/` contains exactly `model.onnx`, `config.json`, `tokenizer.json` and `tokenizer_config.json`. The loader checks successful finite FP32 ONNX/FastEmbed parity,384 dimensions, mean pooling, normalization,128-token settings and every asset SHA256. Missing/changed or unexpected files (including an unverified `special_tokens_map.json`) fail closed before cached vectors are accepted. Local loading is offline; it never silently substitutes another Hub model. This receipt is an operator-owned local artifact, not a signed approval or staff acceptance.

The model name and collection identity depend on model **and tokenizer/config** hashes. Both books and knowledge namespaces get separate candidate collections; existing baseline collections remain intact. Asset changes require a new validated export/restart. Batches contain at most64 embedding texts/points; failures retain old points and completed batches can be reused after restart. Obsolete chunks are deleted only after all updates succeed.

## Reproduce on Windows

Use a new trial directory. The snapshot command opens the source DB read-only and copies only published books/knowledge and public schedule records, with original IDs and seed markers. Accounts, sessions, chats, jobs and audit are never copied. An existing target is refused. Do not restore a private full database into a demonstration environment.

```powershell
$ErrorActionPreference = 'Stop'
backend/.venv/Scripts/python.exe scripts/prepare_candidate.py --source backend/runtime/library.sqlite3 --output backend/runtime/trial-01
if ($LASTEXITCODE -ne 0) { throw 'Public snapshot failed.' }
$trialData = (Resolve-Path backend/runtime/trial-01).Path
$trialExport = (Resolve-Path training/runtime/uth-minilm-2026-10-31/onnx-parity.json).Path
$oldData = $env:DATA_DIR
$oldExport = $env:EMBEDDING_EXPORT
$oldOrigins = $env:ALLOWED_ORIGINS
$oldCrawl = $env:CRAWL_INTERVAL_HOURS
try {
    $env:DATA_DIR = $trialData
    $env:EMBEDDING_EXPORT = $trialExport
    $env:ALLOWED_ORIGINS = 'http://localhost:8001,http://127.0.0.1:8001'
    $env:CRAWL_INTERVAL_HOURS = '0'
    Push-Location backend
    try {
        ./.venv/Scripts/python.exe -m app.cli index --namespace books
        if ($LASTEXITCODE -ne 0) { throw 'Book index failed.' }
        ./.venv/Scripts/python.exe -m app.cli index
        if ($LASTEXITCODE -ne 0) { throw 'Knowledge index failed.' }
    } finally { Pop-Location }
    backend/.venv/Scripts/python.exe scripts/evaluate_vector_index.py --data-dir $trialData --dataset training/runtime/dataset-2026-10-31 --output tmp/trial-vector.json
    if ($LASTEXITCODE -ne 0) { throw 'Vector evaluation failed.' }
    Push-Location backend
    try {
        ./.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --workers 1 --no-proxy-headers --no-access-log
    } finally { Pop-Location }
} finally {
    $env:DATA_DIR = $oldData
    $env:EMBEDDING_EXPORT = $oldExport
    $env:ALLOWED_ORIGINS = $oldOrigins
    $env:CRAWL_INTERVAL_HOURS = $oldCrawl
}
```

CPU indexing is portable but takes time. Stop the owning API before opening its local Qdrant index from CLI. Start Ollama separately and run `app.cli ai-check`; a healthy API or installed model does not establish live generation. Use `scripts/evaluate.py --base-url http://localhost:8001` with the existing case files for real chat/LLM checks. Linux uses the corresponding venv `bin/python` paths.

## Measured trial, 31 October 2026

The isolated trial contains5,569 public book records/27 knowledge entries,18,441 books chunks/126 knowledge chunks. Candidate preparation used13,684 unique texts encoded in FP32 on the existing local GPU (23.27s,516,385,792 peak allocated bytes);32 sampled vectors matched FastEmbed CPU within1.44e-7. This is sampled numerical parity, not a bitwise proof for the whole corpus. Qdrant preparation took161.01s using those vectors. Runtime query embedding used the actual CPU FastEmbed loader. The CPU CLI above is the normal reproduction path; it does not require PyTorch in the backend.

Same frozen354 synthetic queries, same5,569-record corpus, unchanged384-byte guard/six chunk hits/0.45 score threshold:

| Metric | Baseline | Candidate |
|---|---:|---:|
| Hit@1 | 0.432203 | 0.576271 |
| Hit@5 | 0.485876 | 0.661017 |
| MRR@5 | 0.456309 | 0.610829 |
| nDCG@5 | 0.463898 | 0.623509 |

There were81 per-query nDCG improvements,7 regressions and266 ties. No over-budget query was excluded; no training, parameter/threshold tuning or gold answer was supplied to retrieval. These chunk-path scores differ from earlier full-document training scores and are not staff-reviewed relevance. Single-run mean query times244.85/222.59ms include lazy model loading; no concurrency/SLA conclusion follows.

Both baseline and candidate passed80 live chat cases with Ollama running. Initial semantic checks used sourced fallback while Ollama was offline; the provider was started and the complete checks rerun without weakening guards. A temporary administrator in the trial verified20-row pages, page2, filtered reset to1/1 and source links; its account/sessions were removed afterward. Main reader accounts were not copied or modified.

## Next gate

The durable [integration evidence and seven-query review queue](validation/2026-10-31-candidate-integration.json) records corpus/dataset hashes, both metric summaries, returned sources, build/parity checks and QA cleanup. Reviewers should label relevance independently; do not retrain or tune against this frozen test queue.

Technical candidate integration is verified; production promotion remains pending a staff/user relevance pilot, review of the7 regressions, target-host memory/concurrency and deployment checks. Docker's Linux-engine endpoint is currently unavailable on this Windows host. Printed holdings, actual renewals and current dated policies still need authorized library sources. Keep the baseline configuration for the main service until those gates are satisfied.
