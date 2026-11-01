# Docker verification, 1 November 2026

## Current result

Docker Desktop's `desktop-linux` context now reaches Engine29.9.2 on WSL2/Linux amd64. The previous unavailable-engine observation is historical. No Windows/WSL/security setting or daemon configuration was changed in this session.

The existing Dockerfile builds successfully with native exit0. Its Node22 stage runs a clean npm install and production build; Python3.11 runs the application as UID10001 with all capabilities dropped and no-new-privileges. The image contains neither backend/.env nor training weights. Runtime/model data are mounted separately; the main reader database is never mounted into the trial.

The first build could not find `docker-credential-desktop` even though Docker was installed. Prefixing the installed Docker binary directory to this process's PATH fixed resolution; credentials/configuration were not rewritten:

```powershell
$dockerBin = Split-Path (Get-Command docker).Source
$env:PATH = $dockerBin + ';' + $env:PATH
docker version
docker build --tag uth-library:local --progress plain .
if ($LASTEXITCODE -ne 0) { throw 'Docker build failed.' }
```

## Isolated full-data trial

The measured container `uth-library-qa-20261101` listens only on `http://127.0.0.1:8100`. It uses a new public-only snapshot at `backend/runtime/docker-qa-20261101`, not the main runtime. It contains5,569 catalog records/31 reviewed or explicitly unconfirmed FAQs. The verified local candidate ONNX receipt/assets are mounted read-only; actual Linux CPU FastEmbed loads them. Ollama is reached through `host.docker.internal:11434`, using the existing local Qwen3-1.7B service without publishing its API to the LAN or downloading a second model. The main Windows service at8000 retains baseline embedding.

Prepare a new content-only directory using [candidate runtime instructions](candidate-runtime.md), then mount that directory at `/var/lib/library`. Keep `DATA_DIR=/var/lib/library`, explicit origins matching the local port, `CRAWL_INTERVAL_HOURS=0`, one Uvicorn worker, loopback publishing and the nonroot user. For a local export, mount its receipt at `/model/onnx-parity.json` and its exact asset directory at `/model/onnx/model`, both read-only; set `EMBEDDING_EXPORT=/model/onnx-parity.json`. Never copy the full private runtime or an account backup into a demo. Stop the owning API before copying/reindexing local Qdrant. The measured trial reused the separately prepared public candidate collections; raw training/cache files were not copied.

A fresh Git clone includes17 FAQ seeds and one catalog seed, not the local5,569-record harvest or model artifacts. To add the reviewed public packs to a running container:

```powershell
docker exec YOUR_CONTAINER python -m app.cli import-knowledge /app/data/faq/public-library-2026-10-31.json
docker exec YOUR_CONTAINER python -m app.cli import-knowledge /app/data/faq/public-library-2026-11-01.json
docker exec YOUR_CONTAINER python -m app.cli ai-check
```

Import is idempotent and preserves operator edits/withdrawals. Follow [digital metadata import](dspace-import.md) for a reconciled public catalog. Do not treat image build or model-catalog readiness as proof of generated answers; this trial separately ran live semantic checks.

## Verified boundaries

- 25 HTTP/application checks at the initial27-FAQ checkpoint: built frontend, UID10001, fresh named-volume seeding, no default admin, registration, real sourced LLM generation, owner isolation, cross-origin rejection, session/history persistence after container restart, deletion password requirement and removal of all synthetic accounts.
- 86/86 live chat cases on both final Windows/baseline and Linux/candidate profiles after the source/data update and image rebuild. These are development regressions, not independent relevance labels or a production throughput benchmark.
- Actual SQLite backup/restore inside Linux retained5,569 books/27 FAQs at that earlier checkpoint, passed integrity check, and had zero users/sessions/messages. The later reviewed pack increases FAQs to31. Restore never overwrites an existing destination.
- Compose configuration and the actual Caddy image validate successfully. An isolated Caddy/app network also passed10 HTTPS checks on localhost8443, including Secure/HttpOnly/SameSite=Strict cookies, HSTS, authenticated requests and origin rejection. Its local CA was passed only to the test client; host trust stores were not changed. Temporary TLS containers are stopped after QA, and the synthetic TLS account was deleted.

See [durable evidence](validation/2026-11-01-data-container.json). Local TLS does not prove public DNS/ACME, target-host uptime, capacity, or authorized circulation. The production Compose stack also needs its own target-host acceptance and a persistent model volume; this trial used host Ollama instead of the Compose Ollama service. No public deployment or remote CI is claimed.
