# Local UTH embedding training

This is a local retrieval-model experiment, not from-scratch LLM training. The base is `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dimensions). Qwen3-1.7B and the application's production embedding configuration are unchanged by these scripts.

## Environment

Run from the repository root. Use a separate training environment; do not install PyTorch into the backend venv:

```powershell
uv venv training/.venv --python 3.11
uv pip install --python training/.venv/Scripts/python.exe -r training/requirements.txt --torch-backend cu128
```

The measured environment uses Python3.11.17, PyTorch2.11.0+cu128, SentenceTransformers6.2.0, Transformers5.22.1, Datasets5.1.0 and Accelerate1.15.0. Exact package resolution is in `training/requirements-lock.txt`; the CUDA wheel index must still be selected explicitly when reproducing it. The local RTX3060 Laptop GPU has6GiB VRAM. No paid GPU/API, external tracker, Hub upload or production deployment is used.

## Data and split policy

Input is the collector's public DSpace metadata snapshots under `backend/runtime/uth-dspace/records`. Only item records with inArchive=True, withdrawn=False, discoverable=True, matching canonical source identity and matching canonical-record SHA256 enter the dataset. Metadata/value arrays must be well formed. Titles must be nonempty strings of at most500 characters; oversized titles are rejected and counted, never silently clipped. Selected fields are title, subjects and public abstract when present; missing abstracts remain missing. Raw source snapshots are preserved independently.

Queries are deterministic **weak supervision**: partial-title lookup requests, including no-accent variants. They are not questions written or approved by librarians/users. Each normalized title family supplies one canonical pair; duplicated parts labelled Thuyết minh/Bản vẽ/Phụ lục share relevance. Title families and shared-author connected components stay wholly within train, dev or test. Unrelated works by one author are not made mutually relevant. Grouping is conservative metadata processing, not an authoritative bibliographic resolver; topic-related false negatives and unlabelled duplicate works may remain.

The script writes immutable corpus/pairs/group/rejection files and hashes. A repeat build refuses to replace an existing frozen manifest. Training verifies those hashes and disjoint split components before loading the model. Dev/test queries and their positive pairs are excluded from training; their corpus documents remain retrievable because retrieval evaluates against the public catalog.

```powershell
training/.venv/Scripts/python.exe training/prepare_data.py --source backend/runtime/uth-dspace/records --output training/runtime/dataset-v1
training/.venv/Scripts/python.exe training/train_embedding.py --dataset training/runtime/dataset-v1 --output training/runtime/smoke --smoke
training/.venv/Scripts/python.exe training/train_embedding.py --dataset training/runtime/dataset-v1 --output training/runtime/run-v1
```

Freeze the final dataset only after the collector has completed and reconciled its inventory. A separate partial pilot is permitted for software/resource smoke checks, but must never be relabelled as the completed corpus or used to tune the final test set.

## Training and measurement

- Template: the installed train-sentence-transformers skill's SentenceTransformer trainer example, adapted to local UTH metadata and no publication.
- MultipleNegativesRankingLoss with `BatchSamplers.NO_DUPLICATES`, batch8, explicit128-token encoder limit, seed31, learning rate2e-5, FP32 weights and bf16 autocast on this GPU.
- One bounded run: at most300 optimizer steps/one epoch budget. Dev nDCG@5 selects the saved checkpoint; the frozen test is evaluated before and after, without selecting hyperparameters from test.
- Metrics: Hit/accuracy@1 and@5, Recall@5, MRR@5, nDCG@5 and MAP@5. Baseline and final scores, dataset/base revisions, environment, runtime and peak allocated memory are saved to `metrics.json`.
- `VERDICT: WIN|MARGINAL|REGRESSION` compares test nDCG@5 with the baseline. This is an experiment label, not a production acceptance gate or a general AI-accuracy claim.
- Logging/checkpoints/model weights remain under ignored `training/runtime/`. The end-of-run model is `final/`; logs are local, including `logs/experiments.md`.

## Verification and remaining gate

### Completed run, 31 October 2026

The final frozen corpus contains5,568 documents from5,569 source snapshots (one missing title rejected), with4,458 train/402 dev/354 test pairs across5,214 work groups. A real300-step CUDA run completed in157.58 seconds including baseline/final evaluation, with2,305,350,144 peak allocated GPU bytes. Dev selected checkpoint300. On the354 synthetic held-out test queries:

| Metric | Base | Fine-tuned |
|---|---:|---:|
| Hit@1 | 0.4237 | 0.5734 |
| Hit@5 | 0.4689 | 0.6808 |
| Recall@5 | 0.4689 | 0.6784 |
| MRR@5 | 0.4408 | 0.6137 |
| nDCG@5 | 0.4478 | 0.6297 |

Artifacts are local: `training/runtime/dataset-2026-10-31/`, `training/runtime/uth-minilm-2026-10-31/metrics.json` and `final/`. The experiment verdict is WIN; no claim about staff-approved accuracy follows from synthetic partial-title queries. Production still uses the base FastEmbed model. The saved report's base_revision is null after checkpoint reload; exact original Hub revision was not captured, so it is not a fully pinned model reproduction. Dataset file hashes and resolved package versions are recorded. Export/runtime parity passed later in [EXPORT-01](embedding-export.md); separate-index pipeline comparison and staff-reviewed evaluation remain required before promotion.

Twelve lightweight dataset tests cover deterministic grouping/splits, duplicate relevance, author separation, malformed/withdrawn data, source integrity/publication flags, immutable output and corrupted evaluation data. A separate209-record pilot completed a real one-step CUDA smoke with checkpoint reload, dev/test baseline and final evaluation: peak allocated1.93GB and9.06s after model loading. Pilot scores were unchanged, as expected for its single warmup step; this is not the full training result.

The trained checkpoint must not replace the deployed FastEmbed model automatically. The current application uses an ONNX/FastEmbed path; deployment needs a compatible export, embedding/parity checks, a separate versioned vector index, a pipeline regression comparison and broader staff-reviewed held-out evaluation. Keep the baseline if the experiment regresses or the export is unverified.

The earlier Optimum export attempt was blocked by incompatible Transformers constraints. This is now resolved through the supported direct PyTorch exporter in a separate CPU environment with the same ST6.2/Transformers5.22 versions, leaving training/backend environments unchanged. Actual ONNX and offline FastEmbed parity passed against50 original-runtime vectors, max absolute error below3.1e-7. Source/output hashes, tokenizer/mean-pooling settings and128-token boundary inputs were checked. See [export evidence and reproduction](embedding-export.md). Application registration, a separate vector index, complete pipeline comparison and staff-reviewed relevance remain separate promotion gates; numerical parity does not prove retrieval quality. No forced dependency install, model upload or automatic serving change occurred.

Primary references: [SentenceTransformers training](https://www.sbert.net/docs/sentence_transformer/training_overview.html), [retrieval evaluator](https://www.sbert.net/docs/package_reference/sentence_transformer/evaluation.html), [MNRL](https://www.sbert.net/docs/package_reference/sentence_transformer/losses.html).
