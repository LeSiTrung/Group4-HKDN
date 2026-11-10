# Local performance and answer validation

These are repeatable developer checks on the current Windows host, not a
production capacity guarantee or library acceptance. Do not run them against
the university's OPAC or a public production service.

## Concurrent read-only requests

```powershell
backend/.venv/Scripts/python.exe scripts/benchmark_load.py --concurrency 1 5 10 20 --requests 20 --output tmp/load.json
backend/.venv/Scripts/python.exe scripts/benchmark_load.py --profile llm --concurrency 1 2 4 --requests 4 --output tmp/llm-load.json
```

The runner permits only a loopback API and local Ollama/disabled model provider,
caps concurrency and requests, uses pooled HTTP connections, and counts wrong
answers, transport errors and rate limiting as failures. It searches the local
catalog and sends guest questions; it does not call OPAC availability, register
accounts or change loans. Report p50/p95/max, elapsed time, throughput, HTTP
statuses and answer modes. A successful FAQ fallback is not a model generation.
The model has a two-call admission bound; inspect fallback modes under load.

All requests originate from one IP and the application's rate limit remains
enabled. The phases are closed-loop synthetic clients, not a claim about twenty
human users' behavior. Avoid unrelated CPU-heavy work during timing comparisons.
Warm-up is recorded separately; it does not establish a controlled cold start.

`tests/test_multi_reader_concurrency.py` separately checks five synthetic account
sessions saving messages concurrently against a temporary SQLite database and
rejecting cross-account history access. Its in-process transport and disabled
models isolate correctness; its timings are not network-load measurements.

The catalog keeps at most four public metadata projections, keyed by a database
revision incremented by triggers on book/MARC writes. Committed edits, deletion,
withdrawal and MARC updates invalidate the projection; no user/session/history
data is cached. Existing SQLite data is preserved. The ignored local rollback
snapshot from this session is not a deployment backup or a public artifact.

## Frozen source-based evaluation

`tests/evaluation/independent-library-2026-11-07.json` was authored by a separate
agent without inspecting the chatbot implementation or outputs. It embeds only
selected published public evidence. The initial run and review are retained in
`docs/validation/2026-11-07-independent-results.json` and
`docs/validation/2026-11-07-independent-review.json`.

```powershell
backend/.venv/Scripts/python.exe scripts/evaluate_independent.py
```

The recorder refuses to overwrite its initial result or silently accept a
different dataset hash. It records twenty guest API cases and seven local Qwen
calls supplied with correct frozen evidence. Actual Ollama HTTP receipts, raw
outputs, validated results and latency are separate from the content review.
The runner does not grade semantic correctness automatically. Keep full,
partial, failed, rejected and critical-error counts separate.

After findings are exposed and used for fixes, reruns are known-set regressions.
They cannot be advertised as fresh holdout accuracy. The independent AI review
does not replace human readers or library staff. Current source selection asks
Qwen for numbered sentences and derives returned wording/citations on the
server, preventing changes to the selected facts. Relevance, omitted conditions,
stale sources and coverage still require evaluation; valid citations alone do
not prove a complete answer.

## Real transactions

The user confirmed on 07/11/2026 that the library has not supplied permission or
an API. Actual transaction acceptance is blocked. The local bridge tests and
`2026-11-07-transaction-readiness.json` document authentication, confirmation,
idempotency, timeout uncertainty, receipt isolation and audited reconciliation.
They are synthetic contracts, not a real loan/renewal result.

To clear that blocker, the library must provide an approved environment and
contract, a test reader token and eligible loan, upstream idempotency/ownership
rules, and a way to independently confirm the official receipt and due date.
Do not put credentials in chat, reports, frontend code or load-test files. Do
not retry an uncertain real renewal until its result has been reconciled.
